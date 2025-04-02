import re
import json
import logging

from rdflib import BNode, Literal, URIRef
from rdflib.namespace import RDF, SKOS

import ckan.logic as logic
from ckan.common import config
from ckan.lib.i18n import get_lang, get_locales

from ckanext.dcat.profiles.base import (
    ADMS,
    DCAT,
    DCT,
    FOAF,
    LOCN,
    OWL,
    SCHEMA,
    TIME,
    VCARD,
    RDFProfile,
    RDFS,
)
from ckanext.dcat.utils import catalog_uri, dataset_uri, resource_uri

import ckanext.dcatapit.helpers as helpers
import ckanext.dcatapit.interfaces as interfaces
from ckanext.dcatapit import schema, validators
from ckanext.dcatapit.dcat.const import DCATAPIT, it_namespaces, THEME_BASE_URI, LANG_BASE_URI, FREQ_BASE_URI, \
    FORMAT_BASE_URI, GEO_BASE_URI, THEME_CONCEPTS, GEO_CONCEPTS, DEFAULT_THEME_KEY, DEFAULT_FORMAT_CODE, \
    DEFAULT_FREQ_CODE, LOCALISED_DICT_NAME_BASE, LOCALISED_DICT_NAME_RESOURCES, lang_mapping_ckan_to_voc, \
    lang_mapping_xmllang_to_ckan, lang_mapping_ckan_to_xmllang, format_mapping
from ckanext.dcatapit.model.subtheme import Subtheme
from ckanext.dcatapit.mapping import theme_name_to_uri, theme_aggrs_unpack, theme_names_to_uris, themes_parse_to_uris
from ckanext.dcatapit.schema import FIELD_THEMES_AGGREGATE

DEFAULT_LANG = config.get('ckan.locale_default', 'it')
HANDLED_LANGS = set(['it', 'fr', 'de', 'en'])
OFFERED_LANGS = set(get_locales()).intersection(HANDLED_LANGS)
PREF_LANDING= config.get('ckanext.dcat.base_uri')


log = logging.getLogger(__name__)


class ItalianDCATAPProfile(RDFProfile):
    '''
    An RDF profile for the Italian DCAT-AP recommendation for data portals
    It requires the European DCAT-AP profile (`euro_dcat_ap`)
    '''

    def parse_dataset(self, dataset_dict, dataset_ref):

        # check the dataset type
        if (dataset_ref, RDF.type, DCATAPIT.Dataset) not in self.g:
            # not a DCATAPIT dataset
            return dataset_dict

        # date info
        for predicate, key, logf in (
                (DCT.issued, 'issued', log.debug),
                (DCT.modified, 'modified', log.warn),
        ):
            value = self._object_value(dataset_ref, predicate)
            if value:
                self._remove_from_extra(dataset_dict, key)

                value = helpers.format(value, '%Y-%m-%d', 'date')
                dataset_dict[key] = value
            else:
                logf('No %s found for dataset "%s"', predicate, dataset_dict.get('title', '---'))

        # 0..1 predicates
        for predicate, key, logf in (
                (DCT.identifier, 'identifier', log.warn),
        ):
            value = self._object_value(dataset_ref, predicate)
            if value:
                if ' ' in value:
                  value=re.sub(r'[^a-zA-Z0-9:_]',r'',value)
                  value=re.sub('\W+','', value)
                  value = value.replace('//', '')
                if 'http' in value:
                      value=re.sub(r'[^a-zA-Z0-9:_]',r'',value)
                      value=re.sub('\W+','', value)
                      value = value.replace('//', '')
                self._remove_from_extra(dataset_dict, key)
                dataset_dict[key] = value
            else:
                logf('No %s found for dataset "%s"', predicate, dataset_dict.get('title', '---'))

        # 0..n predicates list
        for predicate, key, logf in (
                (DCT.isVersionOf, 'is_version_of', log.debug),
        ):
            valueList = self._object_value_list(dataset_ref, predicate)
            if valueList:
                self._remove_from_extra(dataset_dict, key)
                value = ','.join(valueList)
                dataset_dict[key] = value
            else:
                logf('No %s found for dataset "%s"', predicate, dataset_dict.get('title', '---'))

        alternate_identifiers = self.g.objects(dataset_ref, ADMS.identifier)
        extras_alt_identifiers = None
        extras_alt_idx = None

        for eidx, ex in enumerate(dataset_dict.get('extras') or []):
            if ex['key'] == 'alternate_identifier':
                extras_alt_identifiers = ex['value']
                extras_alt_idx = eidx
                break
        if extras_alt_identifiers is not None:
            dataset_dict['extras'].pop(extras_alt_idx)

        alt_ids = []

        for alt_id in alternate_identifiers:
            alternate_id = self._alternate_id(dataset_ref, alt_id)

            if alternate_id:
                alt_ids.append(alternate_id)
        if extras_alt_identifiers and alt_ids:
            log.warning('Two separate alternate identifers got for %s: %s and %s',
                        dataset_dict.get('id'),
                        alt_ids,
                        extras_alt_identifiers)
        # let's reuse
        if extras_alt_identifiers and not alt_ids:
            try:
                validators.dcatapit_alternate_identifier(extras_alt_identifiers, {})
                alt_ids = extras_alt_identifiers
            except validators.Invalid:
                pass

        dataset_dict['alternate_identifier'] = json.dumps(alt_ids)

        # conformsTo
        self._remove_from_extra(dataset_dict, 'conforms_to')
        conform_list = []
        for conforms_to in self.g.objects(dataset_ref, DCT.conformsTo):
            conform_list.append(self._conforms_to(conforms_to))
        if conform_list:
            dataset_dict['conforms_to'] = json.dumps(conform_list)
        else:
            log.debug('No DCT.conformsTo found for dataset "%s" , set DCATAPIT by default', dataset_dict.get('title', '---'))
            dataset_dict['conforms_to']=DCATAPIT

        # Temporal
        temporal_coverage = self._get_temporal_coverage(dataset_ref)
        if temporal_coverage:
            dataset_dict['temporal_coverage'] = json.dumps(temporal_coverage)

        # start, end = self._time_interval(dataset_ref, DCT.temporal)

        # URI 0..1
        for predicate, key, base_uri in (
                (DCT.accrualPeriodicity, 'frequency', FREQ_BASE_URI),
        ):
            valueRef = self._object_value(dataset_ref, predicate)
            if valueRef:
    #              if 'Dato' or 'disponibile' in valueRef:
       #              valueRef='UNKNOW'
                self._remove_from_extra(dataset_dict, key)
                value = self._strip_uri(valueRef, base_uri)
                dataset_dict[key] = value
            else:
                log.warning('No %s found for dataset "%s"', predicate, dataset_dict.get('title', '---'))

        # URI lists
        for predicate, key, base_uri in (
                (DCT.language, 'language', LANG_BASE_URI),
        ):
            self._remove_from_extra(dataset_dict, key)
            valueRefList = self._object_value_list(dataset_ref, predicate)
            valueList = [self._strip_uri(valueRef, base_uri) for valueRef in valueRefList]
            value = ','.join(valueList)
            if len(valueList) > 1:
                value = '{' + value + '}'
            dataset_dict[key] = value

        self._parse_themes(dataset_dict, dataset_ref)

        # Spatial
        spatial_tags = []
        geonames_url = None

        for spatial in self.g.objects(dataset_ref, DCT.spatial):
            for spatial_literal in self.g.objects(spatial, DCATAPIT.geographicalIdentifier):
                spatial_value = spatial_literal.value
                if GEO_BASE_URI in spatial_value:
                    spatial_tags.append(self._strip_uri(spatial_value, GEO_BASE_URI))
                else:
                    if geonames_url:
                        log.warning('GeoName URL is already set to %s, value %s will not be imported', geonames_url, spatial_value)
                    else:
                        geonames_url = spatial_value

        if len(spatial_tags) > 0:
            value = ','.join(spatial_tags)
            if len(spatial_tags) > 1:
                value = '{' + value + '}'
            dataset_dict['geographical_name'] = value

        if geonames_url:
            dataset_dict['geographical_geonames_url'] = geonames_url

        # Collect strings from multilang fields

        # { 'field_name': {'it': 'italian loc', 'de': 'german loc', ...}, ...}
        localized_dict = {}

        for key, predicate in (
                ('title', DCT.title),
                ('notes', DCT.description),
        ):
            self._collect_multilang_strings(dataset_dict, key, dataset_ref, predicate, localized_dict)

        # Agents
        for predicate, basekey in (
                (DCT.publisher, 'publisher'),
                (DCT.rightsHolder, 'holder'),
                # for backward compatibility only,
                # new format is handled with self._parse_creators() below
                (DCT.creator, 'creator'),
        ):
            agent_dict, agent_loc_dict = self._parse_agent(dataset_ref, predicate, basekey)
            for key, v in agent_dict.items():
                self._remove_from_extra(dataset_dict, key)
                dataset_dict[key] = v
            localized_dict.update(agent_loc_dict)

        creators = self._parse_creators(dataset_ref)

        # use data from old method to populate new format
        from_old = {}
        if dataset_dict.get('creator_name'):
            from_old['creator_name'] = {DEFAULT_LANG: dataset_dict['creator_name']}
        if dataset_dict.get('creator_identifier'):
            from_old['creator_identifier'] = dataset_dict['creator_identifier']

        # do not add old format if the same identifier is in new data
        # this will avoid duplicates in re-harvesting
        from_old_add = False
        if from_old:
            from_old_add = True
            if from_old.get('creator_identifier'):
                for cr in creators:
                    cid = cr.get('creator_identifier')
                    if cid is None:
                        continue
                    if cid == from_old['creator_identifier']:
                        from_old_add = False
                        break
        if from_old_add:
            creators.append(from_old)
        dataset_dict['creator'] = json.dumps(creators)

        # when all localized data have been parsed, check if there really any and add it to the dict
        if len(localized_dict) > 0:
            log.debug('Found multilang metadata')
            dataset_dict[LOCALISED_DICT_NAME_BASE] = localized_dict

        # Resources

        resources_loc_dict = {}

        # In ckan, the license is a dataset property, not resource's
        # We'll collect all of the resources' licenses, then we will postprocess them
        licenses = []  # contains tuples (url, name)

        for resource_dict in dataset_dict.get('resources', []):
            resource_uri = resource_dict['uri']
            if not resource_uri:
                log.warning('URI not defined for resource %s', resource_dict['name'])
                continue

            distribution = URIRef(resource_uri)
            if not (dataset_ref, DCAT.distribution, distribution) in self.g:
                log.warning('Distribution not found in dataset %s', resource_uri)
                continue

            # fix the CKAN resource's url set by the dcat extension
            resource_dict['url'] = (self._object_value(distribution, DCAT.downloadURL) or
                                    self._object_value(distribution, DCAT.accessURL))

            if 'csv' in resource_dict['url']: 
                 resource_dict.pop('format', None)
                 resource_dict['format']='CSV'
            if 'link' in resource_dict['url']:
                 resource_dict.pop('format', None)
                 resource_dict['format']='HTML_SIMPL'
            if 'ZIP' in resource_dict['url']:
                 resource_dict.pop('format', None)
                 resource_dict['format']='ZIP'
            if 'pdf' in resource_dict['url']:
                 resource_dict.pop('format', None)
                 resource_dict['format']='PDF'
            if 'PDF' in resource_dict['url']:
                 resource_dict.pop('format', None) 
                 resource_dict['format']='PDF'
            if 'zip' in resource_dict['url']:
                 resource_dict.pop('format', None) 
                 resource_dict['format']='ZIP'
            if 'wms' in resource_dict['url']:
                 resource_dict.pop('format', None) 
                 resource_dict['format']='WMS'
            if 'kml' in resource_dict['url']:
                 resource_dict.pop('format', None) 
                 resource_dict['format']='KML'
            if 'shp' in resource_dict['url']:
                 resource_dict.pop('format', None) 
                 resource_dict['format']='SHP'
            # URI 0..1
            for predicate, key, base_uri in (
                    (DCT['format'], 'format', FORMAT_BASE_URI),  # Format
            ):
                valueRef = self._object_value(distribution, predicate)
                if valueRef:
                    if 'csv' in resource_dict['url']:
                     resource_dict.pop('format', None)
                     resource_dict['format']='CSV'
                    if 'link' in resource_dict['url']:
                     resource_dict.pop('format', None)
                     resource_dict['format']='HTML_SIMPL'
                    if 'ZIP' in resource_dict['url']:
                     resource_dict.pop('format', None)
                     resource_dict['format']='ZIP'
                    if 'pdf' in resource_dict['url']:
                     resource_dict.pop('format', None)
                     resource_dict['format']='PDF'
                    if 'PDF' in resource_dict['url']:
                     resource_dict.pop('format', None)
                     resource_dict['format']='PDF'
                    value = self._strip_uri(valueRef, base_uri)
                    resource_dict[key] = value
                    log.debug('value in dct format %s',value)
                else:
                    log.warning('No %s found for resource "%s"::"%s"',
                                predicate,
                                dataset_dict.get('title', '---'),
                                resource_dict.get('name', '---'))

            # License
            setlic=0
            license = self._object(distribution, DCT.license)
            #applico patch alle licenze specifiche e per evitare duplicati in dct:license e patch ad hoc per Reg Campania
            if license:
                license=license.replace("https://w3id.org/italia/env/ld/catalog/license/ccby40","https://creativecommons.org/licenses/by/4.0/")
                license=license.replace("https://api.smartdatanet.it/metadataapi/api/license/CCBY","https://creativecommons.org/licenses/by/4.0/")
                license=license.replace("https://dati.veneto.it/lod/licenses/CC_BY-SA_-_Condivisione_con_la_stessa_licenza","https://creativecommons.org/licenses/by-sa/4.0/")
                license=license.replace("deed.it","")
                log.debug('sto sostituendo le licenze')
                license=license.replace("https://sparql-noipa.mef.gov.it/metadata/Licenza","https://creativecommons.org/licenses/by/4.0/")
                license=license.replace("https://w3id.org/italia/controlled-vocabulary/licences/A21:CCBY40","https://w3id.org/italia/controlled-vocabulary/licences/A21_CCBY40")
                license=license.replace("https://w3id.org/italia/controlled-vocabulary/licences/A11:CCO10","https://w3id.org/italia/controlled-vocabulary/licences/A11_CCO10")
                license=license.replace("https://w3id.org/italia/controlled-vocabulary/licences/A29_IODL20","https://www.dati.gov.it/content/italian-open-data-license-v20")
                license=license.replace("http://www.dati.gov.it/iodl/2.0/","https://www.dati.gov.it/content/italian-open-data-license-v20")
                license=license.replace("https://w3id.org/italia/controlled-vocabulary/licences/A21_CCBY40","https://creativecommons.org/licenses/by/4.0/")
                license=license.replace("http://www.opendefinition.org/licenses/cc-zero","https://w3id.org/italia/controlled-vocabulary/licences/A11_CCO10")
                license=license.replace("C1_Unknown","A21_CCBY40")
                license=license.replace("Licenza Sconosciuta","Creative Commons Attribuzione 4.0 Internazionale (CC BY 4.0)")
                license_uri = str(license)
                license_uri = license_uri.replace("https://w3id.org/italia/controlled-vocabulary/licences/C1_Unknown","https://w3id.org/italia/controlled-vocabulary/licences/A21_CCBY40")
                license_dct = self._object_value(license, DCT.type)
                license_names = self.g.objects(license, FOAF.name)  # may be either the title or the id
                license_version = self._object_value(license, FOAF.versionInfo)

                names = {}
                prefname = None
                for l in license_names:
                    if l.language:
                        names[l.language] = str(l)
                    else:
                        prefname = str(l)

                if license_uri is not None:
                          if 'https://creativecommons.org/licenses/by/4.0/' in license_uri:
                            # log.warning('1. Licenza Sconosciuta nel dataset, provo a settare CCBY')
                            prefname='Creative Commons Attribuzione 4.0 Internazionale (CC BY 4.0)'
                            license_dct='https://creativecommons.org/licenses/by/4.0/'
                            dataset_dict['license_id']=prefname
                            dataset_dict['license_title']=prefname
                            resource_dict['license_type'] = license_uri
                            resource_dict['license_id'] = prefname
                            setlic=1
                            license_uri=license_uri.replace("https://creativecommons.org/licenses/by/4.0/","https://w3id.org/italia/controlled-vocabulary/licences/A21_CCBY40")
                            license_uri=license_uri.replace("deed.it","")
                 #log.debug('prima de from_dcat %s %s %s',license_uri,license_dct,prefname)
                license_type = interfaces.get_license_from_dcat(license_uri,
                                                                license_dct,
                                                                prefname,
                                                                **names)

                log.debug('license_type from dcat %s',license_type)

                if license_version and str(license_version) != license_type.version:
                    log.warning(
                        'License version mismatch between %s and %s',
                        license_version,
                        license_type.version
                    )

                if license_type is not None:
                    resource_dict['license_type'] = license_type.uri
                else:
                    resource_dict['license_type'] = str(license)

                if dataset_dict.get('holder_identifier') is not None:
                  if 'r_campan' in dataset_dict.get('holder_identifier'):
                    license_type.document_uri = 'https://creativecommons.org/licenses/by/4.0/'
                    license_name = 'Creative Commons Attribuzione 4.0 Internazionale (CC BY 4.0)'
                  if 'r_lazio' in dataset_dict.get('holder_identifier'):
                    license_type.document_uri = 'https://www.dati.gov.it/content/italian-open-data-license-v20'
                    license_name = 'Italian Open Data License 2.0'
                try:
                    #log.info('License Name: %s', names)
                    license_name = names['it']
                except KeyError:
                    try:
                        license_name = names['en']
                    except KeyError:
                        log.warning('license_name non ESISTE')
                        if names.values():
                           #log.warning('names %s',names.values()[0])
                           license_name = names.values()[0]
                        else:
                           log.warning('license_type.default_name')
                           license_name = 'Creative Commons Attribuzione 4.0 Internazionale (CC BY 4.0)'
                           if license_type.document_uri is not None:
                             if 'publicdomain' in license_type.document_uri:
                               license_name='Creative Commons CC0 1.0 Universale - Public Domain Dedication (CC0 1.0)'
                           #license_type.default_name
                         #continue
                 #continue

                #if dataset_dict.get('holder_identifier') is not None:
                 #         if 'r_campan' in dataset_dict.get('holder_identifier'):
                  #            license_name = 'Creative Commons Attribuzione 4.0 Internazionale (CC BY 4.0)'

                if license_type.document_uri is not None:
                          if 'https://creativecommons.org/licenses/by/4.0/' in license_type.document_uri:
                            #log.warning('2. Licenza Sconosciuta nel dataset, provo a settare CCBY')
                            license_name='Creative Commons Attribuzione 4.0 Internazionale (CC BY 4.0)'
                            license_type.uri=license_type.uri.replace("C1_Unknown","A21_CCBY40")
                            dataset_dict['license_id']=license_name
                            dataset_dict['license_title']=license_name
                            resource_dict['license_type'] = license_type.uri
                            resource_dict['license_id'] = license_name
                            setlic=1
                log.info('Setting lincense %s %s %s', license_type.uri, license_name, license_type.document_uri) 
                licenses.append((license_type.uri, license_name, license_type.document_uri))
            else:
                log.warning('No license found for resource "%s"::"%s"',
                            dataset_dict.get('title', '---'),
                            resource_dict.get('name', '---'))

            # Multilang
            loc_dict = {}

            for key, predicate in (
                    ('name', DCT.title),
                    ('description', DCT.description),
            ):
                if resource_dict.get('name') is None:
                  resource_dict['name']="N/A"
                elif len(resource_dict.get('name'))<2:
                  resource_dict['name']="N/A"

                self._collect_multilang_strings(resource_dict, key, distribution, predicate, loc_dict)

            if len(loc_dict) > 0:
                log.debug('Found multilang metadata in resource %s', resource_dict['name'])
                resources_loc_dict[resource_uri] = loc_dict

        if len(resources_loc_dict) > 0:
            log.debug('Found multilang metadata in resources')
            dataset_dict[LOCALISED_DICT_NAME_RESOURCES] = resources_loc_dict

        # postprocess licenses
        # license_ids = {id for url,id in licenses}  # does not work in python 2.6
        license_ids = set()
        for lic_uri, id, doc_uri in licenses:
            license_ids.add(id)
         #log.info('prima del pop license_ids %s',license_ids)
        if len(license_ids) >= 1:
            if setlic==0:
             dataset_dict['license_id'] = license_ids.pop()
            # TODO Map to internally defined licenses
        else:
            log.warning(
                '%d licenses found for dataset "%s"',
                len(license_ids),
                dataset_dict.get('title', '---')
            )
            #dataset_dict['license_id'] = 'notspecified'

        return dataset_dict

    def _collect_multilang_strings(self, base_dict, key, subj, pred, loc_dict):
        '''
        Search for multilang Literals matching (subj, pred).
        - Literals not localized will be stored as source_dict[key] -- possibly replacing the value set by the EURO parser
        - Localized literals will be stored into target_dict[key][lang]
        '''

        for obj in self.g.objects(subj, pred):
            value = obj.value
            lang = obj.language
            if not lang:
                # force default value in dataset
                base_dict[key] = value
            else:
                # add localized string
                lang_dict = loc_dict.setdefault(key, {})
                lang_dict[lang_mapping_xmllang_to_ckan.get(lang)] = value
                # use default lang for localized only if we don't have
                # non-localized node
                if lang == DEFAULT_LANG and not base_dict.get(key):
                    base_dict[key] = value
            # use as fallback
            if not base_dict.get(key):
                base_dict[key] = value

    def _parse_themes(self, dataset, ref):
        # self._remove_from_extra(dataset, 'theme')
        themes = list(self.g.objects(ref, DCAT.theme))
        subthemes04 = list(self.g.objects(ref, DCATAPIT.subTheme)) # dcatapit v0.4 only
        subthemes10 = list(self.g.objects(ref, DCT.subject))

        out = []
        for t in themes:
            theme_name = str(t).split('/')[-1]
            row = {'theme': theme_name, 'subthemes': []}

            try:
                subthemes_for_theme = Subtheme.for_theme_values(theme_name)
            except ValueError as err:
                subthemes_for_theme = []

            for subtheme in set(subthemes04 + subthemes10):
                s = str(subtheme)
                if s in subthemes_for_theme:
                    row['subthemes'].append(s)
            out.append(row)

        dataset[FIELD_THEMES_AGGREGATE] = json.dumps(out)

    def _remove_from_extra(self, dataset_dict, key):

        #  search and replace
        for extra in dataset_dict.get('extras', []):
            if extra['key'] == key:
                dataset_dict['extras'].pop(dataset_dict['extras'].index(extra))
                return

    def _add_or_replace_extra(self, dataset_dict, key, value):

        #  search and replace
        for extra in dataset_dict.get('extras', []):
            if extra['key'] == key:
                extra['value'] = value
                return

        # add if not found
        dataset_dict['extras'].append({'key': key, 'value': value})

    def _set_temporal_coverage(self, graph, dataset_dict, dataset_ref):
        g = graph
        d = dataset_dict

        if d.get('holder_identifier'):
         if 'm_inf' not in d.get('holder_identifier'):
        # clean from dcat's data, to avoid duplicates
          for obj in g.objects(dataset_ref, DCT.temporal):
            self.log_remove('temporal', DCT.temporal)
            g.remove((dataset_ref, DCT.temporal, obj,))
            remove_unused_object(g, obj, "temporal")
        else:
          for obj in g.objects(dataset_ref, DCT.temporal):
            self.log_remove('temporal', DCT.temporal)
            g.remove((dataset_ref, DCT.temporal, obj,))
            remove_unused_object(g, obj, "temporal")


        temp_cov = dataset_dict.get('temporal_coverage')

        startemp = False

        if temp_cov:
            if len(temp_cov)>6:
              startemp = True
            temp_cov = json.loads(temp_cov)
        else:
            temp_cov = []

        if 'temporal_start' in d.get('extras'):
            for eidx, ex in enumerate(d.get('extras') or []):
             if ex['key'] == 'temporal_start':
                extras_alt_identifiers = ex['value']
                extras_alt_idx = eidx
                if len(extras_alt_identifiers)>4:
                   temporal_coverage_item = {'temporal_start': extras_alt_identifiers}
                   temp_cov.append(temporal_coverage_item)
                   
        if d.get('temporal_start'):
            temporal_coverage_item = {'temporal_start': d['temporal_start']}
            if d.get('temporal_end'):
                temporal_coverage_item.update({'temporal_end': d['temporal_end']})
            temp_cov.append(temporal_coverage_item)
        elif d.get('holder_identifier'):
         if 'm_inf' not in d.get('holder_identifier'): # non essendoci, setto dct:temporal con startDate il campo modified
          if startemp == False:
           if d.get('modified'):
             temporal_coverage_item = {'temporal_start': d.get('modified')}
             temp_cov.append(temporal_coverage_item)



            
        if not temp_cov:
            return

        for tc in temp_cov:
            start = tc['temporal_start']
            end = tc.get('temporal_end')
            temporal_extent = BNode()
            g.add((temporal_extent, RDF.type, DCT.PeriodOfTime))
            _added = False
            if start:
                _added = True
                self._add_date_triple(temporal_extent, DCATAPIT.startDate, start)
                self._add_date_triple(temporal_extent, DCAT.startDate, start)
            if end:
                _added = True
                self._add_date_triple(temporal_extent, DCATAPIT.endDate, end)
                self._add_date_triple(temporal_extent, DCAT.endDate, end)
            if _added:
                g.add((dataset_ref, DCT.temporal, temporal_extent))

    def _get_temporal_coverage(self, dataset_ref):
        pred = DCT.temporal
        out = []

        for interval in self.g.objects(dataset_ref, pred):
            # Fist try the schema.org way
            start = self._object_value(interval, DCATAPIT.startDate)
            end = self._object_value(interval, DCATAPIT.endDate)
            if start or end:
                out.append({'temporal_start': start,
                            'temporal_end': end})
                continue
            start_nodes = [t for t in self.g.objects(interval,
                                                     TIME.hasBeginning)]
            end_nodes = [t for t in self.g.objects(interval,
                                                   TIME.hasEnd)]
            if start_nodes:
                start = self._object_value(start_nodes[0],
                                           TIME.inXSDDateTime)
            if end_nodes:
                end = self._object_value(end_nodes[0],
                                         TIME.inXSDDateTime)

            if start or end:
                out.append({'temporal_start': start,
                            'temporal_end': end})

        return out

    def _conforms_to(self, conforms_id):
        ref_docs = [str(val) for val in self.g.objects(conforms_id, DCATAPIT.referenceDocumentation)]

        out = {'identifier': str(self.g.value(conforms_id, DCT.identifier)),
               'title': {},
               'description': {},
               'referenceDocumentation': ref_docs}
        if isinstance(conforms_id, (URIRef, Literal,)):
            out['uri'] = str(conforms_id)

        for t in self.g.objects(conforms_id, DCT.title):
            out['title'][t.language] = str(t)

        for t in self.g.objects(conforms_id, DCT.description):
            out['description'][t.language] = str(t)

        return out

    def _alternate_id(self, dataset_ref, alt_id):
        out = {}
        identifier = self.g.value(alt_id, SKOS.notation)

        if not identifier:
            return out

        out['identifier'] = str(identifier)

        basekey = 'creator'
        agent_dict, agent_loc_dict = self._parse_agent(alt_id, DCT.creator, basekey)
        agent = {}
        for k, v in agent_dict.items():
            new_k = 'agent_{}'.format(k[len(basekey) + 1:])
            agent[new_k] = v

        out['agent'] = agent
        if agent_loc_dict.get('creator_name'):
            out['agent']['agent_name'] = agent_loc_dict['creator_name']

        return out

    def _parse_creators(self, dataset_ref):
        out = []
        for cref in self.g.objects(dataset_ref, DCT.creator):
            creator = {}
            creator['creator_identifier'] = self._object_value(cref, DCT.identifier)
            creator_name = {}
            for obj in self.g.objects(cref, FOAF.name):
                if obj.language:
                    creator_name[str(obj.language)] = str(obj)
                else:
                    creator_name[DEFAULT_LANG] = str(obj)
            creator['creator_name'] = creator_name
            out.append(creator)
        return out

    def _parse_agent(self, subject, predicate, base_name):

        agent_dict = {}
        loc_dict = {}

        for agent in self.g.objects(subject, predicate):
            agent_dict[base_name + '_identifier'] = self._object_value(agent, DCT.identifier)
            self._collect_multilang_strings(agent_dict, base_name + '_name', agent, FOAF.name, loc_dict)

        return agent_dict, loc_dict

    def _strip_uri(self, value, base_uri):
        return value.replace(base_uri, '')

    def graph_from_dataset(self, dataset_dict, dataset_ref):

        title = dataset_dict.get('title')

        # extract fields from extras, just in case
        schema_fields = schema.get_custom_package_schema()
        for fdef in schema_fields:
            for eidx, ex in enumerate(dataset_dict.get('extras') or []):
                if ex['key'] == fdef['name']:
                    dataset_dict['extras'].pop(eidx)
                    dataset_dict[fdef['name']] = ex['value']
                    break

        g = self.g

        for prefix, namespace in it_namespaces.items():
            g.bind(prefix, namespace)

        # add a further type for the Dataset node
        g.add((dataset_ref, RDF.type, DCATAPIT.Dataset))

        # replace themes
        self._add_themes(dataset_ref,
                         self._get_dict_value(dataset_dict, FIELD_THEMES_AGGREGATE),
                         self._get_dict_value(dataset_dict, 'theme'))

        # replace languages
        value = self._get_dict_value(dataset_dict, 'language')
        if value:
            value=value.replace('"it"','ITA') 
            value=value.replace('[', '').replace(']', '')
            for lang in value.split(','):
                self.g.remove((dataset_ref, DCT.language, Literal(lang)))
                lang = lang.replace('{', '').replace('}', '')
                lang = lang.replace('["it"]', '')
                lang = lang.replace('it', 'ITA').replace('aA', 'A')
                lang = lang.replace('[', '').replace(']', '')
                lang = lang.replace('"it"', '')
                self.g.remove((dataset_ref, DCT.language, None))
                self.g.add((dataset_ref, DCT.language, URIRef(LANG_BASE_URI + lang)))
                # self._add_concept(LANG_CONCEPTS, lang)

        # add spatial (EU URI)
        value = self._get_dict_value(dataset_dict, 'geographical_name')
        if value:
            for gname in value.split(','):
                gname = gname.replace('{', '').replace('}', '')

                dct_location = BNode()
                self.g.add((dataset_ref, DCT.spatial, dct_location))

                self.g.add((dct_location, RDF['type'], DCT.Location))

                # Try and add a Concept from the spatial vocabulary
                if self._add_concept(GEO_CONCEPTS, gname):
                    self.g.add((dct_location, DCATAPIT.geographicalIdentifier, Literal(GEO_BASE_URI + gname)))

                    # geo concept is not really required, but may be a useful adding
                    self.g.add((dct_location, LOCN.geographicalName, URIRef(GEO_BASE_URI + gname)))
                else:
                    # The dataset field is not a controlled tag, let's create a Concept out of the label we have
                    concept = BNode()
                    self.g.add((concept, RDF['type'], SKOS.Concept))
                    self.g.add((concept, SKOS.prefLabel, Literal(gname)))
                    self.g.add((dct_location, LOCN.geographicalName, concept))

        # add spatial (GeoNames)
        value = self._get_dict_value(dataset_dict, 'geographical_geonames_url')
        if value:
            dct_location = BNode()
            self.g.add((dataset_ref, DCT.spatial, dct_location))

            self.g.add((dct_location, RDF['type'], DCT.Location))
            self.g.add((dct_location, DCATAPIT.geographicalIdentifier, Literal(value)))
        else:
            value='https://www.geonames.org/3175395'
            if dataset_dict.get('holder_identifier'):
              if 'r_abruzz' in dataset_dict.get('holder_identifier'):
               value='https://www.geonames.org/3183560'
              if 'regcal' in dataset_dict.get('holder_identifier'):
               value='https://www.geonames.org/2525468'
              if 'r_campan' in dataset_dict.get('holder_identifier'):
               value='https://www.geonames.org/3181042'
              if 'r_emiro' in dataset_dict.get('holder_identifier'):
               value='https://www.geonames.org/3177401'
              if 'r_friuve' in dataset_dict.get('holder_identifier'):
               value='https://www.geonames.org/3176525'
              if 'r_lazio' in dataset_dict.get('holder_identifier'):
               value='https://www.geonames.org/3174976'
              if 'r_liguri' in dataset_dict.get('holder_identifier'):
               value='https://www.geonames.org/3174725'
              if 'r_lombar' in dataset_dict.get('holder_identifier'):
               value='https://www.geonames.org/3174618'
              if 'r_marche' in dataset_dict.get('holder_identifier'):
               value='https://www.geonames.org/3174004'
              if 'r_molise' in dataset_dict.get('holder_identifier'):
               value='https://www.geonames.org/3173222'
              if 'r_piemon' in dataset_dict.get('holder_identifier'):
               value='https://www.geonames.org/3170831'
              if 'p_bz' in dataset_dict.get('holder_identifier'):
               value='https://www.geonames.org/3181912'
              if 'p_TN' in dataset_dict.get('holder_identifier'):
               value='https://www.geonames.org/3165241'
              if 'r_sicili' in dataset_dict.get('holder_identifier'):
               value='https://www.geonames.org/2523119'
              if 'r_basili' in dataset_dict.get('holder_identifier'):
               value='https://www.geonames.org/3182306'
              if 'r_toscan' in dataset_dict.get('holder_identifier'):
               value='https://www.geonames.org/3165361'
              if 'r_umbria' in dataset_dict.get('holder_identifier'):
               value='https://www.geonames.org/3165048'
              if 'r_vda' in dataset_dict.get('holder_identifier'):
               value='https://www.geonames.org/3164857'
              if 'r_veneto' in dataset_dict.get('holder_identifier'):
               value='https://www.geonames.org/3164604'
              if 'r_puglia' in dataset_dict.get('holder_identifier'):
               value='https://www.geonames.org/3169778'
              if 'r_sardeg' in dataset_dict.get('holder_identifier'):
               value='https://www.geonames.org/2523228'
            dct_location = BNode()
            self.g.add((dataset_ref, DCT.spatial, dct_location))
            self.g.add((dct_location, RDF['type'], DCT.Location))
            self.g.add((dct_location, DCATAPIT.geographicalIdentifier, Literal(value)))

        # replace periodicity
        self._remove_node(dataset_dict, dataset_ref, ('frequency', DCT.accrualPeriodicity, None, Literal))
        if dataset_dict.get('frequency'):
          if 'continuo' in dataset_dict.get('frequency'):
            dataset_dict['frequency']='OTHER'
          elif 'Dato non disponibile' in dataset_dict.get('frequency'):
            dataset_dict['frequency']='OTHER'
          elif 'mai' in dataset_dict.get('frequency'):
            dataset_dict['frequency']='NEVER'
          elif 'Annuale' in dataset_dict.get('frequency'):
            dataset_dict['frequency']='ANNUAL'
          elif 'Giornaliera' in dataset_dict.get('frequency'):
            dataset_dict['frequency']='DAILY'
          elif 'Sconosciuta' in dataset_dict.get('frequency'):
            dataset_dict.pop('frequency', None)
            dataset_dict['frequency']='UNKNOWN'
          elif 'Settimanale' in dataset_dict.get('frequency'):
            dataset_dict['frequency']='WEEKLY'
          elif 'annually' in dataset_dict.get('frequency'):
            dataset_dict['frequency']='ANNUAL'
          elif 'irregolare' in dataset_dict.get('frequency'):
            dataset_dict['frequency']='IRREG'
          elif 'mensile' in dataset_dict.get('frequency'):
            dataset_dict['frequency']='MONTHLY'
        else:
            dataset_dict['frequency']='UNKNOWN'
        
        self._add_uri_node(dataset_dict, dataset_ref, ('frequency', DCT.accrualPeriodicity, DEFAULT_FREQ_CODE, URIRef),
                           FREQ_BASE_URI)
        # self._add_concept(FREQ_CONCEPTS, dataset_dict.get('frequency', DEFAULT_VOCABULARY_KEY))

        landing_page_url=""
        # replace landing page
        if 'cciaan' in dataset_dict.get('holder_identifier'):
          landing_page_uri = dataset_dict.get('url')
          landing_page_url = dataset_dict.get('url')
          # landing_page_uri = 'https://opendata.marche.camcom.it'
          log.debug('url originale: %s',landing_page_uri)
          # self.g.add((dataset_ref, DCAT.landingPage, URIRef(landing_page_uri)))
        else:
         self._remove_node(dataset_dict, dataset_ref, ('url', DCAT.landingPage, None, URIRef))
         landing_page_uri = None
         if dataset_dict.get('name'):
            landing_page_uri = '{0}/dataset/{1}'.format(catalog_uri().rstrip('/'), dataset_dict['name'])
         else:
            landing_page_uri = dataset_uri(dataset_dict)  # TODO: preserve original URI if harvested

         noaddsl=0
        #   if 'cciaan' in dataset_dict.get('holder_identifier'):
          #    landing_page_uri = landing_page_url
         if 'KH5RHFCV' in dataset_dict.get('holder_identifier'):
            landing_page_uri=landing_page_uri.replace(PREF_LANDING,"https://dati-ustat.mur.gov.it/")
         if 'cmna' in dataset_dict.get('holder_identifier'):
            landing_page_uri=landing_page_uri.replace(PREF_LANDING,"https://dati.cittametropolitana.na.it/")
         if '00514490010' in dataset_dict.get('holder_identifier'):
            landing_page_uri=landing_page_uri.replace(PREF_LANDING,"http://aperto.comune.torino.it/")
         if 'r_lazio' in dataset_dict.get('holder_identifier'):
            landing_page_uri = dataset_uri(dataset_dict)
            landing_page_uri=landing_page_uri.replace(PREF_LANDING,"http://dati.lazio.it/catalog/")
         if 'r_basili' in dataset_dict.get('holder_identifier'):
            landing_page_uri = dataset_uri(dataset_dict)
            landing_page_uri=landing_page_uri.replace(PREF_LANDING,"https://dati.regione.basilicata.it/catalog/")
         if 'c_a944' in dataset_dict.get('holder_identifier'):
            landing_page_uri = dataset_uri(dataset_dict)
         if 'r_friuve' in dataset_dict.get('holder_identifier'):
            landing_page_uri = dataset_uri(dataset_dict)
         if 'c_d969' in dataset_dict.get('holder_identifier'):
            landing_page_uri = dataset_uri(dataset_dict)
            landing_page_uri=landing_page_uri.replace(PREF_LANDING,"https://dati.comune.genova.it")
         if 'aci' in dataset_dict.get('holder_identifier'):
            landing_page_uri=landing_page_uri.replace(PREF_LANDING,"http://lod.aci.it/")
         if 'r_marche' in dataset_dict.get('holder_identifier'):
            landing_page_uri=landing_page_uri.replace(PREF_LANDING,"https://dati.regione.marche.it/")
         if 'r_emiro' in dataset_dict.get('holder_identifier'):
            landing_page_uri=landing_page_uri.replace(PREF_LANDING,"https://dati.emilia-romagna.it/")
         if 'r_toscan' in dataset_dict.get('holder_identifier'):
            landing_page_uri=landing_page_uri.replace(PREF_LANDING,"https://dati.toscana.it/")
         if 'p_TN' in dataset_dict.get('holder_identifier'):
            landing_page_uri = dataset_uri(dataset_dict)
            landing_page_uri=landing_page_uri.replace(PREF_LANDING,"http://dati.trentino.it")
         if 'r_veneto' in dataset_dict.get('holder_identifier'):
            landing_page_uri = dataset_uri(dataset_dict)
            landing_page_uri=landing_page_uri.replace(PREF_LANDING,"https://dati.veneto.it")
         if 'c_g273' in dataset_dict.get('holder_identifier'):
            landing_page_uri = dataset_uri(dataset_dict)
            landing_page_uri=landing_page_uri.replace(PREF_LANDING,"https://opendata.comune.palermo.it")
         if 'anac' in dataset_dict.get('holder_identifier'):
            landing_page_uri = dataset_uri(dataset_dict)
            landing_page_uri=landing_page_uri.replace(PREF_LANDING,"https://dati.anticorruzione.it/opendata")
         if 'c_f052' in dataset_dict.get('holder_identifier'):
            landing_page_uri = dataset_uri(dataset_dict)
            landing_page_uri=landing_page_uri.replace(PREF_LANDING,"http://dati.comune.matera.it")
         if 'c_f158' in dataset_dict.get('holder_identifier'):
            landing_page_uri = dataset_uri(dataset_dict)
            landing_page_uri=landing_page_uri.replace(PREF_LANDING,"https://opendata.comune.messina.it")
         if 'c_f205' in dataset_dict.get('holder_identifier'):
            landing_page_uri = dataset_uri(dataset_dict)
            landing_page_uri=landing_page_uri.replace(PREF_LANDING,"https://dati.comune.milano.it")
         if 'c_e506' in dataset_dict.get('holder_identifier'):
            landing_page_uri = dataset_uri(dataset_dict)
         if 'regcal' in dataset_dict.get('holder_identifier'):
            landing_page_uri = dataset_uri(dataset_dict)
         if 'p_bz' in dataset_dict.get('holder_identifier'):
            landing_page_uri = dataset_uri(dataset_dict)
         if 'cvtiap' in dataset_dict.get('holder_identifier'):
            landing_page_uri = dataset_uri(dataset_dict)
         if '04155080270' in dataset_dict.get('holder_identifier'):
            landing_page_uri = dataset_uri(dataset_dict)
         if 'm_bac' in dataset_dict.get('holder_identifier'):
            landing_page_uri = 'http://dati.san.beniculturali.it/dataset'
         if 'M_ef' in dataset_dict.get('holder_identifier'):
            landing_page_uri = dataset_uri(dataset_dict)
            landing_page_uri=landing_page_uri.replace(PREF_LANDING,"https://sparql-noipa.mef.gov.it")
            noaddsl=1
         if 'MEF-BDAP' in dataset_dict.get('holder_name'):
            landing_page_uri = dataset_uri(dataset_dict)
            # landing_page_uri=landing_page_uri.replace(PREF_LANDING,"https://sparql-noipa.mef.gov.it")
            noaddsl=1
         if 'm_pi' in dataset_dict.get('holder_identifier'):
            landing_page_uri = dataset_uri(dataset_dict)
            landing_page_uri=landing_page_uri.replace(PREF_LANDING,"http://dati.istruzione.it")
            noaddsl=1
         if 'r_campan' in dataset_dict.get('holder_identifier'):
            landing_page_uri = dataset_uri(dataset_dict)
            landing_page_uri=landing_page_uri.replace(PREF_LANDING,"https://dati.regione.campania.it")
            noaddsl=0
         if 'uni_ba' in dataset_dict.get('holder_identifier'):
            landing_page_uri = dataset_uri(dataset_dict)
            landing_page_uri=landing_page_uri.replace(PREF_LANDING,"https://opendata.uniba.it")
            noaddsl=1
         if 'uni_bo' in dataset_dict.get('holder_identifier'):
            landing_page_uri = dataset_uri(dataset_dict)
            landing_page_uri=landing_page_uri.replace(PREF_LANDING,"https://dati.unibo.it")
            noaddsl=1
         if 'r_sicili' in dataset_dict.get('holder_identifier'):
            landing_page_uri = dataset_uri(dataset_dict)
            landing_page_uri=landing_page_uri.replace(PREF_LANDING,"https://dati.regione.sicilia.it")
            noaddsl=1
         if 'c_h501' in dataset_dict.get('holder_identifier'):
            landing_page_uri = dataset_uri(dataset_dict)
            landing_page_uri=landing_page_uri.replace(PREF_LANDING,"https://dati.comune.roma.it")
            noaddsl=1
         if 'cr_campa' in dataset_dict.get('holder_identifier'):
            self._remove_node(dataset_dict, dataset_ref, ('url', DCAT.landingPage, None, URIRef))
            landing_page_uri = '{0}/dataset/{1}'.format(catalog_uri().rstrip('/'), dataset_dict['name'])
            landing_page_uri=landing_page_uri.replace(PREF_LANDING,"http://opendata-crc.di.unisa.it/")
            landing_page_uri=landing_page_uri.replace("CONSIGLIO%20REGIONE%20CAMPANIA","")
            landing_page_uri=landing_page_uri.replace("CONSIGLIO REGIONE CAMPANIA","")
            landing_page_uri=landing_page_uri.replace("Consiglio%20Regionale%20Campania","")
            landing_page_uri=landing_page_uri.replace("Consiglio Regionale Campania","")
            noaddsl=1
         if '00304260409' in dataset_dict.get('holder_identifier'):
            landing_page_uri = dataset_uri(dataset_dict)
            landing_page_uri=landing_page_uri.replace(PREF_LANDING,"https://opendata.comune.rimini.it/")
            noaddsl=1
         if 'm_sa' in dataset_dict.get('holder_identifier'):
            landing_page_uri = dataset_uri(dataset_dict)
            landing_page_uri=landing_page_uri.replace(PREF_LANDING,"http://www.dati.salute.gov.it")
            noaddsl=1
         if 'c_a345' in dataset_dict.get('holder_identifier'):
            landing_page_uri = dataset_uri(dataset_dict)
            landing_page_uri=landing_page_uri.replace(PREF_LANDING,"https://ckan.opendatalaquila.it")
            noaddsl=1
         if 'cci' in dataset_dict.get('holder_identifier'):
            landing_page_uri = dataset_uri(dataset_dict)
            landing_page_uri=landing_page_uri.replace(PREF_LANDING,"https://www.mistralportal.it")
            noaddsl=1
         if 'agid' in dataset_dict.get('holder_identifier'):
            landing_page_uri = dataset_uri(dataset_dict)
            landing_page_uri=landing_page_uri.replace(PREF_LANDING,"https://indicepa.gov.it")
            noaddsl=1
         if 'consip' in dataset_dict.get('holder_identifier'):
            landing_page_uri = dataset_uri(dataset_dict)
            landing_page_uri=landing_page_uri.replace(PREF_LANDING,"https://dati.consip.it")
            noaddsl=1
         if 'r_lomb' in dataset_dict.get('holder_identifier'):
            landing_page_uri = dataset_uri(dataset_dict)
            landing_page_uri=landing_page_uri.replace(PREF_LANDING,"https://www.dati.lombardia.it")
            noaddsl=1
         if 'uds_ca' in dataset_dict.get('holder_identifier'):
            landing_page_uri = dataset_uri(dataset_dict)
            landing_page_uri=landing_page_uri.replace(PREF_LANDING,"http://data.tdm-project.it")
            noaddsl=1
         if 'PCM - Dipartimento della Protezione Civile' in dataset_dict.get('holder_name'):
            landing_page_uri = dataset_uri(dataset_dict)
            landing_page_uri=landing_page_uri.replace(PREF_LANDING,"https://github.com/pcm-dpc")
         if 'r_puglia' in dataset_dict.get('holder_identifier'):
            landing_page_uri = dataset_uri(dataset_dict)
            landing_page_uri=landing_page_uri.replace(PREF_LANDING,"https://dati.puglia.it")
            noaddsl=1 
         if 'ispra_rm' in dataset_dict.get('holder_identifier'):
            landing_page_uri = dataset_uri(dataset_dict)
            noaddsl=1
         if 'm_lps' in dataset_dict.get('holder_identifier'):
            landing_page_uri = dataset_uri(dataset_dict)
            noaddsl=1  
         if 'm_inf' in dataset_dict.get('holder_identifier'):
            landing_page_uri = dataset_uri(dataset_dict)
            landing_page_uri=landing_page_uri.replace(PREF_LANDING,"https://dati.mit.gov.it")
            noaddsl=1 
         if 'agcm_' in dataset_dict.get('holder_identifier'):
            landing_page_uri = dataset_uri(dataset_dict)
            noaddsl=0
            landing_page_uri=landing_page_uri.replace("/catalog","")
         if noaddsl==0:
           landing_page_uri += '/'
             
         for extra in dataset_dict.get('extras', []):
             if extra['key'] == 'landingpage':
                landing_page_uri = extra['value']
                 
         landing_page_uri = landing_page_uri.replace('documento:pubblico','documento_pubblico')  

         landing_page_uri_f=""
         if landing_page_uri.endswith("/"):
            landing_page_uri_f = landing_page_uri[:-1]
         else:
            landing_page_uri_f = landing_page_uri

         landing_page_uri_f += '#'

#         self.g.add((dataset_ref, DCAT.landingPage, URIRef(landing_page_uri_f)))

         if 'http' in landing_page_uri:
          self.g.add((dataset_ref, DCAT.landingPage, URIRef(landing_page_uri_f)))

        # conformsTo
        self.g.remove((dataset_ref, DCT.conformsTo, None))
        value = self._get_dict_value(dataset_dict, 'conforms_to')
        if value:
            try:
                conforms_to = json.loads(value)
            except (TypeError, ValueError):
                log.warning('Cannot deserialize DCATAPIT:conformsTo value: %s', value)
                conforms_to = []

            for item in conforms_to:
                standard = URIRef(item['uri']) if item.get('uri') else BNode()

                self.g.add((dataset_ref, DCT.conformsTo, standard))
                self.g.add((standard, RDF['type'], DCT.Standard))
                self.g.add((standard, RDF['type'], DCATAPIT.Standard))

                self.g.add((standard, DCT.identifier, Literal(item['identifier'])))

                for lang, val in (item.get('title') or {}).items():
                    if lang in OFFERED_LANGS:
                        if 'dcatapit' in item['identifier']:
                         self.g.add((standard, DCT.title, Literal('DCAT-AP_IT')))
                        else:
                         self.g.add((standard, DCT.title, Literal(val, lang=lang_mapping_ckan_to_xmllang.get(lang, lang))))

                for lang, val in (item.get('description') or {}).items():
                    if lang in OFFERED_LANGS:
                       if 'dcatapit' in item['identifier']:
                        self.g.add((standard, DCT.description, Literal('Profilo metadatazione DCAT-AP_IT')))
                       else:
                        self.g.add((standard, DCT.description, Literal(val, lang=lang_mapping_ckan_to_xmllang.get(lang, lang))))

                for reference_document in (item.get('referenceDocumentation') or []):
                   if 'dcatapit' in item['identifier']:
                    self.g.add((standard, DCATAPIT.referenceDocumentation, URIRef('https://www.dati.gov.it/onto/dcatapit')))
                   else:
                    self.g.add((standard, DCATAPIT.referenceDocumentation, URIRef(reference_document)))

        # ADMS:identifier alternative identifiers
        self.g.remove((dataset_ref, ADMS.identifier, None,))

        # alternate_identifier sometimes resides in extras

        try:
            if dataset_dict.get('identifier'):
             if ' ' in dataset_dict.get('identifier'):
              dataset_dict["identifier"]=re.sub(r'[^a-zA-Z0-9:_]',r'',dataset_dict["identifier"])
              dataset_dict["identifier"]=re.sub('\W+','', dataset_dict["identifier"])
              
            dataset_dict['alternate_identifier']=dataset_dict['alternate_identifier'].replace('[','').replace(']','')
            dataset_dict['alternate_identifier']=dataset_dict['alternate_identifier'].replace('["','').replace('"]','')
            dataset_dict['alternate_identifier']=dataset_dict['alternate_identifier'].replace('"','').replace('"','')
            dataset_dict['alternate_identifier']=dataset_dict['alternate_identifier'].replace('\"','').replace('\"','')
            alt_ids = json.loads(dataset_dict['alternate_identifier'])
        except (KeyError, TypeError, ValueError):
            alt_ids = []

        for alt_identifier in alt_ids:
            node = BNode()
            self.g.add((dataset_ref, ADMS.identifier, node))

            identifier = Literal(alt_identifier['identifier'])
            self.g.add((node, SKOS.notation, identifier))

            if alt_identifier.get('agent'):
                adata = alt_identifier['agent']
                agent = BNode()

                self.g.add((agent, RDF['type'], DCATAPIT.Agent))
                self.g.add((agent, RDF['type'], FOAF.Agent))
                self.g.add((node, DCT.creator, agent))
                if adata.get('agent_name'):
                    for alang, aname in adata['agent_name'].items():
                        if alang in OFFERED_LANGS:
                            self.g.add((agent, FOAF.name, Literal(aname, lang=lang_mapping_ckan_to_xmllang.get(alang, alang))))

                if adata.get('agent_identifier'):
                    self.g.add((agent, DCT.identifier, Literal(adata['agent_identifier'])))

        self._set_temporal_coverage(self.g, dataset_dict, dataset_ref)

        # publisher

        # DCAT by default creates this node
        # <dct:publisher>
        #   <foaf:Organization rdf:about="http://10.10.100.75/organization/55535226-f82a-4cf7-903a-3e10afeaa79a">
        #     <foaf:name>orga2_test</foaf:name>
        #   </foaf:Organization>
        # </dct:publisher>

        # remove the publisher created by the dcat plugin, bc we are going to encode it in a different way
        for s, p, o in g.triples((dataset_ref, DCT.publisher, None)):
            self.log_remove('publisher', DCT.publisher)
            g.remove((s, p, o))
            remove_unused_object(g, o, "publisher")  # if the publisher node is not used elsewhere, remove it
        # il publisher del dataset non esiste. impongo il nome di org e id di holder_identifier
        if dataset_dict.get('publisher_name') is None:
           if dataset_dict.get('holder_name'):
             dataset_dict['publisher_name'] = dataset_dict['holder_name']
           if dataset_dict.get('holder_identifier'):
             dataset_dict['publisher_identifier'] = dataset_dict.get('holder_identifier')
        else:
            if len(dataset_dict.get('publisher_name'))<1 or 'N/A' in dataset_dict.get('publisher_name'):
             if dataset_dict.get('holder_name'):
              dataset_dict.pop('publisher_name', None)
              dataset_dict['publisher_name'] = dataset_dict['holder_name']
             if dataset_dict.get('holder_identifier'):
              dataset_dict['publisher_identifier'] = dataset_dict.get('holder_identifier')  
              
        publisher_ref = self._add_agent(dataset_dict, dataset_ref, 'publisher', DCT.publisher, use_default_lang=True)

        # Autore : Agent
        self._add_creators(dataset_dict, dataset_ref)

        # Point of Contact

        # <dcat:contactPoint rdf:resource="http://dati.gov.it/resource/PuntoContatto/contactPointRegione_r_liguri"/>

        # <!-- http://dati.gov.it/resource/PuntoContatto/contactPointRegione_r_liguri -->
        # <dcatapit:Organization rdf:about="http://dati.gov.it/resource/PuntoContatto/contactPointRegione_r_liguri">
        #    <rdf:type rdf:resource="&vcard;Kind"/>
        #    <rdf:type rdf:resource="&vcard;Organization"/>
        #    <vcard:hasEmail rdf:resource="mailto:infoter@regione.liguria.it"/>
        #    <vcard:fn>Regione Liguria - Sportello Cartografico</vcard:fn>
        # </dcatapit:Organization>

        # TODO: preserve original info if harvested

        # retrieve the contactPoint added by the euro serializer
        euro_poc = g.value(subject=dataset_ref, predicate=DCAT.contactPoint, object=None, any=False)

        # euro poc has this format:
        # <dcat:contactPoint>
        #    <vcard:Organization rdf:nodeID="Nfcd06f452bcd41f48f33c45b0c95979e">
        #       <vcard:fn>THE ORGANIZATION NAME</vcard:fn>
        #       <vcard:hasEmail>THE ORGANIZATION EMAIL</vcard:hasEmail>
        #    </vcard:Organization>
        # </dcat:contactPoint>

        if euro_poc:
            g.remove((dataset_ref, DCAT.contactPoint, euro_poc))
            self.log_remove('contactPoint', DCAT.contactPoint)
            remove_unused_object(g, euro_poc, "contactPoint")

        org_id = dataset_dict.get('owner_org')

        # get orga info
        org_show = logic.get_action('organization_show')

        org_dict = {}
        if org_id:
            try:
                org_dict = org_show({'ignore_auth': True},
                                    {'id': org_id,
                                     'include_datasets': False,
                                     'include_tags': False,
                                     'include_users': False,
                                     'include_groups': False,
                                     'include_extras': True,
                                     'include_followers': False}
                                    )
            except Exception as err:
                log.warning('Cannot get org for %s: %s', org_id, err, exc_info=err)

        org_uri = organization_uri(org_dict)

        poc = URIRef(org_uri)
        g.add((dataset_ref, DCAT.contactPoint, poc))
        g.add((poc, RDF.type, DCATAPIT.Organization))
        g.add((poc, RDF.type, VCARD.Kind))
        g.add((poc, RDF.type, VCARD.Organization))

        g.add((poc, VCARD.fn, Literal(org_dict.get('display_name'))))

        if 'email' in org_dict.keys():  # this element is mandatory for dcatapit, but it may not have been filled for imported datasets
            g.add((poc, VCARD.hasEmail, URIRef('mailto:'+org_dict.get('email'))))
        if 'telephone' in org_dict.keys():
            g.add((poc, VCARD.hasTelephone, Literal(org_dict.get('telephone'))))
        if 'site' in org_dict.keys():
            g.add((poc, VCARD.hasURL, URIRef(org_dict.get('site'))))

        # Rights holder : Agent,
        # holder_ref keeps graph reference to holder subject
        # holder_use_dataset is a flag if holder info is taken from dataset (or organization)
        holder_ref, holder_use_dataset = self._add_right_holder(dataset_dict, org_dict, dataset_ref)

        # Multilingual
        # Add localized entries in dataset
        # TODO: should we remove the non-localized nodes?

        loc_dict = interfaces.get_for_package(dataset_dict['id'])
        #  The multilang fields
        loc_package_mapping = {
            'title': (dataset_ref, DCT.title),
            'notes': (dataset_ref, DCT.description),
            'publisher_name': (publisher_ref, FOAF.name),
        }

        dataset_is_local = dataset_dict.get('dataset_is_local')
        if dataset_is_local:
            _org_name = interfaces.get_for_group_or_organization(dataset_dict['owner_org'])
            if _org_name.get('title'):
                loc_dict['holder_name'] = _org_name['title']

        # rights holder should use special trick to avoid duplicated foaf:name entries
        if holder_use_dataset and holder_ref:
            loc_package_mapping['holder_name'] = (holder_ref, FOAF.name, dataset_is_local)

        if loc_dict.get('publisher_name'):
          if len(loc_dict.get('publisher_name'))<2:
             loc_dict.pop('publisher_name',None)
             log.debug('sto facendo pop pub_name perchè empty')

        self._add_multilang_values(loc_dict, loc_package_mapping)

        if not holder_use_dataset and holder_ref:
            loc_dict = interfaces.get_for_group_or_organization(org_dict['id'])
            loc_package_mapping = {'name': (holder_ref, FOAF.name)}
            self._add_multilang_values(loc_dict, loc_package_mapping)

        # Resources
        for resource_dict in dataset_dict.get('resources', []):
            #log.debug('Debug formato %s',resource_dict.get('url'))
            if 'csv' in resource_dict.get('url'):
                 resource_dict.pop('format', None)
                 resource_dict['format']=FORMAT_BASE_URI+'CSV'
                 resource_dict['distribution_format']='CSV'
            if 'link' in resource_dict.get('url'):
                 resource_dict.pop('format', None)
                 resource_dict['format']=FORMAT_BASE_URI+'HTML_SIMPL'
                 resource_dict['distribution_format']='HTML_SIMPL'
            if 'ZIP' in resource_dict.get('url'):
                 resource_dict.pop('format', None)
                 resource_dict['format']=FORMAT_BASE_URI+'ZIP'
                 resource_dict['distribution_format']='ZIP'
            if 'pdf' in resource_dict.get('url'):
                 resource_dict.pop('format', None)
                 resource_dict['format']=FORMAT_BASE_URI+'PDF'
                 resource_dict['distribution_format']='PDF'
            if 'PDF' in resource_dict.get('url'):
                 resource_dict.pop('format', None)
                 resource_dict['format']=FORMAT_BASE_URI+'PDF'
                 resource_dict['distribution_format']='PDF'
            guessed_format = guess_format(resource_dict)
            if guessed_format:
             if guessed_format.casefold() in resource_dict.get('url').casefold():
                 resource_dict.pop('format', None)
                 resource_dict.pop('distribution_format', None)
                 resource_dict['format']=FORMAT_BASE_URI+guessed_format
                 resource_dict['distribution_format']=guessed_format

            distribution = URIRef(resource_uri(resource_dict))  # TODO: preserve original info if harvested
            
            if 'cmna' in dataset_dict.get('holder_identifier'):
              distribution = distribution.replace(PREF_LANDING,"https://dati.cittametropolitana.na.it/")
              distribution=URIRef(distribution)
            if '00514490010' in dataset_dict.get('holder_identifier'):
              distribution = distribution.replace(PREF_LANDING,"http://aperto.comune.torino.it/")
              distribution=URIRef(distribution)
            if 'r_marche' in dataset_dict.get('holder_identifier'):
              distribution = distribution.replace(PREF_LANDING,"https://dati.regione.marche.it/")
              distribution=URIRef(distribution)
                #  log.info('resource_distribution_it %s',distribution)
            if 'r_emiro' in dataset_dict.get('holder_identifier'):
              distribution = distribution.replace("dati.comune.fe.it","https://dati.comune.fe.it")
              distribution = distribution.replace(PREF_LANDING,"https://dati.emilia-romagna.it/")
              distribution=URIRef(distribution)
                 #  log.info('resource_distribution_it %s',distribution)
            if 'm_it' in dataset_dict.get('holder_identifier'):
              distribution = distribution.replace(PREF_LANDING,"https://www.interno.gov.it/")
              distribution=URIRef(distribution)
            if 'r_toscan' in dataset_dict.get('holder_identifier'):
              distribution = distribution.replace(PREF_LANDING,"https://dati.toscana.it/")
              distribution=URIRef(distribution)
            if 'r_basili' in dataset_dict.get('holder_identifier'):
              distribution = distribution.replace(PREF_LANDING,"https://dati.regione.basilicata.it/catalog/")
              distribution=URIRef(distribution)
            if 'r_lazio' in dataset_dict.get('holder_identifier'):
              distribution = distribution.replace(PREF_LANDING,"http://dati.lazio.it/catalog/")
              distribution=URIRef(distribution)
            if 'm_lps' in dataset_dict.get('holder_identifier'):
              distribution = distribution.replace(PREF_LANDING,"http://dati.lavoro.gov.it/")
              distribution=URIRef(distribution)
            if 'cr_campa' in dataset_dict.get('holder_identifier'):
              distribution = distribution.replace(PREF_LANDING,"http://opendata-crc.di.unisa.it/")
              distribution=URIRef(distribution)
            if '00304260409' in dataset_dict.get('holder_identifier'):
              distribution = distribution.replace(PREF_LANDING,"https://opendata.comune.rimini.it/")
              distribution=URIRef(distribution)
            if 'm_inf' in dataset_dict.get('holder_identifier'):
              distribution = distribution.replace(PREF_LANDING,"https://dati.mit.gov.it")
              distribution=URIRef(distribution)
            if 'c_a345' in dataset_dict.get('holder_identifier'):
              distribution = distribution.replace(PREF_LANDING,"ckan.opendatalaquila.it")
              distribution=URIRef(distribution)
            if 'uds_ca' in dataset_dict.get('holder_identifier'):
              distribution = distribution.replace(PREF_LANDING,"data.tdm-project.it")
              distribution=URIRef(distribution)
            if 'aci' in dataset_dict.get('holder_identifier'):
              distribution = distribution.replace(PREF_LANDING,"http://lod.aci.it/")
              distribution=URIRef(distribution)


            # Add the DCATAPIT type
            g.add((distribution, RDF.type, DCATAPIT.Distribution))

            # format             
            self._remove_node(resource_dict, distribution, ('format', DCT['format'], None, Literal))
            # log.debug('prima del guessed_format ma dopo il remove')
            if not self._add_uri_node(resource_dict, distribution, ('distribution_format', DCT['format'], None, URIRef),
                                      FORMAT_BASE_URI):
                guessed_format = guess_format(resource_dict)
                if guessed_format:
                    log.debug('SONO IN GUESSED FORMAT')
                    if 'CSV' in resource_dict['url']:
                       guessed_format='CSV'
                    if 'ZIP' in resource_dict['url']:
                       guessed_format='ZIP'
                    if 'link' in resource_dict['url']:
                       guessed_format='HTML_SIMPL'   
                    if 'pdf' in resource_dict['url']:
                       guessed_format='PDF'
                    if 'PDF' in resource_dict['url']:
                       guessed_format='PDF'
                    if 'wms' in resource_dict['url']:
                       guessed_format='WMS'
                    if 'kml' in resource_dict['url']:
                       guessed_format='KML'
                    if 'shp' in resource_dict['url']:
                       guessed_format='SHP'
                    if 'wfs' in resource_dict['url']:
                       guessed_format='WFS'
                    if 'zip' in resource_dict['url']:
                       guessed_format='ZIP'           
                       
                    self.g.add((distribution, DCT['format'], URIRef(FORMAT_BASE_URI + guessed_format)))
                else:
                    log.warning('No format for resource: %s / %s', dataset_dict.get('title', 'N/A'), resource_dict.get('description', 'N/A'))
                    self.g.add((distribution, DCT['format'], URIRef(FORMAT_BASE_URI + DEFAULT_FORMAT_CODE)))

            # license
            # <dct:license rdf:resource="http://creativecommons.org/licenses/by/3.0/it/"/>
            #
            # <dcatapit:LicenseDocument rdf:about="http://creativecommons.org/licenses/by/3.0/it/">
            #    <rdf:type rdf:resource="&dct;LicenseDocument"/>
            #    <owl:versionInfo>3.0 ITA</owl:versionInfo>
            #    <foaf:name>CC BY</foaf:name>
            #    <dct:type rdf:resource="http://purl.org/adms/licencetype/Attribution"/>
            # </dcatapit:LicenseDocument>

            # "license_id" : "cc-zero"
            # "license_title" : "Creative Commons CCZero",
            # "license_url" : "http://www.opendefinition.org/licenses/cc-zero",

            license_info = interfaces.get_license_for_dcat(resource_dict.get('license_type'))
            dcat_license, license_title, license_url, license_version, dcatapit_license, names = license_info

            # be lenient about license existence
            license_maybe = license_url or dcatapit_license
            if license_maybe:
                license_maybe=license_maybe.replace("deed.it","")
                license = URIRef(license_maybe)
                if 'C1_Unknown' in license:
                    license=license.replace('https://w3id.org/italia/controlled-vocabulary/licences/C1_Unknown','http://creativecommons.org/licenses/by/4.0/it/')
                log.debug('provo a patchare la licenza: %s',license)
                if 'http' in license:
                    license=URIRef(license)
                for lang, name in names.items():
                  if 'Creative Commons Attribuzione 4.0' in name:
                    license=URIRef('https://creativecommons.org/licenses/by/4.0/')
                  if 'Italian Open Data License 2.0' in name:
                    license=URIRef('https://www.dati.gov.it/content/italian-open-data-license-v20')
                #qui è presente ancora il bug. se il dataset ha una licenza diversa dalla distribuzione, il dct.licensedocument segue il dataset 
                g.add((URIRef(license), RDF.type, DCATAPIT.LicenseDocument))
                g.add((URIRef(license), RDF.type, DCT.LicenseDocument))
                g.add((URIRef(license), DCT.type, URIRef(dcat_license)))
                if license_version:
                    g.add((license, OWL.versionInfo, Literal(license_version)))
                for lang, name in names.items():
                    g.add((license, FOAF.name, Literal(name, lang=lang)))
                if resource_dict.get('license'):
                  license=license.replace('https://w3id.org/italia/controlled-vocabulary/licences/B11_CCBYNC40','http://creativecommons.org/licenses/by/4.0/')
                  license=license.replace('by-nc','by')
                  if resource_dict['license'] == license_url:
                    log.debug('dct.license in dcatapit: %s',license)
                    #g.add((distribution, DCT.license, URIRef(license)))
                else:
                    g.add((distribution, DCT.license, URIRef('http://creativecommons.org/licenses/by/4.0/')))
            else:
                log.error('*** License not set')

            # Multilingual
            # Add localized entries in resource
            # TODO: should we remove the not-localized nodes?

            loc_dict = interfaces.get_for_resource(resource_dict['id'])

            #  The multilang fields
            loc_resource_mapping = {
                'name': (distribution, DCT.title),
                'description': (distribution, DCT.description),
            }
            self._add_multilang_values(loc_dict, loc_resource_mapping)

    def _add_multilang_values(self, loc_dict, loc_mapping, exclude_default_lang=False):
        if loc_dict:
            default_lang = get_lang() or DEFAULT_LANG
            default_lang = default_lang.split('_')[0]
            for field_name, lang_dict in loc_dict.items():
                try:
                    ref, pred, exclude = loc_mapping.get(field_name, (None, None, exclude_default_lang))
                except ValueError:
                    # prolly the tuple does not include the exclude lang boolean
                    ref, pred = loc_mapping.get(field_name, (None, None))
                    exclude = exclude_default_lang

                if pred is None:
                    log.warning('Multilang field not mapped "%s"', field_name)
                    continue
                for lang, value in lang_dict.items():
                    lang = lang.split('_')[0]  # rdflib is quite picky in lang names

                    if exclude and lang == default_lang:
                        continue
                    self.g.add((ref, pred, Literal(value, lang=lang)))
      #  else:
       #     log.warning('No mulitlang source data')

    def _add_right_holder(self, dataset_dict, org_dict, ref):
        basekey = 'holder'
        agent_name = self._get_dict_value(dataset_dict, basekey + '_name', None)
        agent_id = self._get_dict_value(dataset_dict, basekey + '_identifier', None)
        holder_ref = None
        dataset_is_local = dataset_dict.get('dataset_is_local')
        if (agent_id and agent_name):
            use_dataset = True
            holder_ref = self._add_agent(dataset_dict,
                                         ref,
                                         'holder',
                                         DCT.rightsHolder,
                                         use_default_lang=dataset_is_local)
        else:
            use_dataset = False
            agent_name = org_dict.get('name')
            agent_id = org_dict.get('identifier')
            if agent_id and agent_name:
                agent_data = (agent_name, agent_id,)
                holder_ref = self._add_agent(org_dict,
                                             ref,
                                             'organization',
                                             DCT.rightsHolder,
                                             use_default_lang=True,
                                             agent_data=agent_data)
        return holder_ref, use_dataset

    def _add_themes(self, dataset_ref, aggr_raw_value, theme_raw_value):
        """
        Create theme/subtheme
        """
        themes_list = None
        sub_list = []

        # check if there's the aggregate theme/subthemes;
        if aggr_raw_value:
             #log.debug(f'Parsing aggr themes: {aggr_raw_value}')
            try:
                aggr_themes = json.loads(aggr_raw_value)
                themes_list, sub_list = theme_aggrs_unpack(aggr_themes)
            except (TypeError, ValueError) as e:
                log.warning(f'Error parsing aggr themes: {e} -- {aggr_raw_value}')

        # if no aggregate, take the plain themes
        if theme_raw_value and themes_list is None:
            themes_list = themes_parse_to_uris(theme_raw_value)

        # ckanext-dcat will leave bad values from serialized themes
        self.g.remove((dataset_ref, DCAT.theme, None))

        self._add_subthemes(dataset_ref, sub_list)

        if themes_list:
            for theme in themes_list:
                # theme_name = theme['theme']
                # subthemes = theme.get('subthemes') or []
                # theme_ref = URIRef(theme_name)
                # self.g.remove((dataset_ref, DCAT.theme, theme_ref))

                self.g.add((dataset_ref, DCAT.theme, URIRef(theme)))
                self._add_concept(THEME_CONCEPTS, uri=theme)
                # self._add_subthemes(dataset_ref, subthemes)
        else:
            self.g.add((dataset_ref, DCAT.theme, URIRef(theme_name_to_uri(DEFAULT_THEME_KEY))))
            self._add_concept(THEME_CONCEPTS, DEFAULT_THEME_KEY)

    def _add_subthemes(self, ref, subthemes):
        """
        subthemes is a list of eurovoc hrefs.

        """
        for subtheme in subthemes:
            sref = URIRef(subtheme)
            sthm = Subtheme.get(subtheme)
            if not sthm:
                log.info(f'No subtheme for {subtheme}')
                continue

            labels = sthm.get_names_dict()
            self.g.add((sref, RDF.type, SKOS.Concept))
            self.g.add((sref, RDF.type, DCATAPIT.subTheme))  # only for dcatapit 0.4, not in 1.0
            for lang, label in labels.items():
                if lang in OFFERED_LANGS:
                    labelnonmb=label[5:].strip()
                    self.g.add((sref, SKOS.prefLabel, Literal(labelnonmb, lang=lang)))
                 #   self.g.add((sref, SKOS.prefLabel, Literal(label, lang=lang)))
            self.g.add((ref, DCT.subject, sref))

    def _add_creators(self, dataset_dict, ref):
        """
        new style creators. creator field is serialized json, with pairs of name/identifier
        """
        # clear any previous data
        self.g.remove((ref, DCT.creator, None))
        creators_data = dataset_dict.get('creator')
        if not creators_data:
            for extra in (dataset_dict.get('extras') or []):
                if extra['key'] == 'creator':
                    creators_data = extra['value']

        try:
            creators = json.loads(creators_data)
        except (TypeError, ValueError) as err:
            creators = []
        if dataset_dict.get('creator_identifier') or dataset_dict.get('creator_name'):
            old_creator = {}
            if dataset_dict.get('creator_identifier'):
                old_creator['creator_identifier'] = dataset_dict['creator_identifier']
            if dataset_dict.get('creator_name'):
                old_creator['creator_name'] = {DEFAULT_LANG: dataset_dict['creator_name']}
            old_to_add = bool(old_creator)
            if old_creator.get('creator_identifier'):
                for cr in creators:
                    if cr.get('creator_identifier') and cr['creator_identifier'] == old_creator['creator_identifier']:
                        old_to_add = False
                        break
            if old_to_add:
                creators.append(old_creator)

        for creator in creators:
            self._add_agent(creator, ref, 'creator', DCT.creator)

    def _add_agent(self, _dict, ref, basekey, _type, use_default_lang=False, agent_data=None):
        ''' Stores the Agent in this format:
                <dct:publisher rdf:resource="http://dati.gov.it/resource/Amministrazione/r_liguri"/>
                    <dcatapit:Agent rdf:about="http://dati.gov.it/resource/Amministrazione/r_liguri">
                        <rdf:type rdf:resource="&foaf;Agent"/>
                        <dct:identifier>r_liguri</dct:identifier>
                        <foaf:name>Regione Liguria</foaf:name>
                    </dcatapit:Agent>

            Returns the ref to the agent node
        '''

        try:
            agent_name, agent_id = agent_data
        except (TypeError, ValueError, IndexError,):
            agent_name = self._get_dict_value(_dict, basekey + '_name', 'N/A')
            agent_id = self._get_dict_value(_dict, basekey + '_identifier', 'N/A')

        agent = BNode()
        rlang = get_lang() or DEFAULT_LANG
        rlang = rlang.split('_')[0]

        self.g.add((agent, RDF['type'], DCATAPIT.Agent))
        self.g.add((agent, RDF['type'], FOAF.Agent))
        self.g.add((ref, _type, agent))

        def _found_no_lang():
            found_no_lang = False
            for val in self.g.objects(agent, FOAF.name):
                if not hasattr(val, 'lang') or not val.lang:
                    found_no_lang = True
                    break
            return found_no_lang
        if isinstance(agent_name, dict):
            for lang, aname in agent_name.items():
                if lang in OFFERED_LANGS:
                    self.g.add((agent, FOAF.name, Literal(aname, lang=lang_mapping_ckan_to_xmllang.get(lang, lang))))
                    if lang == rlang and not _found_no_lang():
                        self.g.add((agent, FOAF.name, Literal(aname)))
        else:
            if use_default_lang:
                # we may use web context language or lang from config
                self.g.add((agent, FOAF.name, Literal(agent_name, lang=rlang)))
            else:
                self.g.add((agent, FOAF.name, Literal(agent_name)))
        self.g.add((agent, DCT.identifier, Literal(agent_id)))

        return agent

    def _add_uri_node(self, _dict, ref, item, base_uri=''):

        key, pred, fallback, _type = item

        value = self._get_dict_value(_dict, key)
        if value:
            self.g.add((ref, pred, _type(base_uri + value)))
            return True
        elif fallback:
            self.g.add((ref, pred, _type(base_uri + fallback)))
            return False
        else:
            return False

    def _remove_node(self, _dict, ref, item):

        key, pred, fallback, _type = item

        value = self._get_dict_value(_dict, key)
        if value:
            self.log_remove(key, pred)
            self.g.remove((ref, pred, _type(value)))

    def _add_concept(self, concepts, tag=None, uri=None):

        # Localized concepts should be serialized as:
        #
        # <dcat:theme rdf:resource="http://publications.europa.eu/resource/authority/data-theme/ENVI"/>
        #
        # <skos:Concept rdf:about="http://publications.europa.eu/resource/authority/data-theme/ENVI">
        #     <skos:prefLabel xml:lang="it">Ambiente</skos:prefLabel>
        # </skos:Concept>
        #
        # Return true if Concept has been added

        voc, base_uri = concepts

        if uri:
            tag = uri.replace('#', '/').split('/')[-1]

        loc_dict = interfaces.get_all_localized_tag_labels(tag)

        if loc_dict and len(loc_dict) > 0:

            concept = URIRef(uri if uri else f'{base_uri}{tag}')
            self.g.add((concept, RDF['type'], SKOS.Concept))

            for lang, label in loc_dict.items():
                lang = lang.split('_')[0]  # rdflib is quite picky in lang names
                self.g.add((concept, SKOS.prefLabel, Literal(label, lang=lang)))

            return True

        return False

    def graph_from_catalog(self, catalog_dict, catalog_ref):

        g = self.g

        for prefix, namespace in it_namespaces.items():
            g.bind(prefix, namespace)

        # Add a further type for the Catalog node
        g.add((catalog_ref, RDF.type, DCATAPIT.Catalog))

        # Replace homepage
        # Try to avoid to have the Catalog URIRef identical to the homepage URI
        g.remove((catalog_ref, FOAF.homepage, URIRef(config.get('ckan.site_url'))))
        g.add((catalog_ref, FOAF.homepage, URIRef(catalog_uri() + '/#')))
 #        g.add((catalog_ref, FOAF.homepage, URIRef(catalog_uri())))

        # publisher
        pub_agent_name = config.get('ckanext.dcatapit_configpublisher_name', 'unknown')
        pub_agent_id = config.get('ckanext.dcatapit_configpublisher_code_identifier', 'unknown')

        agent = BNode()
        self.g.add((agent, RDF['type'], DCATAPIT.Agent))
        self.g.add((agent, RDF['type'], FOAF.Agent))
        self.g.add((catalog_ref, DCT.publisher, agent))
        self.g.add((agent, FOAF.name, Literal(pub_agent_name)))
        self.g.add((agent, DCT.identifier, Literal(pub_agent_id)))

        # issued date
        issued = config.get('ckanext.dcatapit_config.catalog_issued', '1900-01-01')
        if issued:
            self._add_date_triple(catalog_ref, DCT.issued, issued)

        # theme taxonomy

        # <dcat:themeTaxonomy rdf:resource="http://publications.europa.eu/resource/authority/data-theme"/>

        # <skos:ConceptScheme rdf:about="http://publications.europa.eu/resource/authority/data-theme">
        #    <dct:title xml:lang="it">Il Vocabolario Data Theme</dct:title>
        # </skos:ConceptScheme>

        taxonomy = URIRef(THEME_BASE_URI.rstrip('/'))
        self.g.add((catalog_ref, DCAT.themeTaxonomy, taxonomy))
        self.g.add((taxonomy, RDF.type, SKOS.ConceptScheme))
        self.g.add((taxonomy, DCT.title, Literal('Il Vocabolario Data Theme', lang='it')))

        # language
        langs = config.get('ckan.locales_offered', 'it')

        if isinstance(langs, list):
        # Convert list to a space-separated string
          langs = ' '.join(langs)

        for lang_offered in langs.split():
            lang_code = lang_mapping_ckan_to_voc.get(lang_offered)
            if lang_code:
                self.g.remove((catalog_ref, DCT.language, Literal(lang_offered)))
                self.g.add((catalog_ref, DCT.language, URIRef(LANG_BASE_URI + lang_code)))

        self.g.remove((catalog_ref, DCT.language, Literal(config.get(DEFAULT_LANG))))

    def log_remove(self, key, pred):
         log.debug(f'Removing "{key}" type "{self.g.qname(pred)}"')
          #pippo=key

def organization_uri(orga_dict):
    '''
    Returns an URI for the organization

    This will be used to uniquely reference the organization on the RDF serializations.

    The value will be

        `catalog_uri()` + '/organization/' + `orga_id`

    Check the documentation for `catalog_uri()` for the recommended ways of
    setting it.

    Returns a string with the resource URI.
    '''

    uri = '{0}/organization/{1}'.format(catalog_uri().rstrip('/'), orga_dict.get('id', None))

    return uri


def remove_unused_object(g, o, oname='object'):
    usage_s, usage_p = next(g.subject_predicates(o), (None, None))
    if not usage_s:
        log.debug(f'Removing unused {oname} {o}')
        for ps, pp, po in g.triples((o, None, None)):
            po_print = g.qname(po) if pp == RDF.type else po
            log.debug(f' - Removing {oname} detail: {g.qname(pp)}::{po_print}')
            g.remove((ps, pp, po))


def guess_format(resource_dict):
    f = resource_dict.get('format')
    f = f.replace(FORMAT_BASE_URI,'')
    
    if not f:
        log.info('No format found')
        return None

    ret = format_mapping.get(f, None)

    if not ret:
        log.info('Mapping not found for format %s', f)

    return ret
