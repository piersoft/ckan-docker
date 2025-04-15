from builtins import str
from past.builtins import basestring
import json
import uuid
import logging
import hashlib
import traceback

import ckan.plugins as p
import ckan.model as model

import ckan.lib.plugins as lib_plugins
from ckanext.harvest.harvesters.base import HarvesterBase
from ckanext.harvest.model import HarvestObject, HarvestObjectExtra
from ckanext.harvest.logic.schema import unicode_safe
from ckanext.dcat.harvesters.base import DCATHarvester
from ckanext.dcat.processors import RDFParserException, RDFParser
from ckanext.dcat.interfaces import IDCATRDFHarvester
from ckan.lib.munge import munge_title_to_name, munge_tag
import ckan.plugins.toolkit as toolkit

log = logging.getLogger(__name__)


class DCATRDFHarvester(DCATHarvester):
    def _clean_tags(self, tags):
        try:
            def _update_tag(tag_dict, key, newvalue):
                # update the dict and return it
                tag_dict[key] = newvalue
                return tag_dict

            # assume it's in the package_show form
            tags = [_update_tag(t, 'name', munge_tag(t['name'])) for t in tags if munge_tag(t['name']) != '']

        except TypeError:  # a TypeError is raised if `t` above is a string
            # REST format: 'tags' is a list of strings
            tags = [munge_tag(t) for t in tags if munge_tag(t) != '']
            tags = list(set(tags))
            return tags

        return tags

    def info(self):
        return {
            'name': 'dcat_rdf',
            'title': 'Generic DCAT RDF Harvester',
            'description': 'Harvester for DCAT datasets from an RDF graph'
        }

    _names_taken = []

    def _get_dict_value(self, _dict, key, default=None):
        '''
        Returns the value for the given key on a CKAN dict

        By default a key on the root level is checked. If not found, extras
        are checked, both with the key provided and with `dcat_` prepended to
        support legacy fields.

        If not found, returns the default value, which defaults to None
        '''

        if key in _dict:
            return _dict[key]

        for extra in _dict.get('extras', []):
            if extra['key'] == key or extra['key'] == 'dcat_' + key:
                log.debug('prova extras %s', extra['value'])
                return extra['value']

        return default

    def _get_guid(self, dataset_dict, source_url=None):
        '''
        Try to get a unique identifier for a harvested dataset

        It will be the first found of:
         * URI (rdf:about)
         * dcat:identifier
         * Source URL + Dataset name
         * Dataset name

         The last two are obviously not optimal, as depend on title, which
         might change.

         Returns None if no guid could be decided.
        '''
        guid = None

        guid = (
            self._get_dict_value(dataset_dict, 'uri') or
            self._get_dict_value(dataset_dict, 'identifier')
        )
        if guid:
            return guid

        if dataset_dict.get('name'):
            guid = dataset_dict['name']
            if source_url:
                guid = source_url.rstrip('/') + '/' + guid
        return guid

    def _mark_datasets_for_deletion(self, guids_in_source, harvest_job):
        '''
        Given a list of guids in the remote source, checks which in the DB
        need to be deleted

        To do so it queries all guids in the DB for this source and calculates
        the difference.

        For each of these creates a HarvestObject with the dataset id, marked
        for deletion.

        Returns a list with the ids of the Harvest Objects to delete.
        '''

        object_ids = []

        # Get all previous current guids and dataset ids for this source
        query = model.Session.query(HarvestObject.guid, HarvestObject.package_id) \
                             .filter(HarvestObject.current==True) \
                             .filter(HarvestObject.harvest_source_id==harvest_job.source.id)

        guid_to_package_id = {}
        for guid, package_id in query:
            guid_to_package_id[guid] = package_id

        guids_in_db = list(guid_to_package_id.keys())

        # Get objects/datasets to delete (ie in the DB but not in the source)
        guids_to_delete = set(guids_in_db) - set(guids_in_source)

        # Create a harvest object for each of them, flagged for deletion
        for guid in guids_to_delete:
            obj = HarvestObject(guid=guid, job=harvest_job,
                                package_id=guid_to_package_id[guid],
                                extras=[HarvestObjectExtra(key='status',
                                                           value='delete')])

            # Mark the rest of objects for this guid as not current
            model.Session.query(HarvestObject) \
                         .filter_by(guid=guid) \
                         .update({'current': False}, False)
            obj.save()
            object_ids.append(obj.id)

        return object_ids

    def validate_config(self, source_config):
        if not source_config:
            return source_config

        source_config_obj = json.loads(source_config)
        if 'rdf_format' in source_config_obj:
            rdf_format = source_config_obj['rdf_format']
            if not isinstance(rdf_format, basestring):
                raise ValueError('rdf_format must be a string')
            supported_formats = RDFParser().supported_formats()
            if rdf_format not in supported_formats:
                raise ValueError('rdf_format should be one of: ' + ", ".join(supported_formats))

        return source_config

    def gather_stage(self, harvest_job):

        log.debug('In DCATRDFHarvester gather_stage')
        setlic=0
        rdf_format = None
        if harvest_job.source.config:
            rdf_format = json.loads(harvest_job.source.config).get("rdf_format")

        # Get file contents of first page
        next_page_url = harvest_job.source.url

        guids_in_source = []
        object_ids = []
        last_content_hash = None
        self._names_taken = []

        while next_page_url:
            for harvester in p.PluginImplementations(IDCATRDFHarvester):
                next_page_url, before_download_errors = harvester.before_download(next_page_url, harvest_job)

                for error_msg in before_download_errors:
                    self._save_gather_error(error_msg, harvest_job)

                if not next_page_url:
                    return []

            content, rdf_format = self._get_content_and_type(next_page_url, harvest_job, 1, content_type=rdf_format)

            content_hash = hashlib.md5()
            if content:
                content_hash.update(content.encode('utf8'))

            if last_content_hash:
                if content_hash.digest() == last_content_hash.digest():
                    log.warning('Remote content was the same even when using a paginated URL, skipping')
                    break
            else:
                last_content_hash = content_hash

            # TODO: store content?
            for harvester in p.PluginImplementations(IDCATRDFHarvester):
                content, after_download_errors = harvester.after_download(content, harvest_job)

                for error_msg in after_download_errors:
                    self._save_gather_error(error_msg, harvest_job)

            if not content:
                return []

            # TODO: profiles conf
            parser = RDFParser()

            try:
                parser.parse(content, _format=rdf_format)
            except RDFParserException as e:
                self._save_gather_error('Error parsing the RDF file: {0}'.format(e), harvest_job)
                return []

            for harvester in p.PluginImplementations(IDCATRDFHarvester):
                parser, after_parsing_errors = harvester.after_parsing(parser, harvest_job)

                for error_msg in after_parsing_errors:
                    self._save_gather_error(error_msg, harvest_job)

            if not parser:
                return []

            try:

                source_dataset = model.Package.get(harvest_job.source.id)

                for dataset in parser.datasets():
                    if not dataset.get('name'):
                        dataset['name'] = self._gen_new_name(dataset['title'])
                    if dataset['name'] in self._names_taken:
                        suffix = len([i for i in self._names_taken if i.startswith(dataset['name'] + '-')]) + 1
                        dataset['name'] = '{}-{}'.format(dataset['name'], suffix)
                    self._names_taken.append(dataset['name'])

                    # Unless already set by the parser, get the owner organization (if any)
                    # from the harvest source dataset
                    if not dataset.get('owner_org'):
                        if source_dataset.owner_org:
                            dataset['owner_org'] = source_dataset.owner_org

                    # Try to get a unique identifier for the harvested dataset
                    guid = self._get_guid(dataset, source_url=source_dataset.url)

                    if not guid:
                        self._save_gather_error('Could not get a unique identifier for dataset: {0}'.format(dataset),
                                                harvest_job)
                        continue

                    dataset['extras'].append({'key': 'guid', 'value': guid})
                    #log.debug('dataset extras in gather rdf %s',dataset['extras'])
                    guids_in_source.append(guid)

                    obj = HarvestObject(guid=guid, job=harvest_job,
                                        content=json.dumps(dataset))
            
                    obj.save()
                    object_ids.append(obj.id)
            except Exception as e:
                setlic=1
                log.debug('ha dato error ma continuo')
                self._save_gather_error('Error when processsing dataset: %r / %s' % (e, traceback.format_exc()),
                                         harvest_job)
                return []
           

            # get the next page
            if setlic==0:
               next_page_url = parser.next_page()

        # Check if some datasets need to be deleted
        object_ids_to_delete = self._mark_datasets_for_deletion(guids_in_source, harvest_job)

        object_ids.extend(object_ids_to_delete)

        return object_ids

    def fetch_stage(self, harvest_object):
        # Nothing to do here
        return True

    def import_stage(self, harvest_object):

        log.debug('In DCATRDFHarvester import_stage')

        status = self._get_object_extra(harvest_object, 'status')
        if status == 'delete':
            # Delete package
            context = {'model': model, 'session': model.Session,
                       'user': self._get_user_name(), 'ignore_auth': True}

            try:
                p.toolkit.get_action('package_delete')(context, {'id': harvest_object.package_id})
                log.info('Deleted package {0} with guid {1}'.format(harvest_object.package_id,
                                                                    harvest_object.guid))
            except p.toolkit.ObjectNotFound:
                log.info('Package {0} already deleted.'.format(harvest_object.package_id))
            
            return True

        if harvest_object.content is None:
            self._save_object_error('Empty content for object {0}'.format(harvest_object.id),
                                    harvest_object, 'Import')
            return False

        try:
            dataset = json.loads(harvest_object.content)
        except ValueError:
            self._save_object_error('Could not parse content for object {0}'.format(harvest_object.id),
                                    harvest_object, 'Import')
            return False

        # Get the last harvested object (if any)
        previous_object = model.Session.query(HarvestObject) \
                                       .filter(HarvestObject.guid==harvest_object.guid) \
                                       .filter(HarvestObject.current==True) \
                                       .first()

        # Flag previous object as not current anymore
        if previous_object:
            previous_object.current = False
            previous_object.add()

        # Flag this object as the current one
        harvest_object.current = True
        harvest_object.add()

        context = {
            'user': self._get_user_name(),
            'return_id_only': True,
            'ignore_auth': True,
        }

        dataset = self.modify_package_dict(dataset, {}, harvest_object)

        # Check if a dataset with the same guid exists
        existing_dataset = self._get_existing_dataset(harvest_object.guid)

        try:
            package_plugin = lib_plugins.lookup_package_plugin(dataset.get('type', None))
            if existing_dataset:
                package_schema = package_plugin.update_package_schema()
                for harvester in p.PluginImplementations(IDCATRDFHarvester):
                    package_schema = harvester.update_package_schema_for_update(package_schema)
                context['schema'] = package_schema
#                 if dataset.get('access_rights'):
  #                 if dataset['access_rights']=='http://publications.europa.eu/resource/authority/access-right/PUBLIC':
    #                 log.warning('1. esiste access_rights')
      #               if 'access_rights' in package_schema:
        #               del package_schema['access_rights']
          #             dataset['access_rights']='http://publications.europa.eu/resource/authority/access-right/PUBLIC'


                # Don't change the dataset name even if the title has
                dataset['name'] = existing_dataset['name']
                dataset['id'] = existing_dataset['id']
                if 'access_rights' in existing_dataset:
#                    dataset['access_rights'] = existing_dataset['access_rights']
                  existing_dataset.pop('access_rights',None)
                #  dataset['access_rights']='http://publications.europa.eu/resource/authority/access-right/PUBLIC'
                  log.debug('in existing dataset è presente access_right')
                if 'applicableLegislation' in existing_dataset:
                  existing_dataset.pop('applicableLegislation',None)
                  existing_dataset.pop('applicable_legislation',None)
                  # dataset['access_rights']='http://publications.europa.eu/resource/authority/access-right/PUBLIC'
                  log.debug('in existing dataset è presente applicableLegislation')
                if 'applicable_legislation' in existing_dataset:
                  existing_dataset.pop('applicableLegislation',None)
                  existing_dataset.pop('applicable_legislation',None)
                  # dataset['access_rights']='http://publications.europa.eu/resource/authority/access-right/PUBLIC'
                  log.debug('in existing dataset è presente applicableLegislation')
                if 'hvd_category' in existing_dataset:
                  existing_dataset.pop('hvd_category',None)
                  # dataset['access_rights']='http://publications.europa.eu/resource/authority/access-right/PUBLIC'
                  log.debug('in existing dataset è presente hvd_category')
                #log.debug('existing_dataset: %s',existing_dataset)
                identif = dataset['identifier']
                if not identif:
                    dataset['identifier']=dataset['id']

                notes = dataset['notes']
                if not notes:
                    dataset['notes']="N_A"
                tags = dataset.get('tags',[])
                if not tags:
                    dataset['tags']=[{"display_name": "N_A", "id": "b8907f2e-928c-4a83-a24e-51c0c0fc6d39", "name": "N_A", "state": "active"}]
                else:
                    dataset['tags']=self._clean_tags(tags)
                freq = dataset.get('frequency')
                if not freq:
                    dataset['frequency']="UNKNOWN"

                harvester_tmp_dict = {}

                # check if resources already exist based on their URI
                existing_resources =  existing_dataset.get('resources')
                resource_mapping = {r.get('uri'): r.get('id') for r in existing_resources if r.get('uri')}
                for resource in dataset.get('resources'):
                    res_uri = resource.get('uri')
                    res_disform = resource.get('distribution_format')
                    if not res_disform:
                      resource['distribution_format']=resource['format']
                    if res_uri and res_uri in resource_mapping:
                        resource['id'] = resource_mapping[res_uri]
                        if not 'rights' in resource:
                           resource['rights']='http://publications.europa.eu/resource/authority/access-right/PUBLIC'
                        else:
                           resource.pop('rights')
                           resource['rights']='http://publications.europa.eu/resource/authority/access-right/PUBLIC'
 #                           if not dataset['access_rights']:
   #                          dataset['access_rights']='http://publications.europa.eu/resource/authority/access-right/PUBLIC'
   #                         if 'license' in resource:
      #                        if resource['license']=='https://w3id.org/italia/controlled-vocabulary/licences/A21_CCBY40':
      #                         resource['license'] = 'https://creativecommons.org/licenses/by/4.0/'
      #                        if resource['license']=='https://w3id.org/italia/controlled-vocabulary/licences/A29_IODL20':
      #                         resource['license'] = 'https://www.dati.gov.it/content/italian-open-data-license-v20' 
                for harvester in p.PluginImplementations(IDCATRDFHarvester):
                    harvester.before_update(harvest_object, dataset, harvester_tmp_dict)
                    package_schema = harvester.update_package_schema_for_update(package_schema)
                    context['schema'] = package_schema
                    if 'access_rights' in package_schema:
                       log.warning('2.0  esiste access_rights')
                       del package_schema['access_rights']
                       dataset.pop('access_rights',None)
                        #dataset['access_rights']='http://publications.europa.eu/resource/authority/access-right/PUBLIC'
                    if 'applicable_legislation' in package_schema:
                       log.warning('2.0  esiste applicable_legislation')
                       del package_schema['applicable_legislation']
                       dataset.pop('applicable_legislation',None)
                     #   dataset['extras'].append({'key':'applicable_legislation','value':'http://data.europa.eu/eli/reg_impl/2023/138/oj'})
                    if 'hvd_category' in package_schema:
                       log.warning('2.0  esiste hvdCategory')
                       del package_schema['hvd_category']
                schemaexist=False
                try:
                    if dataset:
                        package_schema = package_plugin.update_package_schema()
                        for harvester in p.PluginImplementations(IDCATRDFHarvester):
                             package_schema = harvester.update_package_schema_for_update(package_schema)
                        context['schema'] = package_schema
                        extras_alt_identifiers = None
                        extras_alt_idx = None
                        if 'access_rights' in package_schema:
 #                            del package_schema['access_rights']
                            log.warning('2.1 esiste access_rights')
                            dataset.pop('access_rights',None)
                            dataset['access_rights']='http://publications.europa.eu/resource/authority/access-right/PUBLIC'
                            existing_dataset['access_rights']='http://publications.europa.eu/resource/authority/access-right/PUBLIC'
                            log.debug('controllo dataset.get access_right %s',dataset.get('access_rights'))
                            checkar=dataset.get('access_rights')
                            if 'http://publications.europa.eu/resource/authority/access-right/PUBLIC' in checkar:
                             log.warning('2.2 esiste access_rights ma provo a riscriverlo')
                             del package_schema['access_rights']
                             schemaexist=True
# alcuni cataloghi ad oggi espongono gia' access_right
                #             if dataset.get('holder_identifier')=='ispra_rm':
                #               del package_schema['access_rights']
                #             if dataset.get('publisher_identifier')=='lispa':
                #               del package_schema['access_rights']
                #             if dataset.get('publisher_identifier')=='cciaan':
                #               del package_schema['access_rights']
                #             if dataset.get('publisher_identifier')=='piersoft':
                #               del package_schema['access_rights']
                #             if dataset.get('publisher_identifier')=='ISTAT':
                #               del package_schema['access_rights']
                #             if 'geodati-rndt-hvd' in dataset.get('organization[]'):
                #               del package_schema['access_rights']
                             dataset.pop('access_rights',None)
                             existing_dataset['access_rights']='http://publications.europa.eu/resource/authority/access-right/PUBLIC'
                             dataset['access_rights']='http://publications.europa.eu/resource/authority/access-right/PUBLIC'
                        if 'applicable_legislation' in package_schema:
                            del package_schema['applicable_legislation']
                            log.warning('2.1 esiste applicable_legislation')
                            dataset.pop('applicable_legislation',None)
                        if 'hvd_category' in package_schema:
                            log.warning('2.0  esiste hvd_category')
                            del package_schema['hvd_category']
                        if 'applicableLegislation' in package_schema:
                            del package_schema['applicableLegislation']
                            log.warning('2.1 esiste applicableLegislation')
                            dataset.pop('applicableLegislation',None)
 #                            dataset['extras'].append({'key':'applicableLegislation','value':'http://data.europa.eu/eli/reg_impl/2023/138/oj'})
                        # Save reference to the package on the object
                        for eidx, ex in enumerate(dataset.get('extras') or []):
                           #log.debug('controllo negli extra le key: %s', ex['key'])
                           if ex['key'] == 'access_rights' or ex['key'] == 'hvd_category' or ex['key'] == 'applicable_legislation':
                             extras_alt_identifiers = ex['value']
                             schemaexist=True
                             log.debug('ho cancellato negli extra il value: %s', ex['value'])
                             extras_alt_idx = eidx
                             break
                        harvest_object.package_id = dataset['id']
                        harvest_object.add()

                        #p.toolkit.get_action('package_update')(context, dataset)
                        if dataset.get('access_rights') !='http://publications.europa.eu/resource/authority/access-right/PUBLIC':
                        #if dataset.get('access_rights'):
                              dataset['access_rights']='http://publications.europa.eu/resource/authority/access-right/PUBLIC'
                        p.toolkit.get_action('package_update')(context, dataset)
                    else:
                        log.info('Ignoring dataset %s' % existing_dataset['name'])
                        return 'unchanged'
                except p.toolkit.ValidationError as e:
                  if schemaexist==False:
                    self._save_object_error('Update validation Error: %s' % str(e.error_summary), harvest_object, 'Import')
                    return False

                for harvester in p.PluginImplementations(IDCATRDFHarvester):
                    err = harvester.after_update(harvest_object, dataset, harvester_tmp_dict)

                    if err:
                        self._save_object_error('RDFHarvester plugin error: %s' % err, harvest_object, 'Import')
                        return False

                log.info('Updated dataset %s' % dataset['name'])

#  altrimenti il dataset è nuovo a va creato da zero
            else:
                package_schema = package_plugin.create_package_schema()
                for harvester in p.PluginImplementations(IDCATRDFHarvester):
                    package_schema = harvester.update_package_schema_for_create(package_schema)
                context['schema'] = package_schema

                # We need to explicitly provide a package ID
                dataset['id'] = str(uuid.uuid4())
                package_schema['id'] = [unicode_safe]
                
                if package_schema['access_rights']:
                       del package_schema['access_rights']
                       dataset['access_rights']='http://publications.europa.eu/resource/authority/access-right/PUBLIC'
                if package_schema['applicable_legislation']:
                       del package_schema['applicable_legislation']
                       dataset['applicable_legislation']='http://data.europa.eu/eli/reg_impl/2023/138/oj'
                if package_schema['hvd_category']:
                       del package_schema['hvd_category']
                harvester_tmp_dict = {}

                name = dataset['name']
                identif = dataset['identifier']
                if not identif:
                    dataset['identifier']=dataset['id']
                notes = dataset['notes']
                if not notes:
                    dataset['notes']="N_A"
                tags = dataset.get('tags',[]) 
                if not tags:
                    dataset['tags']=[{"display_name": "N_A", "id": "b8907f2e-928c-4a83-a24e-51c0c0fc6d39", "name": "N_A", "state": "active"}]
                else:
                    dataset['tags']=self._clean_tags(tags)
                freq = dataset.get('frequency')
                if not freq:
                    dataset['frequency']="UNKNOWN"
                packid=dataset.get('package_id')
                if packid:
                     del dataset['package_id']
                     del  package_schema['package_id']
                for harvester in p.PluginImplementations(IDCATRDFHarvester):
                    harvester.before_create(harvest_object, dataset, harvester_tmp_dict)
                context['schema'] = package_schema
                if 'access_rights' in package_schema:
                       del package_schema['access_rights']
                       dataset['access_rights']='http://publications.europa.eu/resource/authority/access-right/PUBLIC'
                if 'applicable_legislation'  in package_schema:
                       del package_schema['applicable_legislation']
                       dataset['applicable_legislation']='http://data.europa.eu/eli/reg_impl/2023/138/oj'
                if 'hvd_category' in package_schema:
                       del package_schema['hvd_category']
                if dataset.get('access_rights'):
 #                       del package_schema['access_rights']
                       dataset['access_rights']='http://publications.europa.eu/resource/authority/access-right/PUBLIC'
                if dataset.get('applicableLegislation'):
 #                       del package_schema['applicableLegislation']
                       dataset['applicableLegislation']='http://data.europa.eu/eli/reg_impl/2023/138/oj'
  #                if dataset.get('hvd_category'):
  #                      del package_schema['hvd_category']
                for item in dataset["extras"]:
                   if item["key"] == "landingpage":
                       dataset["url"] = item["value"]  # Aggiorna il valore
                       break
                try:
                    if dataset:
                        log.debug('dataset in rdf')

                        # Save reference to the package on the object
                        harvest_object.package_id = dataset['id']
                        harvest_object.add()
                        log.debug(harvest_object.package_id)
                        # Defer constraints and flush so the dataset can be indexed with
                        # the harvest object id (on the after_show hook from the harvester
                        # plugin)
                        model.Session.execute('SET CONSTRAINTS harvest_object_package_id_fkey DEFERRED')
                        model.Session.flush()
                       # log.debug('context: %s',context)
                        p.toolkit.get_action('package_create')(context, dataset)
                    else:
                        log.info('Ignoring dataset %s' % name)
                        return 'unchanged'
                except p.toolkit.ValidationError as e:
                     log.error('errore creazione dataset ma continuo')
                     self._save_object_error('Create validation Error: %s' % str(e.error_summary), harvest_object, 'Import')
                     return True

                for harvester in p.PluginImplementations(IDCATRDFHarvester):
                    log.debug(harvester_tmp_dict)
                    err = harvester.after_create(harvest_object, dataset, harvester_tmp_dict)
                    if err:
                        self._save_object_error('RDFHarvester plugin error: %s' % err, harvest_object, 'Import')
                        return False

                log.info('Created dataset %s' % dataset['name'])

        except Exception as e:
            self._save_object_error('Error importing dataset %s: %r / %s' % (dataset.get('name', ''), e, traceback.format_exc()), harvest_object, 'Import')
            return False

        finally:
            model.Session.commit()

        return True
