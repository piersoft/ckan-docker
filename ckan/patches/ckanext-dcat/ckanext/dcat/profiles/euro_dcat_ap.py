import re
import json
import logging
log = logging.getLogger(__name__)
from rdflib import term, URIRef, BNode, Literal
import ckantoolkit as toolkit
import ckan.logic as logic
from ckan.lib.munge import munge_tag

from ckanext.dcat.utils import (
    resource_uri,
    DCAT_EXPOSE_SUBCATALOGS,
    DCAT_CLEAN_TAGS,
    publisher_uri_organization_fallback,
)
from .base import RDFProfile, URIRefOrLiteral, CleanedURIRef
from .base import (
    RDF,
    XSD,
    SKOS,
    RDFS,
    DCAT,
    DCT,
    ADMS,
    XSD,
    VCARD,
    FOAF,
    SCHEMA,
    SKOS,
    LOCN,
    GSP,
    OWL,
    SPDX,
    GEOJSON_IMT,
    namespaces,
)

config = toolkit.config


DISTRIBUTION_LICENSE_FALLBACK_CONFIG = "ckanext.dcat.resource.inherit.license"
PREF_LANDING= config.get('ckanext.dcat.base_uri')

class EuropeanDCATAPProfile(RDFProfile):
    """
    An RDF profile based on the DCAT-AP for data portals in Europe

    More information and specification:

    https://joinup.ec.europa.eu/asset/dcat_application_profile

    """

    def parse_dataset(self, dataset_dict, dataset_ref):

        dataset_dict["extras"] = []
        dataset_dict["resources"] = []

        # Basic fields
        for key, predicate in (
            ("title", DCT.title),
            ("notes", DCT.description),
            ("url", DCAT.landingPage),
            ("version", OWL.versionInfo),
        ):
            value = self._object_value(dataset_ref, predicate)
            if value:
                if key == 'url':
                   log.debug('CERCO DCATLANDINGPAGE: %s', value)
                   dataset_dict["extras"].append({"key": "landingpage", "value": value})
                if 'opendata.marche.camcom.it' in value:
              
                   log.debug('sono in CamCom Marche')
              #    dataset_dict[key] = value
                   log.debug('value landing: %s',value)
                else:
                    if 'onsiglio' or 'CONSIGLIO' in value:
                     value=''
                    if 'servizieducativi' in value:
                     value=''                  
                dataset_dict[key] = value

        if not dataset_dict.get("version"):
            # adms:version was supported on the first version of the DCAT-AP
            value = self._object_value(dataset_ref, ADMS.version)
            if value:
                dataset_dict["version"] = value

        # Tags
        # replace munge_tag to noop if there's no need to clean tags
        do_clean = toolkit.asbool(config.get(DCAT_CLEAN_TAGS, False))
        tags_val = [
            munge_tag(tag) if do_clean else tag for tag in self._keywords(dataset_ref)
        ]
        tags = [{"name": tag} for tag in tags_val]
        dataset_dict["tags"] = tags

        # Extras

        #  Simple values
        for key, predicate in (
            ("issued", DCT.issued),
            ("modified", DCT.modified),
            ("identifier", DCT.identifier),
            ("version_notes", ADMS.versionNotes),
            ("frequency", DCT.accrualPeriodicity),
            ("provenance", DCT.provenance),
            ("dcat_type", DCT.type),
        ):
            value = self._object_value(dataset_ref, predicate)
            if value:
                if dataset_dict.get('holder_name'):
                  if 'BDAP' in dataset_dict.get('holder_name'):
                   dataset_dict.pop('frequency', None)
                   dataset_dict['frequency']='UNKNOWN'
                   log.debug('Patch Freq per BDAP')
                if dataset_dict.get('holder_identifier'):
                 if 'r_lazio' in dataset_dict.get('holder_identifier'):
                  dataset_dict.pop('frequency', None)
                  dataset_dict['frequency']='UNKNOWN'
                if key=="identifier":
                  log.debug('value identifier: %s',value)
                  if ' ' in value:
                      value=re.sub(r'[^a-zA-Z0-9:_]',r'',value)
                      value=re.sub('\W+','', value)
                      value = value.replace('//', '')
                  if 'http' in value:
                      value=re.sub(r'[^a-zA-Z0-9:_]',r'',value)
                      value=re.sub('\W+','', value)
                      value = value.replace('//', '')
                log.debug('value freq: %s',value)
                dataset_dict["extras"].append({"key": key, "value": value})

        #  Lists
        for key, predicate, in (
            ("language", DCT.language),
            ("theme", DCAT.theme),
            ("alternate_identifier", ADMS.identifier),
            ("conforms_to", DCT.conformsTo),
            ("documentation", FOAF.page),
            ("related_resource", DCT.relation),
            ("has_version", DCT.hasVersion),
            ("is_version_of", DCT.isVersionOf),
            ("source", DCT.source),
            ("sample", ADMS.sample),
        ):
            values = self._object_value_list(dataset_ref, predicate)
            if values:
                 # log.debug('values in list eurodcat %s',values)
                  dataset_dict["extras"].append({"key": key, "value": json.dumps(values)})
        # Contact details
        contact = self._contact_details(dataset_ref, DCAT.contactPoint)
        if not contact:
            # adms:contactPoint was supported on the first version of DCAT-AP
            contact = self._contact_details(dataset_ref, ADMS.contactPoint)

        if contact:
            for key in ("uri", "name", "email"):
                if contact.get(key):
                    dataset_dict["extras"].append(
                        {"key": "contact_{0}".format(key), "value": contact.get(key)}
                    )

        # Publisher
        publisher = self._publisher(dataset_ref, DCT.publisher)
        for key in ("uri", "name", "email", "url", "type"):
            if publisher.get(key):
                dataset_dict["extras"].append(
                    {"key": "publisher_{0}".format(key), "value": publisher.get(key)}
                )

        # Temporal
        start, end = self._time_interval(dataset_ref, DCT.temporal)
        if start:
            dataset_dict["extras"].append({"key": "temporal_start", "value": start})
        if end:
            dataset_dict["extras"].append({"key": "temporal_end", "value": end})

        # Spatial
        spatial = self._spatial(dataset_ref, DCT.spatial)
        for key in ("uri", "text", "geom"):
            self._add_spatial_to_dict(dataset_dict, key, spatial)

        # Dataset URI (explicitly show the missing ones)
        dataset_uri = str(dataset_ref) if isinstance(dataset_ref, term.URIRef) else ""
        dataset_dict["extras"].append({"key": "uri", "value": dataset_uri})

        # access_rights
        access_rights = self._access_rights(dataset_ref, DCT.accessRights)
        if access_rights:
            dataset_dict["extras"].append(
                {"key": "access_rights", "value": access_rights}
            )

        # License
        if "license_id" not in dataset_dict:
            dataset_dict["license_id"] = self._license(dataset_ref)

        # Source Catalog
        if toolkit.asbool(config.get(DCAT_EXPOSE_SUBCATALOGS, False)):
            catalog_src = self._get_source_catalog(dataset_ref)
            if catalog_src is not None:
                src_data = self._extract_catalog_dict(catalog_src)
                dataset_dict["extras"].extend(src_data)

        # Resources
        for distribution in self._distributions(dataset_ref):

            resource_dict = {}

            #  Simple values
            for key, predicate in (
                ("name", DCT.title),
                ("description", DCT.description),
                ("access_url", DCAT.accessURL),
                ("download_url", DCAT.downloadURL),
                ("issued", DCT.issued),
                ("modified", DCT.modified),
                ("status", ADMS.status),
                ("license", DCT.license),
            ):
                value = self._object_value(distribution, predicate)
                if value:
                    # applico patch alle licenze specifiche e per evitare duplicati in dct:license
                    value=value.replace("deed.it","")
                    value=value.replace('https://sparql-noipa.mef.gov.it/metadata/Licenza','https://creativecommons.org/licenses/by/4.0/')
                    value=value.replace('https://api.smartdatanet.it/metadataapi/api/license/CCBY','https://creativecommons.org/licenses/by/4.0/')
                    value=value.replace('https://w3id.org/italia/controlled-vocabulary/licences/A11_CCO10','https://creativecommons.org/publicdomain/zero/1.0/')
                    value=value.replace('https://w3id.org/italia/controlled-vocabulary/licences/A29_IODL20','https://www.dati.gov.it/content/italian-open-data-license-v20')
                    value=value.replace("https://w3id.org/italia/controlled-vocabulary/licences/A21_CCBY40","https://creativecommons.org/licenses/by/4.0/")              
                    value=value.replace('https://w3id.org/italia/controlled-vocabulary/licences/A21:CCBY40','https://w3id.org/italia/controlled-vocabulary/licences/A21_CCBY40')
                    value=value.replace('https://w3id.org/italia/controlled-vocabulary/licences/A11:CCO10','https://w3id.org/italia/controlled-vocabulary/licences/A11_CCO10')
                    value=value.replace('https://w3id.org/italia/controlled-vocabulary/licences/C1_Unknown','https://creativecommons.org/licenses/by/4.0/')

                    log.info('valuelic: %s',value)
                    resource_dict[key] = value

            resource_dict["url"] = self._object_value(
                distribution, DCAT.downloadURL
            ) or self._object_value(distribution, DCAT.accessURL)
            #  Lists
            for key, predicate in (
                ("language", DCT.language),
                ("documentation", FOAF.page),
                ("conforms_to", DCT.conformsTo),
            ):
                values = self._object_value_list(distribution, predicate)
                if values:
                    resource_dict[key] = json.dumps(values)

            # rights
            rights = self._access_rights(distribution, DCT.rights)
            if rights:
                resource_dict["rights"] = rights

            # Format and media type
            normalize_ckan_format = toolkit.asbool(
                config.get("ckanext.dcat.normalize_ckan_format", True)
            )
            imt, label = self._distribution_format(distribution, normalize_ckan_format)

            if imt:
                resource_dict["mimetype"] = imt

            if label:
                # log.debug('resource format %s',label)
                 #label=label.replace('http://publications.europa.eu/resource/authority/file-type/','')
                resource_dict["format"] = label

            elif imt:
                resource_dict["format"] = imt

            # Size
            size = self._object_value_int(distribution, DCAT.byteSize)
            if size is not None:
                resource_dict["size"] = size

            # Checksum
            for checksum in self.g.objects(distribution, SPDX.checksum):
                algorithm = self._object_value(checksum, SPDX.algorithm)
                checksum_value = self._object_value(checksum, SPDX.checksumValue)
                if algorithm:
                    resource_dict["hash_algorithm"] = algorithm
                if checksum_value:
                    resource_dict["hash"] = checksum_value

            # Distribution URI (explicitly show the missing ones)
            resource_dict["uri"] = (
                str(distribution) if isinstance(distribution, term.URIRef) else ""
            )

            # Remember the (internal) distribution reference for referencing in
            # further profiles, e.g. for adding more properties
            resource_dict["distribution_ref"] = str(distribution)

            dataset_dict["resources"].append(resource_dict)

        if self.compatibility_mode:
            # Tweak the resulting dict to make it compatible with previous
            # versions of the ckanext-dcat parsers
            for extra in dataset_dict["extras"]:
                if extra["key"] in (
                    "issued",
                    "modified",
                    "publisher_name",
                    "publisher_email",
                ):

                    extra["key"] = "dcat_" + extra["key"]

                if extra["key"] == "language":
                    extra["value"] = ",".join(sorted(json.loads(extra["value"])))

        return dataset_dict

    def graph_from_dataset(self, dataset_dict, dataset_ref):

        g = self.g

        for prefix, namespace in namespaces.items():
            g.bind(prefix, namespace)

        g.add((dataset_ref, RDF.type, DCAT.Dataset))

        # Basic fields
        items = [
            ("title", DCT.title, None, Literal),
            ("notes", DCT.description, None, Literal),
            ("url", DCAT.landingPage, None, URIRef),
            ("identifier", DCT.identifier, ["guid", "id"], URIRefOrLiteral),
            ("version", OWL.versionInfo, ["dcat_version"], Literal),
            ("version_notes", ADMS.versionNotes, None, Literal),
            ("frequency", DCT.accrualPeriodicity, None, URIRefOrLiteral),
            ("access_rights", DCT.accessRights, None, URIRefOrLiteral),
            ("dcat_type", DCT.type, None, Literal),
            ("provenance", DCT.provenance, None, Literal),
        ]
        if dataset_dict.get('url'):
         if 'www.comune.torino.it/servizieducativi/' in dataset_dict['url']:
               log.debug('trovata doppia landingpage nel Comune di Torino')
               dataset_dict.pop('url', None)
         elif 'serviziocontratti' in dataset_dict['url']:
               log.debug('trovata doppia landingpage nel M_INF')
               dataset_dict.pop('url', None)
         elif 'http' not in dataset_dict['url']:
               log.debug('trovata doppia landingpage per datasetmodificato in locale')
               dataset_dict.pop('url', None)
         else:
               self._add_triples_from_dict(dataset_dict, dataset_ref, items)
        if dataset_dict.get('identifier'):
           if ' ' in dataset_dict.get('identifier'):
              identifier='';
              identifier=re.sub(r'[^a-zA-Z0-9:_]',r'',dataset_dict["identifier"])
              identifier=re.sub('\W+','', dataset_dict["identifier"])
              dataset_dict.pop('identifier', None)
              dataset_dict["identifier"]=identifier
              log.debug('sanitazed identifier')
        if  dataset_dict.get('access_rights') is not None:
              log.debug('esiste accessrights PUBLIC nel dcat')
        else:
              dataset_dict.pop('access_rights', None)
              dataset_dict["access_rights"]= 'http://publications.europa.eu/resource/authority/access-right/PUBLIC'
              log.debug('non esiste accessrights PUBLIC nel dcat e lo aggiungo')
            
        self._add_triples_from_dict(dataset_dict, dataset_ref, items)


        # Tags
        for tag in dataset_dict.get("tags", []):
            g.add((dataset_ref, DCAT.keyword, Literal(tag["name"])))

        # Dates
        items = [
            ("issued", DCT.issued, ["metadata_created"], Literal),
            ("modified", DCT.modified, ["metadata_modified"], Literal),
        ]
        self._add_date_triples_from_dict(dataset_dict, dataset_ref, items)

        #  Lists
        items = [
            ("language", DCT.language, None, URIRefOrLiteral),
            ("theme", DCAT.theme, None, URIRef),
            ("conforms_to", DCT.conformsTo, None, Literal),
            ("alternate_identifier", ADMS.identifier, None, URIRefOrLiteral),
            ("documentation", FOAF.page, None, URIRefOrLiteral),
            ("related_resource", DCT.relation, None, URIRefOrLiteral),
            ("has_version", DCT.hasVersion, None, URIRefOrLiteral),
            ("is_version_of", DCT.isVersionOf, None, URIRefOrLiteral),
            ("source", DCT.source, None, URIRefOrLiteral),
            ("sample", ADMS.sample, None, URIRefOrLiteral),
        ]
        
       # log.debug('in euro2 theme %s',dataset_dict.get('theme'))
        self._add_list_triples_from_dict(dataset_dict, dataset_ref, items)

        # Contact details
        if any(
            [
                self._get_dataset_value(dataset_dict, "contact_uri"),
                self._get_dataset_value(dataset_dict, "contact_name"),
                self._get_dataset_value(dataset_dict, "contact_email"),
                self._get_dataset_value(dataset_dict, "maintainer"),
                self._get_dataset_value(dataset_dict, "maintainer_email"),
                self._get_dataset_value(dataset_dict, "author"),
                self._get_dataset_value(dataset_dict, "author_email"),
            ]
        ):

            contact_uri = self._get_dataset_value(dataset_dict, "contact_uri")
            if contact_uri:
                contact_details = CleanedURIRef(contact_uri)
            else:
                contact_details = BNode()

            g.add((contact_details, RDF.type, VCARD.Organization))
             #g.add((dataset_ref, DCAT.contactPoint, contact_details))
            # get orga info
            org_show = logic.get_action('organization_show')
            org_id = dataset_dict.get('owner_org')
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

            if not org_dict.get('name'):
# prova contactpoint a lasciarlo solo al dcatapit
             self._add_triple_from_dict(
                dataset_dict,
                contact_details,
                VCARD.fn,
                "contact_name",
                ["maintainer", "author"],
             )

            if not org_dict.get('email'):
            # Add mail address as URIRef, and ensure it has a mailto: prefix
             self._add_triple_from_dict(
                dataset_dict,
                contact_details,
                VCARD.hasEmail,
                "contact_email",
                ["maintainer_email", "author_email"],
                _type=URIRef,
                value_modifier=self._add_mailto,
             )

        # Publisher
        if any(
            [
                self._get_dataset_value(dataset_dict, "publisher_uri"),
                self._get_dataset_value(dataset_dict, "publisher_name"),
                dataset_dict.get("organization"),
            ]
        ):

            publisher_uri = self._get_dataset_value(dataset_dict, "publisher_uri")
            publisher_uri_fallback = publisher_uri_organization_fallback(dataset_dict)
            publisher_name = self._get_dataset_value(dataset_dict, "publisher_name")
            if publisher_uri:
                publisher_details = CleanedURIRef(publisher_uri)
            elif not publisher_name and publisher_uri_fallback:
                # neither URI nor name are available, use organization as fallback
                publisher_details = CleanedURIRef(publisher_uri_fallback)
            else:
                log.debug('No publisher_uri')
                # No publisher_uri
                publisher_details = BNode()

 #            g.add((publisher_details, RDF.type, FOAF.Organization))
            g.add((dataset_ref, DCT.publisher, publisher_details))

            # In case no name and URI are available, again fall back to organization.
            # If no name but an URI is available, the name literal remains empty to
            # avoid mixing organization and dataset values.
            if (
                not publisher_name
                and not publisher_uri
                and dataset_dict.get("organization")
            ):
                publisher_name = dataset_dict["organization"]["title"]
 # provo a lasciare il dcatapit solo
 #            g.add((publisher_details, FOAF.name, Literal(publisher_name)))
            # TODO: It would make sense to fallback these to organization
            # fields but they are not in the default schema and the
            # `organization` object in the dataset_dict does not include
            # custom fields
            items = [
                ("publisher_email", FOAF.mbox, None, Literal),
                ("publisher_url", FOAF.homepage, None, URIRef),
                ("publisher_type", DCT.type, None, URIRefOrLiteral),
            ]

            self._add_triples_from_dict(dataset_dict, publisher_details, items)

        # Temporal
        start = self._get_dataset_value(dataset_dict, "temporal_start")
        end = self._get_dataset_value(dataset_dict, "temporal_end")
        if start or end:
            temporal_extent = BNode()

            g.add((temporal_extent, RDF.type, DCT.PeriodOfTime))
            if start:
                self._add_date_triple(temporal_extent, DCAT.startDate, start)
            if end:
                self._add_date_triple(temporal_extent, DCAT.endDate, end)
            g.add((dataset_ref, DCT.temporal, temporal_extent))

        # Spatial
        spatial_text = self._get_dataset_value(dataset_dict, "spatial_text")
        spatial_geom = self._get_dataset_value(dataset_dict, "spatial")

        if spatial_text or spatial_geom:
            spatial_ref = self._get_or_create_spatial_ref(dataset_dict, dataset_ref)

            if spatial_text:
                g.add((spatial_ref, SKOS.prefLabel, Literal(spatial_text)))

            if spatial_geom:
                self._add_spatial_value_to_graph(
                    spatial_ref, LOCN.geometry, spatial_geom
                )

        # Use fallback license if set in config
        resource_license_fallback = None
        if toolkit.asbool(config.get(DISTRIBUTION_LICENSE_FALLBACK_CONFIG, False)):
            if "license_id" in dataset_dict and isinstance(
                URIRefOrLiteral(dataset_dict["license_id"]), URIRef
            ):
                resource_license_fallback = dataset_dict["license_id"]
            elif "license_url" in dataset_dict and isinstance(
                URIRefOrLiteral(dataset_dict["license_url"]), URIRef
            ):
                resource_license_fallback = dataset_dict["license_url"]

        # Resources
        for resource_dict in dataset_dict.get("resources", []):

           distribution = CleanedURIRef(resource_uri(resource_dict))
           if dataset_dict.get('holder_identifier'):
            if 'cmna' in dataset_dict.get('holder_identifier'):
              distribution = distribution.replace(PREF_LANDING,"https://dati.cittametropolitana.na.it/")
              distribution=CleanedURIRef(distribution)
            if '00514490010' in dataset_dict.get('holder_identifier'):
              distribution = distribution.replace(PREF_LANDING,"http://aperto.comune.torino.it/")
              distribution=CleanedURIRef(distribution)
            if 'r_lazio' in dataset_dict.get('holder_identifier'):
              distribution = distribution.replace(PREF_LANDING,"http://dati.lazio.it/catalog/")
              distribution=CleanedURIRef(distribution)
            if 'r_basili' in dataset_dict.get('holder_identifier'):
              distribution = distribution.replace(PREF_LANDING,"https://dati.regione.basilicata.it/catalog/")
              distribution=CleanedURIRef(distribution)
            if 'r_marche' in dataset_dict.get('holder_identifier'):
              distribution = distribution.replace(PREF_LANDING,"https://dati.regione.marche.it/")
              distribution=CleanedURIRef(distribution)
            if 'aci' in dataset_dict.get('holder_identifier'):
              distribution = distribution.replace(PREF_LANDING,"http://lod.aci.it/")
              distribution=CleanedURIRef(distribution)
               # log.info('resource_distribution_it %s',distribution)
            if 'r_emiro' in dataset_dict.get('holder_identifier'):
              distribution = distribution.replace("dati.comune.fe.it","https://dati.comune.fe.it")
              distribution = distribution.replace(PREF_LANDING,"https://dati.emilia-romagna.it/")
              distribution=CleanedURIRef(distribution)
            if 'cr_campa' in dataset_dict.get('holder_identifier'):
              distribution = distribution.replace(PREF_LANDING,"http://opendata-crc.di.unisa.it/")
              distribution=CleanedURIRef(distribution)
               # log.info('resource_distribution_it %s',distribution)
            if 'r_toscan' in dataset_dict.get('holder_identifier'):
              distribution = distribution.replace(PREF_LANDING,"https://dati.toscana.it/")
              distribution=CleanedURIRef(distribution)
            if 'm_lps' in dataset_dict.get('holder_identifier'):
              distribution = distribution.replace(PREF_LANDING,"http://dati.lavoro.gov.it/")
              distribution=CleanedURIRef(distribution)
               # log.info('resource_distribution_it %s',distribution)
            if '00304260409' in dataset_dict.get('holder_identifier'):
              distribution = distribution.replace(PREF_LANDING,"https://opendata.comune.rimini.it/")
              distribution=CleanedURIRef(distribution)
            if 'c_a345' in dataset_dict.get('holder_identifier'):
              distribution = distribution.replace(PREF_LANDING,"http://ckan.opendatalaquila.it")
              distribution=CleanedURIRef(distribution)
            if 'uds_ca' in dataset_dict.get('holder_identifier'):
              distribution = distribution.replace(PREF_LANDING,"https://data.tdm-project.it")
              distribution=CleanedURIRef(distribution)
            if 'm_it' in dataset_dict.get('holder_identifier'):
              distribution = distribution.replace(PREF_LANDING,"https://www.interno.gov.it/")
              distribution=CleanedURIRef(distribution)
            if 'm_inf' in dataset_dict.get('holder_identifier'):
              distribution = distribution.replace(PREF_LANDING,"https://dati.mit.gov.it")
              distribution=CleanedURIRef(distribution)

 #            if 'piersoft' in dataset_dict.get('holder_identifier'):
  #             distribution = distribution.replace(PREF_LANDING,"https://www.piersoft.it")
   #            distribution=CleanedURIRef(distribution)
            if 'c_e506' in dataset_dict.get('holder_identifier'):
              distribution = distribution.replace(PREF_LANDING,"http://dati.comune.lecce.it")
              distribution=CleanedURIRef(distribution)
            if distribution is not None:
             g.add((dataset_ref, DCAT.distribution, distribution))

             g.add((distribution, RDF.type, DCAT.Distribution))

 #            g.add((dataset_ref, DCAT.distribution, distribution))
 
  #           g.add((distribution, RDF.type, DCAT.Distribution))

            #  Simple values
            items = [
                ("name", DCT.title, None, Literal),
                ("description", DCT.description, None, Literal),
                ("status", ADMS.status, None, URIRefOrLiteral),
                ("rights", DCT.rights, None, URIRefOrLiteral),
                ("license", DCT.license, None, URIRefOrLiteral),
                ("access_url", DCAT.accessURL, None, URIRef),
                ("download_url", DCAT.downloadURL, None, URIRef),
            ]
            if not resource_dict.get('name') or len(resource_dict.get('name'))<2:
                 resource_dict['name']="N/A"
            if not resource_dict.get('download_url'):
             if resource_dict.get('url'):
              resource_dict['download_url']=resource_dict['url']
            if not resource_dict.get('access_url'):
             if resource_dict.get('url'):
              resource_dict['access_url']=resource_dict['url']
            if resource_dict.get('access_url'):
             if 'view-dataset' in resource_dict.get('access_url'):
               resource_dict['access_url']=resource_dict['url']
# PATCH MOLTO DELICATA: SOSTITUISCE accessURL con la url della risorsa del CKAN e inserisce in downloadURL (campo opzionale per il DCAT)  la vecchia acce>
            if dataset_dict.get('id'):
               resource_dict['access_url']='https://www.piersoftckan.biz/dataset/'+dataset_dict['id']+'/resource/'+resource_dict['id']
            if resource_dict.get('license'):
             resource_dict['license']=resource_dict['license'].replace('https://w3id.org/italia/controlled-vocabulary/licences/C1_Unknown','http://creativecommons.org/licenses/by/4.0/')
             resource_dict['license']=resource_dict['license'].replace('https://w3id.org/italia/controlled-vocabulary/licences/B11_CCBYNC40','http://creativecommons.org/licenses/by/4.0/')
            if 'c_g273' in dataset_dict.get('holder_identifier'):
              resource_dict['access_url']=resource_dict['download_url']
            if 'inps' in dataset_dict.get('holder_identifier'):
              resource_dict['access_url']=resource_dict['download_url']
            if not resource_dict.get('rights'):
                resource_dict['rights']="http://publications.europa.eu/resource/authority/access-right/PUBLIC"

            self._add_triples_from_dict(resource_dict, distribution, items)


            #  Lists
            items = [
                ("documentation", FOAF.page, None, URIRefOrLiteral),
                ("language", DCT.language, None, URIRefOrLiteral),
                ("conforms_to", DCT.conformsTo, None, URIRefOrLiteral),
            ]
            self._add_list_triples_from_dict(resource_dict, distribution, items)

            # Set default license for distribution if needed and available
            if resource_license_fallback and not (distribution, DCT.license, None) in g:
                g.add(
                    (
                        distribution,
                        DCT.license,
                        URIRefOrLiteral(resource_license_fallback),
                    )
                )

            # Format
            if 'CSV' in resource_dict.get('format'):
                 resource_dict.pop('format', None)
                 resource_dict['format']='CSV'
            if 'csv' in resource_dict.get('format'):
                 resource_dict.pop('format', None)
                 resource_dict['format']='CSV'
            if 'link' in resource_dict.get('format'):
                 resource_dict.pop('format', None)
                 resource_dict['format']='HTML_SIMPL'
            if 'ZIP' in resource_dict.get('format'):
                 resource_dict.pop('format', None)
                 resource_dict['format']='ZIP'
            if 'pdf' in resource_dict.get('format'):
                 resource_dict.pop('format', None)
                 resource_dict['format']='PDF'
            if 'PDF' in resource_dict.get('format'):
                 resource_dict.pop('format', None)
                 resource_dict['format']='PDF'
            if 'doc' in resource_dict.get('format'):
                 resource_dict.pop('format', None)
                 resource_dict['format']='DOC'
            if 'GEOJSON' in resource_dict.get('format'):
                 resource_dict.pop('format', None)
                 resource_dict['format']='GEOJSON'
            if 'esri' in resource_dict.get('format'):
                 resource_dict.pop('format', None)
                 resource_dict['format']='SHP'
            if 'kml' in resource_dict.get('format'):
                 resource_dict.pop('format', None)
                 resource_dict['format']='KML'
            if 'ov2' in resource_dict.get('format'):
                  resource_dict.pop('format', None)       
                  resource_dict['format']='BIN'    
            if 'OV2' in resource_dict.get('format'):
                  resource_dict.pop('format', None)       
                  resource_dict['format']='BIN'                 
            if 'turtle' in resource_dict.get('url'):
                  resource_dict.pop('format', None)       
                  resource_dict['format']='RDF_TURTLE'     
            if 'fgb' in resource_dict.get('url'):
                  resource_dict.pop('format', None)       
                  resource_dict['format']='SHP'

            if 'OP_DATPRO' in resource_dict.get('format') or 'ARC' in resource_dict.get('format'):
                if resource_dict.get('url'):
                 if 'rdf' in resource_dict.get('url'):
                  resource_dict.pop('format', None)       
                  resource_dict['format']='RDF'
                 if 'sparql' in resource_dict.get('url'):
                  resource_dict.pop('format', None)       
                  resource_dict['format']='SPARQLQ'
                 if 'xlsx' in resource_dict.get('url'):
                  resource_dict.pop('format', None)       
                  resource_dict['format']='XLSX'
                 if 'zip' in resource_dict.get('url'):
                  resource_dict.pop('format', None)       
                  resource_dict['format']='ZIP'
                 if 'ttl' in resource_dict.get('url'):
                  resource_dict.pop('format', None)       
                  resource_dict['format']='RDF_TURTLE'
                 if 'xml' in resource_dict.get('url'):
                  resource_dict.pop('format', None)       
                  resource_dict['format']='XML'
                 if 'xsd' in resource_dict.get('url'):
                  resource_dict.pop('format', None)       
                  resource_dict['format']='XML'
                 if 'json' in resource_dict.get('url'):
                  resource_dict.pop('format', None)       
                  resource_dict['format']='JSON'
                 if 'ov2' in resource_dict.get('url'):
                  resource_dict.pop('format', None)       
                  resource_dict['format']='BIN'                     
                 if 'turtle' in resource_dict.get('url'):
                  resource_dict.pop('format', None)       
                  resource_dict['format']='RDF_TURTLE'     
                 if 'fgb' in resource_dict.get('url'):
                  resource_dict.pop('format', None)       
                  resource_dict['format']='SHP'
                 if 'shp' in resource_dict.get('url'):
                  resource_dict.pop('format', None)       
                  resource_dict['format']='SHP'
                 if 'kml' in resource_dict.get('url'):
                  resource_dict.pop('format', None)       
                  resource_dict['format']='KML'
                 if 'umap.openstreetmap' in resource_dict.get('url'):
                  resource_dict.pop('format', None)       
                  resource_dict['format']='HTML_SIMPL'
                 if 'infogram.com' in resource_dict.get('url'):
                  resource_dict.pop('format', None)       
                  resource_dict['format']='HTML_SIMPL'
                 if 'pubhtml' in resource_dict.get('url'):
                  resource_dict.pop('format', None)       
                  resource_dict['format']='HTML_SIMPL'

            mimetype = resource_dict.get("mimetype")
            fmt = resource_dict.get("format")

            # IANA media types (either URI or Literal) should be mapped as mediaType.
            # In case format is available and mimetype is not set or identical to format,
            # check which type is appropriate.
            if fmt and (not mimetype or mimetype == fmt):
                if (
                    "iana.org/assignments/media-types" in fmt
                    or not fmt.startswith("http")
                    and "/" in fmt
                ):
                    # output format value as dcat:mediaType instead of dct:format
                    mimetype = fmt
                    fmt = None
                if 'CSV' in fmt:
                    mimetype = 'text/csv'
                if 'JSON' in fmt:
                    mimetype = 'application/json'
                if 'ZIP' in fmt:
                    mimetype = 'application/zip'
                if 'XML' in fmt:
                    mimetype = 'text/xml'
                if 'RDF' in fmt:
                    mimetype = 'application/rdf+xml'
                if 'SPARQL' in fmt:
                    mimetype = 'application/sparql-query'
                if 'XLS' in fmt:
                    mimetype = 'application/vnd.ms-excel'
                if 'GEOJSON' in fmt:
                    mimetype = 'application/geo+json'
                if 'PARQUET' in fmt:
                    mimetype = 'application/vnd.apache.parquet'
                #parquet è application/vnd.apache.parquet ma dataEU  non lo riconosce
                if 'SHP' in fmt:
                    mimetype = 'application/zip'
                if 'KML' in fmt:
                    mimetype = 'application/vnd.google-earth.kml+xml'
                if 'RDF_TURTLE' in fmt:
                    mimetype = 'text/turtle'
                if 'GPX' in fmt:
                    mimetype = 'application/vnd.gpxsee.map+xml'
                if 'N3' in fmt:
                    mimetype = 'text/n3'
                if 'BIN' in fmt:
                    mimetype = 'text/csv'
                if 'TSV' in fmt:
                    mimetype = 'text/tab-separated-values'
                if 'HTML' in fmt:
                    mimetype = 'text/html'
                if 'ODS' in fmt:
                    mimetype = 'application/vnd.oasis.opendocument.spreadsheet'
                if 'PDF' in fmt:
                    mimetype = 'application/pdf'
                if 'GPKG' in fmt:
                    mimetype = 'application/vnd.gentoo.gpkg'
  #                else:
                    # Use dct:format
     #                 mimetype = None

            if mimetype:
                if 'http' not in mimetype:
                 mimetype = "https://iana.org/assignments/media-types/"+mimetype
                mimetype = URIRef(mimetype)
                g.add((distribution, DCAT.mediaType, URIRefOrLiteral(mimetype)))

            if fmt:
              if 'http' in fmt:
                g.add((distribution, DCT["format"], URIRefOrLiteral(fmt)))

            # URL fallback and old behavior
            url = resource_dict.get("url")
            download_url = resource_dict.get("download_url")
            access_url = resource_dict.get("access_url")
            # Use url as fallback for access_url if access_url is not set and download_url is not equal
            if url and not access_url:
                if (not download_url) or (download_url and url != download_url):
                    self._add_triple_from_dict(
                        resource_dict, distribution, DCAT.accessURL, "url", _type=URIRef
                    )

            # Dates
            items = [
                ("issued", DCT.issued, ["created"], Literal),
                ("modified", DCT.modified, ["metadata_modified"], Literal),
            ]

            self._add_date_triples_from_dict(resource_dict, distribution, items)

            # Numbers
            if resource_dict.get("size"):
                try:
                    g.add(
                        (
                            distribution,
                            DCAT.byteSize,
                            Literal(float(resource_dict["size"]), datatype=XSD.decimal),
                        )
                    )
                except (ValueError, TypeError):
                    g.add((distribution, DCAT.byteSize, Literal(resource_dict["size"])))
            else:
                   g.add(
                        (
                            distribution,
                            DCAT.byteSize,
                            Literal(float("1024"), datatype=XSD.decimal),
                        )
                    )

            # Checksum
            if resource_dict.get("hash"):
              if not 'r_emiro' in dataset_dict.get('holder_identifier'):
                checksum = BNode()
                g.add((checksum, RDF.type, SPDX.Checksum))
                g.add(
                    (
                        checksum,
                        SPDX.checksumValue,
                        Literal(resource_dict["hash"], datatype=XSD.hexBinary),
                    )
                )

                if resource_dict.get("hash_algorithm"):
                    g.add(
                        (
                            checksum,
                            SPDX.algorithm,
                            URIRefOrLiteral(resource_dict["hash_algorithm"]),
                        )
                    )
                else:
                    g.add(
                        (
                            checksum,
                            SPDX.algorithm,
                            URIRefOrLiteral("http://spdx.org/rdf/terms#checksumAlgorithm_sha1"),
                        )
                    )

                g.add((distribution, SPDX.checksum, checksum))

    def graph_from_catalog(self, catalog_dict, catalog_ref):

        g = self.g

        for prefix, namespace in namespaces.items():
            g.bind(prefix, namespace)

        g.add((catalog_ref, RDF.type, DCAT.Catalog))
        catalogosenzaslash=config.get("ckan.site_url")
        catalogosenzaslash=catalogosenzaslash+'/#'
        # Basic fields
        items = [
            ("title", DCT.title, config.get("ckan.site_title"), Literal),
            (
                "description",
                DCT.description,
                config.get("ckan.site_description"),
                Literal,
            ),
            ("homepage", FOAF.homepage, catalogosenzaslash, URIRef),
            (
                "language",
                DCT.language,
                config.get("ckan.locale_default", "it"),
                URIRefOrLiteral,
            ),
        ]
        for item in items:
            key, predicate, fallback, _type = item
            if catalog_dict:
                value = catalog_dict.get(key, fallback)
            else:
                value = fallback
            if value:
                g.add((catalog_ref, predicate, _type(value)))

        # Dates
        modified = self._last_catalog_modification()
        if modified:
            self._add_date_triple(catalog_ref, DCT.modified, modified)
