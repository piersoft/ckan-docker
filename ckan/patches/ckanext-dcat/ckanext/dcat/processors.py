from __future__ import print_function

from builtins import str
from builtins import object
import sys
import argparse
import xml
import json
from pkg_resources import iter_entry_points
import logging
log = logging.getLogger(__name__)
from ckantoolkit import config

import rdflib
import rdflib.parser
from rdflib import URIRef, BNode, Literal
from rdflib.namespace import Namespace, RDF, XSD
import datetime
from dateutil.parser import parse as parse_date
import ckan.plugins as p

from ckanext.dcat.utils import catalog_uri, dataset_uri, url_to_rdflib_format, DCAT_EXPOSE_SUBCATALOGS
from ckanext.dcat.profiles import DCAT, DCT, FOAF
from ckanext.dcat.exceptions import RDFProfileException, RDFParserException

HYDRA = Namespace('http://www.w3.org/ns/hydra/core#')
DCAT = Namespace("http://www.w3.org/ns/dcat#")
DCATAPIT = Namespace("http://dati.gov.it/onto/dcatapit#")
RDFS = Namespace("http://www.w3.org/2000/01/rdf-schema#")
RDF_PROFILES_ENTRY_POINT_GROUP = 'ckan.rdf.profiles'
RDF_PROFILES_CONFIG_OPTION = 'ckanext.dcat.rdf.profiles'
COMPAT_MODE_CONFIG_OPTION = 'ckanext.dcat.compatibility_mode'
DEFAULT_RDF_PROFILES = ['euro_dcat_ap']
VCARD = Namespace("http://www.w3.org/2006/vcard/ns#")
CKAN_SITE_URL='ckanext.dcat.base_uri'
PREF_LANDING= config.get('ckanext.dcat.base_uri')

class RDFParserException(Exception):
    pass


class RDFProfileException(Exception):
    pass

class RDFProcessor(object):

    def __init__(self, profiles=None, compatibility_mode=False):
        '''
        Creates a parser or serializer instance

        You can optionally pass a list of profiles to be used.

        In compatibility mode, some fields are modified to maintain
        compatibility with previous versions of the ckanext-dcat parsers
        (eg adding the `dcat_` prefix or storing comma separated lists instead
        of JSON dumps).

        '''
        if not profiles:
            profiles = config.get(RDF_PROFILES_CONFIG_OPTION, None)
            if profiles:
                profiles = profiles.split(' ')
            else:
                profiles = DEFAULT_RDF_PROFILES
        self._profiles = self._load_profiles(profiles)
        if not self._profiles:
            raise RDFProfileException(
                'No suitable RDF profiles could be loaded')

        if not compatibility_mode:
            compatibility_mode = p.toolkit.asbool(
                config.get(COMPAT_MODE_CONFIG_OPTION, False))
        self.compatibility_mode = compatibility_mode

        self.g = rdflib.ConjunctiveGraph()

    def _load_profiles(self, profile_names):
        '''
        Loads the specified RDF parser profiles

        These are registered on ``entry_points`` in setup.py, under the
        ``[ckan.rdf.profiles]`` group.
        '''
        profiles = []
        loaded_profiles_names = []

        for profile_name in profile_names:
            for profile in iter_entry_points(
                    group=RDF_PROFILES_ENTRY_POINT_GROUP,
                    name=profile_name):
                profile_class = profile.load()
                # Set a reference to the profile name
                profile_class.name = profile.name
                profiles.append(profile_class)
                loaded_profiles_names.append(profile.name)
                break

        unknown_profiles = set(profile_names) - set(loaded_profiles_names)
        if unknown_profiles:
            raise RDFProfileException(
                'Unknown RDF profiles: {0}'.format(
                    ', '.join(sorted(unknown_profiles))))

        return profiles


class RDFParser(RDFProcessor):
    '''
    An RDF to CKAN parser based on rdflib

    Supports different profiles which are the ones that will generate
    CKAN dicts from the RDF graph.
    '''

    def _datasets(self):
        '''
        Generator that returns all DCAT datasets on the graph

        Yields rdflib.term.URIRef objects that can be used on graph lookups
        and queries
        '''
        for dataset in self.g.subjects(RDF.type, DCAT.Dataset):
            yield dataset

    def next_page(self):
        '''
        Returns the URL of the next page or None if there is no next page
        '''
        for pagination_node in self.g.subjects(RDF.type, HYDRA.PagedCollection):
            # Try to find HYDRA.next first
            for o in self.g.objects(pagination_node, HYDRA.next):
                return str(o)

            # If HYDRA.next is not found, try HYDRA.nextPage (deprecated)
            for o in self.g.objects(pagination_node, HYDRA.nextPage):
                return str(o)
        return None


    def parse(self, data, _format=None):
        '''
        Parses and RDF graph serialization and into the class graph

        It calls the rdflib parse function with the provided data and format.

        Data is a string with the serialized RDF graph (eg RDF/XML, N3
        ... ). By default RF/XML is expected. The optional parameter _format
        can be used to tell rdflib otherwise.

        It raises a ``RDFParserException`` if there was some error during
        the parsing.

        Returns nothing.
        '''
        log.debug('SONO PRIMA DI URL_TO_RDFLIB con _format: %s',_format)
        _format = url_to_rdflib_format(_format)
        if not _format or _format == 'pretty-xml':
            _format = 'xml'

        try:
            self.g.parse(data=data, format=_format)
        # Apparently there is no single way of catching exceptions from all
        # rdflib parsers at once, so if you use a new one and the parsing
        # exceptions are not cached, add them here.
        # PluginException indicates that an unknown format was passed.
        except (SyntaxError, xml.sax.SAXParseException,
                rdflib.plugin.PluginException, TypeError) as e:

            raise RDFParserException(e)

    def supported_formats(self):
        '''
        Returns a list of all formats supported by this processor.
        '''
        return sorted([plugin.name
                       for plugin
                       in rdflib.plugin.plugins(kind=rdflib.parser.Parser)])

    def datasets(self):
        '''
        Generator that returns CKAN datasets parsed from the RDF graph

        Each dataset is passed to all the loaded profiles before being
        yielded, so it can be further modified by each one of them.

        Returns a dataset dict that can be passed to eg `package_create`
        or `package_update`
        '''
        for dataset_ref in self._datasets():
            dataset_dict = {}
            for profile_class in self._profiles:
                profile = profile_class(self.g, self.compatibility_mode)
                profile.parse_dataset(dataset_dict, dataset_ref)

            yield dataset_dict


class RDFSerializer(RDFProcessor):
    '''
    A CKAN to RDF serializer based on rdflib

    Supports different profiles which are the ones that will generate
    the RDF graph.
    '''
    def _add_pagination_triples(self, paging_info):
        '''
        Adds pagination triples to the graph using the paging info provided

        The pagination info dict can have the following keys:
        `count`, `items_per_page`, `current`, `first`, `last`, `next` or
        `previous`.

        It uses members from the hydra:PagedCollection class

        http://www.hydra-cg.com/spec/latest/core/

        Returns the reference to the pagination info, which will be an rdflib
        URIRef or BNode object.
        '''
        self.g.bind('hydra', HYDRA)

        if paging_info.get('current'):
            pagination_ref = URIRef(paging_info['current'])
        else:
            pagination_ref = BNode()
        self.g.add((pagination_ref, RDF.type, HYDRA.PagedCollection))

        items = [
            ('next', [HYDRA.nextPage, HYDRA.next]),
            ('previous', [HYDRA.previousPage, HYDRA.previous]),
            ('first', [HYDRA.firstPage, HYDRA.first]),
            ('last', [HYDRA.lastPage, HYDRA.last]),
            ('count', [HYDRA.totalItems]),
            ('items_per_page', [HYDRA.itemsPerPage]),
        ]
        for item in items:
            key, predicates = item
            if paging_info.get(key):
                for predicate in predicates:
                    self.g.add((pagination_ref, predicate,
                                Literal(paging_info[key])))
        return pagination_ref

    def graph_from_dataset(self, dataset_dict):
        '''
        Given a CKAN dataset dict, creates a graph using the loaded profiles

        The class RDFLib graph (accessible via `serializer.g`) will be updated
        by the loaded profiles.

        Returns the reference to the dataset, which will be an rdflib URIRef.
        '''
        uri_value = dataset_dict.get('uri')
        if not uri_value:
            for extra in dataset_dict.get('extras', []):
                if extra['key'] == 'uri':
                    uri_value = extra['value']
                    break

        dataset_ref1 = URIRef(dataset_uri(dataset_dict))

        if 'm_lps' in dataset_dict.get('holder_identifier'):
           dataset_ref1=dataset_ref1.replace(PREF_LANDING,"http://dati.lavoro.gov.it/")
        if 'r_emiro' in dataset_dict.get('holder_identifier'):
           dataset_ref1=dataset_ref1.replace(PREF_LANDING,"https://dati.emilia-romagna.it/")
           dataset_ref1=dataset_ref1.replace("dati.comune.fe.it","https://dati.comune.fe.it")
        if 'r_marche' in dataset_dict.get('holder_identifier'):
           dataset_ref1=dataset_ref1.replace(PREF_LANDING,"https://dati.regione.marche.it/")
        if 'r_toscan' in dataset_dict.get('holder_identifier'):
           dataset_ref1=dataset_ref1.replace(PREF_LANDING,"https://dati.toscana.it")
        if 'r_basili' in dataset_dict.get('holder_identifier'):
           dataset_ref1=dataset_ref1.replace(PREF_LANDING,"https://dati.regione.basilicata.it/catalog/")
        if 'r_lazio' in dataset_dict.get('holder_identifier'):
           dataset_ref1=dataset_ref1.replace(PREF_LANDING,"http://dati.lazio.it/catalog/")
        if 'aci' in dataset_dict.get('holder_identifier'):
           dataset_ref1=dataset_ref1.replace(PREF_LANDING,"http://lod.aci.it")
        if 'c_l219' in dataset_dict.get('holder_identifier'):
           dataset_ref1=dataset_ref1.replace(PREF_LANDING,"http://aperto.comune.torino.it/")
        if 'cr_campa' in dataset_dict.get('holder_identifier'):
           dataset_ref1=dataset_ref1.replace(PREF_LANDING,"http://opendata-crc.di.unisa.it/")
        if '00304260409' in dataset_dict.get('holder_identifier'):
           dataset_ref1=dataset_ref1.replace(PREF_LANDING,"https://opendata.comune.rimini.it/")
        if 'c_a345' in dataset_dict.get('holder_identifier'):
           dataset_ref1=dataset_ref1.replace(PREF_LANDING,"https://ckan.opendatalaquila.it")
        if 'uds_ca' in dataset_dict.get('holder_identifier'):
           dataset_ref1=dataset_ref1.replace(PREF_LANDING,"https://data.tdm-project.it")
        if 'm_it' in dataset_dict.get('holder_identifier'):
           dataset_ref1=dataset_ref1.replace(PREF_LANDING,"https://www.interno.gov.it/")
        if '00514490010' in dataset_dict.get('holder_identifier'):
           dataset_ref1=dataset_ref1.replace(PREF_LANDING,"http://aperto.comune.torino.it/")
        if 'm_inf' in dataset_dict.get('holder_identifier'):
           dataset_ref1=dataset_ref1.replace(PREF_LANDING,"https://dati.mit.gov.it/")


        dataset_ref = URIRef(dataset_ref1)
        log.info('dataset_ref in graph_from_dataset %s',dataset_ref)
        for profile_class in self._profiles:
            profile = profile_class(self.g, self.compatibility_mode)
            profile.graph_from_dataset(dataset_dict, dataset_ref)

        return dataset_ref

    def serialize_datasets(self, dataset_dicts, _format='xml'):
        '''
        Given a list of CKAN dataset dicts, returns an RDF serialization
        The serialization format can be defined using the `_format` parameter.
        It must be one of the ones supported by RDFLib, defaults to `xml`.
        Returns a string with the serialized datasets
        '''
        out = []
        for dataset_dict in dataset_dicts:
            out.append(self.serialize_dataset(dataset_dict, _format))
        return '\n'.join(out)


    def graph_from_catalog(self, catalog_dict=None):
        '''
        Creates a graph for the catalog (CKAN site) using the loaded profiles

        The class RDFLib graph (accessible via `serializer.g`) will be updated
        by the loaded profiles.

        Returns the reference to the catalog, which will be an rdflib URIRef.
        '''

        catalog_ref = URIRef(catalog_uri())

        for profile_class in self._profiles:
            profile = profile_class(self.g, self.compatibility_mode)
            profile.graph_from_catalog(catalog_dict, catalog_ref)

        return catalog_ref

    def serialize_dataset(self, dataset_dict, _format='xml'):
        '''
        Given a CKAN dataset dict, returns an RDF serialization

        The serialization format can be defined using the `_format` parameter.
        It must be one of the ones supported by RDFLib, defaults to `xml`.

        Returns a string with the serialized dataset
        '''

        self.graph_from_dataset(dataset_dict)

        if not _format:
            _format = 'xml'
        _format = url_to_rdflib_format(_format)

        if _format == 'json-ld':
            output = self.g.serialize(format=_format, auto_compact=True)
        else:
            output = self.g.serialize(format=_format)

        return output

    def serialize_catalog(self, catalog_dict=None, dataset_dicts=None,
                          _format='xml', pagination_info=None):
        '''
        Returns an RDF serialization of the whole catalog

        `catalog_dict` can contain literal values for the dcat:Catalog class
        like `title`, `homepage`, etc. If not provided these would get default
        values from the CKAN config (eg from `ckan.site_title`).

        If passed a list of CKAN dataset dicts, these will be also serializsed
        as part of the catalog.
        **Note:** There is no hard limit on the number of datasets at this
        level, this should be handled upstream.

        The serialization format can be defined using the `_format` parameter.
        It must be one of the ones supported by RDFLib, defaults to `xml`.

        `pagination_info` may be a dict containing keys describing the results
        pagination. See the `_add_pagination_triples()` method for details.

        Returns a string with the serialized catalog
        '''

        catalog_ref = self.graph_from_catalog(catalog_dict)
        if dataset_dicts:
            for dataset_dict in dataset_dicts:
                dataset_ref = self.graph_from_dataset(dataset_dict)
                log.debug('catalog_ref in graph %s',catalog_ref)
                cat_ref = self._add_source_catalog(catalog_ref, dataset_dict, dataset_ref)
                if not cat_ref:
                    org_site=self.g.objects(URIRef(str(catalog_ref)+"/organization/"+dataset_dict.get('owner_org')), VCARD.hasURL)
                    try:
                     self.g.add((next(org_site), DCAT.dataset, dataset_ref))
                    except StopIteration:
                     log.debug("No more elements in org_site")
                else:
                    self.g.add((cat_ref, DCAT.dataset, dataset_ref))

        if pagination_info:
            self._add_pagination_triples(pagination_info)

        if not _format:
            _format = 'xml'

        _format = url_to_rdflib_format(_format)
        output = self.g.serialize(format=_format)

        return output

    def _add_source_catalog(self, root_catalog_ref, dataset_dict, dataset_ref):
        if not p.toolkit.asbool(config.get(DCAT_EXPOSE_SUBCATALOGS, False)):
            return

        def _get_from_extra(key):
            for ex in dataset_dict.get('extras', []):
                if ex['key'] == key:
                    return ex['value']

        source_uri = _get_from_extra('source_catalog_homepage') 

        log.debug('source_uri pre patch %s',source_uri)
        # patch per harvesting per hasPart Catalog
        if 'r_marche' in dataset_dict.get('holder_identifier'):
            source_uri='https://dati.regione.marche.it/'
        elif 'r_emiro' in dataset_dict.get('holder_identifier'):
            source_uri='https://dati.emilia-romagna.it'
            source_catalog_homepage=source_uri
        elif 'r_toscan' in dataset_dict.get('holder_identifier'):
            source_uri='https://dati.toscana.it'
        elif 'r_lazio' in dataset_dict.get('holder_identifier'):
            source_uri='http://dati.regione.lazio.it'
        elif 'r_basili' in dataset_dict.get('holder_identifier'):
            source_uri='https://dati.regione.basilicata.it'
        elif 'aci' in dataset_dict.get('holder_identifier'):
            source_uri='http://lod.aci.it/'
            source_catalog_homepage=source_uri
        elif 'm_lps' in dataset_dict.get('holder_identifier'):
            source_uri='http://dati.lavoro.gov.it/'
        elif 'c_l219' in dataset_dict.get('holder_identifier'):
            source_uri='http://aperto.comune.torino.it/'
        elif 'cr_campa' in dataset_dict.get('holder_identifier'):
            source_uri='http://opendata-crc.di.unisa.it/'
        elif '00304260409' in dataset_dict.get('holder_identifier'):
            source_uri='https://opendata.comune.rimini.it/'
        elif 'c_a345' in dataset_dict.get('holder_identifier'):
            source_uri='https://ckan.opendatalaquila.it/'
        elif 'uds_ca' in dataset_dict.get('holder_identifier'):
            source_uri='https://data.tdm-project.it'
        elif 'm_it' in dataset_dict.get('holder_identifier'):
            source_uri='https://www.interno.gov.it/'
        elif 'm_inf' in dataset_dict.get('holder_identifier'):
            source_uri='https://dati.mit.gov.it/'
        elif 'uni_ba' in dataset_dict.get('holder_identifier'):
            source_uri='http://opendata.uniba.it/'
        elif 'opendata.maggioli.cloud' in dataset_dict.get('extras', []):
            source_uri='https://www.opendata.maggioli.cloud/'
            log.debug('setto source_uri per Maggioli')

        else:
            source_uri = _get_from_extra('source_catalog_homepage')

        if not source_uri:
            return
        log.debug('source_uri %s', URIRef(source_uri))
        g = self.g
        if not source_uri.endswith("/"):
           source_uri = source_uri + '/'
        catalog_ref = URIRef(source_uri)
#        dataset_dict['extras'].append({'key': 'source_catalog_homepage', 'value': source_uri})

        # we may have multiple subcatalogs, let's check if this one has been already added
        log.debug('root_catalog_ref %s',root_catalog_ref)
        if (root_catalog_ref, DCT.hasPart, catalog_ref) not in g:
            dataset_reftmp=dataset_ref
            dataset_reftmp=dataset_ref.replace(PREF_LANDING,source_uri)
            dataset_refok=URIRef(dataset_reftmp)
            log.info('dataset_ref %s',dataset_ref)

            g.add((root_catalog_ref, DCT.hasPart, catalog_ref))
            g.add((catalog_ref, RDF.type, DCATAPIT.Catalog))
            g.add((catalog_ref, RDF.type, DCAT.Catalog))
            g.add((catalog_ref, DCAT.dataset, dataset_refok))
            sources = (('source_catalog_title', DCT.title, Literal,),
                       ('source_catalog_description', DCT.description, Literal,),
                       ('source_catalog_homepage', FOAF.homepage, URIRef,),
                       ('source_catalog_language', DCT.language, Literal,),
                       ('source_catalog_modified', DCT.modified, Literal,),)

 
            # base catalog struct
            for item in sources:
                key, predicate, _type = item
                value = _get_from_extra(key)
                if key == 'source_catalog_description':
                   if not value:
                     value='Portale Dati Aperti'
                if key == 'source_catalog_title':
                   if not value:
                     value='Portale Dati Aperti'
                if key == 'source_catalog_modified':
                   if not value:
                     value='2024-01-01'
                if key == 'source_catalog_homepage':
                   if not value:
                    if 'opendata.maggioli.cloud' in dataset_dict.get('extras', []):
                     value='https://www.opendata.maggioli.cloud/organization/'+dataset_dict['organization']['name']
                     log.debug('setto homepage org Maggioli: %s',value)

                if value:
                 if key == 'source_catalog_homepage':
                    value = value.replace('##','')
                 if key == 'source_catalog_homepage' and value.endswith("/#"):
                   value = value + '/#'
                   value = value.replace('/#/#','')
                 if key == 'source_catalog_homepage' and not value.endswith("/#"):
                   value = value + '/'
                   if 'uni_ba' in dataset_dict.get('holder_identifier'):
                    if key == 'source_catalog_homepage':
                     value = 'http://opendata.uniba.it/#'
                   if 'cciaan' in dataset_dict.get('holder_identifier'):
                    value = 'https://opendata.marche.camcom.it'
                   if 'aci' in dataset_dict.get('holder_identifier'):
                      dataset_dict['extras'].append({'key': 'source_catalog_modified', 'value': _get_from_extra('dcat_modified')})
                      dataset_dict['extras'].append({'key': 'source_catalog_language', 'value': 'ITA'})
                 if key == 'source_catalog_modified':
                   default_datetime = datetime.datetime(1, 1, 1, 0, 0, 0)
                   _date = parse_date(value, default=default_datetime)
                   g.add((catalog_ref, predicate, _type(_date.isoformat(),
                                                  datatype=XSD.dateTime)))
                 else:
                   g.add((catalog_ref, predicate, _type(value)))
                   log.debug('catalog_ref alla fine %s',_type(value))
            publisher_sources = (
                                 ('identifier', Literal, DCT.identifier, False,),
                                 ('name', Literal, FOAF.name, True,),
                                 ('email', Literal, FOAF.mbox, False,),
                                 ('url', URIRef, FOAF.homepage,False,),
                                 ('type', URIRef, DCT.type, False,))
            
            if dataset_dict.get('holder_identifier'):
             identifier=dataset_dict.get('holder_identifier')
                
            if dataset_dict.get('holder_name'):
             nameid=dataset_dict.get('holder_name')
                
            _pub = _get_from_extra('source_catalog_publisher')

            # patch patch per Marche perchè non ha metadati in extra per il catalogo d'origine.
            if 'm_it' in identifier:
              _pub= '{"uri": "", "name": "Ministero degli Interni", "email": "", "url": "https://www.interno.gov.it/", "type": "http://purl.org/adms/publishertype/NationalAuthority"}'
            if 'r_marche' in identifier:
              _pub= '{"uri": "", "name": "Regione Marche", "email": "", "url": "https://dati.regione.marche.it/", "type": "http://purl.org/adms/publishertype/RegionalAuthority"}'
            if 'r_emiro' in identifier:
              _pub= '{"uri": "", "name": "Regione Emilia-Romagna", "email": "", "url": "https://dati.emilia-romagna.it/", "type": "http://purl.org/adms/publishertype/RegionalAuthority"}'
            if 'r_toscan' in identifier:
              _pub= '{"uri": "", "name": "Regione Toscana", "email": "", "url": "https://dati.toscana.it/", "type": "http://purl.org/adms/publishertype/RegionalAuthority"}'
            if 'r_basili' in identifier:
              _pub= '{"uri": "", "name": "Regione Basilicata", "email": "", "url": "https://dati.regione.basilicata.it/", "type": "http://purl.org/adms/publishertype/RegionalAuthority"}'
            if 'm_lps' in identifier:
              _pub= '{"uri": "", "name": "Ministero del Lavoro", "email": "", "url": "http://dati.lavoro.gov.it/", "type": "http://purl.org/adms/publishertype/NationalAuthority"}'
            if 'c_l219' in identifier:
              _pub= '{"uri": "", "name": "Comune di Torino", "email": "", "url": "http://aperto.comune.torino.it/", "type": "http://purl.org/adms/publishertype/LocalAuthority"}'
            if 'cr_campa' in identifier:
              _pub= '{"uri": "", "name": "Consiglio Regionale della Campania", "email": "", "url": "http://opendata-crc.di.unisa.it/", "type": "http://purl.org/adms/publishertype/RegionalAuthority"}'
            if '00304260409' in identifier:
              _pub= '{"uri": "", "name": "Comune di Rimini", "email": "", "url": "https://opendata.comune.rimini.it/", "type": "http://purl.org/adms/publishertype/LocalAuthority"}'
            if 'c_a345' in identifier:
              _pub= '{"uri": "", "name": "OpenData Aquila", "email": "", "url": "https://ckan.opendatalaquila.it/", "type": "http://purl.org/adms/publishertype/LocalAuthority"}'
            if 'uds_ca' in identifier:
              _pub= '{"uri": "", "name": "Università di Cagliari - Dataset relativi al progetto TDM", "email": "", "url": "https://data.tdm-project.it/", "type": "http://purl.org/adms/publishertype/RegionalAuthority"}'
            if 'aci' in identifier:
              _pub= '{"uri": "", "name": "OpenData Aci", "email": "", "url": "http://lod.aci.it/", "type": "http://purl.org/adms/publishertype/NationalAuthority"}'
            if 'BDAP' in nameid:
              _pub= '{"uri": "", "name": "OpenData BDAP", "email": "", "url": "https://bdap-opendata.rgs.mef.gov.it/", "type": "http://purl.org/adms/publishertype/NationalAuthority"}'
            if 'C_D634' in identifier:
              _pub= '{"uri": "", "name": "Open data Comune di Flero", "email": "protocollo@comune.flero.bs.it", "url": "https://www.opendata.maggioli.cloud/organization/comune-di-flero/", "type": "http://purl.org/adms/publishertype/LocalAuthority"}'
            if 'r_lazio' in identifier:
              _pub= '{"uri": "", "name": "Regione Lazio", "email": "", "url": "http://dati.lazio.it/", "type": "http://purl.org/adms/publishertype/RegionalAuthority"}'
            if 'c_c621' in identifier:
              _pub= '{"uri": "", "name": "Open data Comune di Chiavari", "email": "info@comune.chiavari.ge.it", "url": "https://www.opendata.maggioli.cloud/organization/comune-di-chiavari/", "type": "http://purl.org/adms/publishertype/LocalAuthority"}'
            if 'c_i225' in identifier:
              _pub= '{"uri": "", "name": "Open data Comune di Santa Margherita Ligure", "email": "informatica@comunesml.it", "url": "https://www.opendata.maggioli.cloud/organization/comune-di-santa-margherita-ligure/", "type": "http://purl.org/adms/publishertype/LocalAuthority"}'
            if 'm_inf' in identifier:
             _pub= '{"uri": "", "name": "Ministero delle Infrastrutture e dei Trasporti", "email": "", "url": "https://dati.mit.gov.it/", "type": "http://purl.org/adms/publishertype/NationalAuthority"}'


            if _pub:
                pub = json.loads(_pub)

                #pub_uri = URIRef(pub.get('uri'))

                agent = BNode()
                g.add((agent, RDF.type, DCATAPIT.Agent))
                g.add((agent, RDF.type, FOAF.Agent))
                g.add((agent, DCT.identifier, Literal(identifier)))
                g.add((catalog_ref, DCT.publisher, agent))

                for src_key, _type, predicate, required in publisher_sources:
                    val = pub.get(src_key)
                    if src_key == 'type':
                       if dataset_dict.get('holder_identifier'):
                          if 'r_' in dataset_dict.get('holder_identifier') or 'p_' in dataset_dict.get('holder_identifier') :
                           val="http://purl.org/adms/publishertype/RegionalAuthority"
                          if 'm_' in dataset_dict.get('holder_identifier'):
                           val="http://purl.org/adms/publishertype/NationalAuthority"
                          if 'c_' in dataset_dict.get('holder_identifier'):
                           val="http://purl.org/adms/publishertype/LocalAuthority"
                          if 'inail' in dataset_dict.get('holder_identifier') or 'inps' in dataset_dict.get('holder_identifier') or 'agid' in dataset_dict.get('holder_identifier'):
                           val="http://purl.org/adms/publishertype/NationalAuthority"
                          if 'anac' in dataset_dict.get('holder_identifier') or 'ispra' in dataset_dict.get('holder_identifier') or 'pcm' in dataset_dict.get('holder_identifier'):
                           val="http://purl.org/adms/publishertype/NationalAuthority"                            
                    if src_key == 'url':
                        homepage=_get_from_extra('source_catalog_homepage')
                        if dataset_dict.get('holder_identifier'):
                         if 'aci' in dataset_dict.get('holder_identifier'):
                            homepage='http://lod.aci.it/'
                        if homepage is not None:
                         if homepage.endswith("/#"):
                           homepage=homepage.replace('/#','/')
                         if not homepage.endswith("/"):
                           homepage=homepage+'/'
                          #if homepage.endswith("/"):
                           # homepage=homepage+'#'
                         else:
                           homepage=homepage.replace('#','')
         #                  g.add((catalog_ref ,FOAF.homepage,URIRef(homepage)))
                         log.info('homepage foaf: %s',URIRef(homepage))
  #                      continue
                    if val is None and required:
                        raise ValueError("Value for %s (%s) is required" % (src_key, predicate))
                    elif val is None:
                        continue
                    g.add((agent, predicate, _type(val)))

        return catalog_ref


if __name__ == '__main__':

    parser = argparse.ArgumentParser(
        description='DCAT RDF - CKAN operations')
    parser.add_argument('mode',
                        default='consume',
                        help='''
Operation mode.
`consume` parses DCAT RDF graphs to CKAN dataset JSON objects.
`produce` serializes CKAN dataset JSON objects into DCAT RDF.
                        ''')
    parser.add_argument('file', nargs='?', type=argparse.FileType('r'),
                        default=sys.stdin,
                        help='Input file. If omitted will read from stdin')
    parser.add_argument('-f', '--format',
                        default='xml',
                        help='''Serialization format (as understood by rdflib)
                                eg: xml, n3 ... Defaults to \'xml\'.''')
    parser.add_argument('-P', '--pretty',
                        action='store_true',
                        help='Make the output more human readable')
    parser.add_argument('-p', '--profile', nargs='*',
                        action='store',
                        help='RDF Profiles to use, defaults to euro_dcat_ap_2')
    parser.add_argument('-m', '--compat-mode',
                        action='store_true',
                        help='Enable compatibility mode')

    parser.add_argument('-s', '--subcatalogs', action='store_true', dest='subcatalogs',
                        default=False,
                        help="Enable subcatalogs handling (dct:hasPart support)")
    args = parser.parse_args()

    contents = args.file.read()

    config.update({DCAT_EXPOSE_SUBCATALOGS: args.subcatalogs})
    # Workaround until the core translation function defaults to the Flask one
    from paste.registry import Registry
    from ckan.lib.cli import MockTranslator
    registry = Registry()
    registry.prepare()
    from pylons import translator
    registry.register(translator, MockTranslator())

    if args.mode == 'produce':
        serializer = RDFSerializer(profiles=args.profile,
                                   compatibility_mode=args.compat_mode)

        dataset = json.loads(contents)
        out = serializer.serialize_dataset(dataset, _format=args.format)
        print(out)
    else:
        parser = RDFParser(profiles=args.profile,
                           compatibility_mode=args.compat_mode)

        parser.parse(contents, _format=args.format)

        ckan_datasets = [d for d in parser.datasets()]

        indent = 4 if args.pretty else None
        print(json.dumps(ckan_datasets, indent=indent))
