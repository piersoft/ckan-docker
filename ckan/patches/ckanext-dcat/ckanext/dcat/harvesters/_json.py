from builtins import str
import json
import logging
from hashlib import sha1
import traceback
import uuid
import ckan.lib.plugins as lib_plugins
import requests

from ckan import model
from ckan import logic
from ckan import plugins as p
from ckanext.harvest.model import HarvestObject, HarvestObjectExtra
from ckanext.harvest.logic.schema import unicode_safe
from ckanext.dcat import converters
from ckanext.dcat.harvesters.base import DCATHarvester
from ckanext.dcat.interfaces import IDCATRDFHarvester
from ckan.lib.munge import munge_title_to_name, munge_tag

log = logging.getLogger(__name__)


class DCATJSONHarvester(DCATHarvester):
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
            'name': 'dcat_json',
            'title': 'DCAT JSON Harvester',
            'description': 'Harvester for DCAT dataset descriptions ' +
                           'serialized as JSON'
        }

    def _get_guids_and_datasets(self, content):

        doc = json.loads(content)

        if isinstance(doc, list):
            # Assume a list of datasets
            datasets = doc
        elif isinstance(doc, dict):
            datasets = doc.get('dataset', [])
        else:
            raise ValueError('Wrong JSON object')

        for dataset in datasets:

            as_string = json.dumps(dataset)

            # Get identifier
            guid = dataset.get('identifier')
            if not guid:
                # This is bad, any ideas welcomed
                guid = sha1(as_string).hexdigest()

            yield guid, as_string

    def _get_package_dict(self, harvest_object):

        content = harvest_object.content

        dcat_dict = json.loads(content)

        package_dict = converters.dcat_to_ckan(dcat_dict)
         #log.debug('package_dict %s',package_dict)
         #log.debug('dcat_dict %s',dcat_dict)
        return package_dict, dcat_dict

    def gather_stage(self, harvest_job):
        log.debug('In DCATJSONHarvester gather_stage')

        ids = []

        # Get the previous guids for this source
        query = \
            model.Session.query(HarvestObject.guid, HarvestObject.package_id) \
            .filter(HarvestObject.current == True) \
            .filter(HarvestObject.harvest_source_id == harvest_job.source.id)
        guid_to_package_id = {}

        for guid, package_id in query:
            guid_to_package_id[guid] = package_id

        guids_in_db = list(guid_to_package_id.keys())
        guids_in_source = []

        # Get file contents
        url = harvest_job.source.url

        previous_guids = []
        page = 1
        while True:

            try:
                content, content_type = \
                    self._get_content_and_type(url, harvest_job, page)
            except requests.exceptions.HTTPError as error:
                if error.response.status_code == 404:
                    if page > 1:
                        # Server returned a 404 after the first page, no more
                        # records
                        log.debug('404 after first page, no more pages')
                        break
                    else:
                        # Proper 404
                        msg = 'Could not get content. Server responded with ' \
                            '404 Not Found'
                        self._save_gather_error(msg, harvest_job)
                        return None
                else:
                    # This should never happen. Raising just in case.
                    raise

            if not content:
                return None

            try:

                batch_guids = []
                for guid, as_string in self._get_guids_and_datasets(content):

                    log.debug('Got identifier: {0}'
                              .format(guid.encode('utf8')))
                    batch_guids.append(guid)

                    if guid not in previous_guids:

                        if guid in guids_in_db:
                            # Dataset needs to be udpated
                            obj = HarvestObject(
                                guid=guid, job=harvest_job,
                                package_id=guid_to_package_id[guid],
                                content=as_string,
                                extras=[HarvestObjectExtra(key='status',
                                                           value='change')])
                        else:
                            # Dataset needs to be created
                            obj = HarvestObject(
                                guid=guid, job=harvest_job,
                                content=as_string,
                                extras=[HarvestObjectExtra(key='status',
                                                           value='new')])
                        obj.save()
                        ids.append(obj.id)

                if len(batch_guids) > 0:
                    guids_in_source.extend(set(batch_guids)
                                           - set(previous_guids))
                else:
                    log.debug('Empty document, no more records')
                    # Empty document, no more ids
                    break

            except ValueError as e:
                msg = 'Error parsing file: {0}'.format(str(e))
                self._save_gather_error(msg, harvest_job)
                return None

            if sorted(previous_guids) == sorted(batch_guids):
                # Server does not support pagination or no more pages
                log.debug('Same content, no more pages')
                break

            page = page + 1

            previous_guids = batch_guids

        # Check datasets that need to be deleted
        guids_to_delete = set(guids_in_db) - set(guids_in_source)
        for guid in guids_to_delete:
            obj = HarvestObject(
                guid=guid, job=harvest_job,
                package_id=guid_to_package_id[guid],
                extras=[HarvestObjectExtra(key='status', value='delete')])
            ids.append(obj.id)
            model.Session.query(HarvestObject).\
                filter_by(guid=guid).\
                update({'current': False}, False)
            obj.save()

        return ids

    def fetch_stage(self, harvest_object):
        return True

    def import_stage(self, harvest_object):
        log.debug('In DCATJSONHarvester import_stage')
        if not harvest_object:
            log.error('No harvest object received')
            return False
        else:
 #            log.debug('harvest_object %s', harvest_object)
             log.debug('harvest_object.package_id %s', harvest_object.package_id)
        if self.force_import:
            status = 'change'
        else:
            status = self._get_object_extra(harvest_object, 'status')

        if status == 'delete':
            # Delete package
            context = {'model': model, 'session': model.Session,
                       'user': self._get_user_name()}

            p.toolkit.get_action('package_delete')(
                context, {'id': harvest_object.package_id})
            log.info('Deleted package {0} with guid {1}'
                     .format(harvest_object.package_id, harvest_object.guid))

            return True

        if harvest_object.content is None:
            self._save_object_error(
                'Empty content for object %s' % harvest_object.id,
                harvest_object, 'Import')
            return False

        # Get the last harvested object (if any)
        previous_object = model.Session.query(HarvestObject) \
            .filter(HarvestObject.guid == harvest_object.guid) \
            .filter(HarvestObject.current == True) \
            .first()

        # Flag previous object as not current anymore
        if previous_object and not self.force_import:
            previous_object.current = False
            previous_object.add()

        package_dict, dcat_dict = self._get_package_dict(harvest_object)
        if not package_dict:
            return False

        if not package_dict.get('name'):
            package_dict['name'] = \
                self._get_package_name(harvest_object, package_dict['title'])

        # copy across resource ids from the existing dataset, otherwise they'll
        # be recreated with new ids
        if status == 'change':
            existing_dataset = self._get_existing_dataset(harvest_object.guid)
            if existing_dataset:
                copy_across_resource_ids(existing_dataset, package_dict)

        # Allow custom harvesters to modify the package dict before creating
        # or updating the package
        package_dict = self.modify_package_dict(package_dict,
                                                dcat_dict,
                                                harvest_object)
        # Unless already set by an extension, get the owner organization (if
        # any) from the harvest source dataset
        if not package_dict.get('owner_org'):
            source_dataset = model.Package.get(harvest_object.source.id)
            if source_dataset.owner_org:
                package_dict['owner_org'] = source_dataset.owner_org
        # if not package_dict.get('access_rights'):
          #       package_dict['access_rights']='http://publications.europa.eu/resource/authority/access-right/PUBLIC'
        # Flag this object as the current one

        harvest_object.current = True
        harvest_object.add()

        context = {
            'user': self._get_user_name(),
            'return_id_only': True,
            'ignore_auth': True,
        }

        try:
            if status == 'new':
                package_schema = logic.schema.default_create_package_schema()
                context['schema'] = package_schema

                # We need to explicitly provide a package ID
                package_dict['id'] = str(uuid.uuid4())
                package_schema['id'] = [unicode_safe]
                # if package_dict.get('access_rights'):
                  #     if 'access_rights' in package_schema:
                    #       del package_schema['access_rights']
           #      package_dict['access_rights']='http://publications.europa.eu/resource/authority/access-right/PUBLIC'
                # Save reference to the package on the object
                harvest_object.package_id = package_dict['id']
                harvest_object.add()

                # Defer constraints and flush so the dataset can be indexed with
                # the harvest object id (on the after_show hook from the harvester
                # plugin)
                model.Session.execute(
                    'SET CONSTRAINTS harvest_object_package_id_fkey DEFERRED')
                model.Session.flush()

            elif status == 'change':
                package_dict = self.modify_package_dict(package_dict, {}, harvest_object)

                if harvest_object.package_id:
                 package_dict['id'] = harvest_object.package_id
                else: 
                 package_dict['id'] = harvest_object.guid
            if status in ['new']:
                package_schema = logic.schema.default_update_package_schema()
                context['schema'] = package_schema
                action = 'package_create' if status == 'new' else 'package_update'
                message_status = 'Created' if status == 'new' else 'Updated'
                package_id = p.toolkit.get_action(action)(context, package_dict)
                log.info('%s dataset with id %s', message_status, package_id)
            if status in ['change']:
# Check if a dataset with the same guid exists
             existing_dataset = self._get_existing_dataset(harvest_object.guid)
             package_plugin = lib_plugins.lookup_package_plugin(package_dict.get('type', None))
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
                package_dict['name'] = existing_dataset['name']
                package_dict['id'] = existing_dataset['id']
                if 'lod.aci' in package_dict.get('url'):
                            existing_dataset.pop('id',None)
                            del package_schema['identifier']
                            # log.warning('2.3 cancello package_schema per aci')
                if 'access_rights' in existing_dataset:
#                    dataset['access_rights'] = existing_dataset['access_rights']
                  existing_dataset.pop('access_rights',None)
                #  dataset['access_rights']='http://publications.europa.eu/resource/authority/access-right/PUBLIC'
                   #log.debug('in existing dataset è presente access_right')
                if 'applicableLegislation' in existing_dataset:
                  existing_dataset.pop('applicableLegislation',None)
                  existing_dataset.pop('applicable_legislation',None)
                  # dataset['access_rights']='http://publications.europa.eu/resource/authority/access-right/PUBLIC'
                   #log.debug('in existing dataset è presente applicableLegislation')
                if 'applicable_legislation' in existing_dataset:
                  existing_dataset.pop('applicableLegislation',None)
                  existing_dataset.pop('applicable_legislation',None)
                  # dataset['access_rights']='http://publications.europa.eu/resource/authority/access-right/PUBLIC'
                   #log.debug('in existing dataset è presente applicableLegislation')
                if 'hvd_category' in existing_dataset:
                  existing_dataset.pop('hvd_category',None)
                  # dataset['access_rights']='http://publications.europa.eu/resource/authority/access-right/PUBLIC'
                   #log.debug('in existing dataset è presente hvd_category')
                #log.debug('existing_dataset: %s',existing_dataset)
                if not package_dict.get('identifier'):
                    package_dict['identifier']=package_dict['id']

                if not package_dict.get('notes'):
                    package_dict['notes']="N/A"

                if not package_dict.get('theme'):
                    package_dict['theme']="GOVE"
                if not package_dict.get('themes_aggregate'):
                    package_dict['themes_aggregate']='[{"theme": "GOVE", "subthemes": []}]'
                if not package_dict.get('modified'):
                    package_dict['modified']="2024-01-01"
                if not package_dict.get('tags',[]):
                    package_dict['tags']=[{"display_name": "N_A", "id": "b8907f2e-928c-4a83-a24e-51c0c0fc6d39", "name": "N_A", "state": "active"}]
                else:
                    tags=package_dict.get('tags',[])
                    package_dict['tags']=self._clean_tags(tags)
                if not package_dict.get('frequency'):
                    package_dict['frequency']="UNKNOWN"
                if not package_dict.get('publisher_name'):
                  if 'lod.aci' in package_dict.get('url'):
                    package_dict['publisher_name']="ACI"
                    package_dict['publisher_identifier']="aci"
                    package_dict['language']="ITA"
                harvester_tmp_dict = {}

                # check if resources already exist based on their URI
                existing_resources =  existing_dataset.get('resources')
                resource_mapping = {r.get('uri'): r.get('id') for r in existing_resources if r.get('uri')}
                for resource in package_dict.get('resources'):
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
                    harvester.before_update(harvest_object, package_dict, harvester_tmp_dict)
                    package_schema = harvester.update_package_schema_for_update(package_schema)
                    context['schema'] = package_schema
                     #log.warning('package_dict prima di lod.aci %s',package_dict)
                    if 'lod.aci' in package_dict.get('url'):
                                    package_dict.pop('id',None)
                                     #log.warning('2.3.1 cancello package_schema per aci')
                       #dataset['access_rights']='http://publications.europa.eu/resource/authority/access-right/PUBLIC'
                try:
                    if package_dict:
                        package_schema = package_plugin.update_package_schema()
                        for harvester in p.PluginImplementations(IDCATRDFHarvester):
                             package_schema = harvester.update_package_schema_for_update(package_schema)
                        context['schema'] = package_schema
                        if 'lod.aci' in existing_dataset.get('url'):
                             package_dict.pop('extras',None)
                             existing_dataset.pop('extras',None)
                              #log.warning('2.4 cancello package_schema per aci %s',existing_dataset.get('extras')) 
                        if 'access_rights' in package_schema:
 #                            del package_schema['access_rights']
                             #log.warning('2.1 esiste access_rights')
                            package_dict.pop('access_rights',None)
                            package_dict['access_rights']='http://publications.europa.eu/resource/authority/access-right/PUBLIC'
                            existing_dataset['access_rights']='http://publications.europa.eu/resource/authority/access-right/PUBLIC'
                             #log.debug('controllo dataset.get access_right %s',package_dict.get('access_rights'))
                            checkar=package_dict.get('access_rights')
                            if 'http://publications.europa.eu/resource/authority/access-right/PUBLIC' in checkar:
                              #log.warning('2.2 esiste access_rights ma provo a riscriverlo')
# alcuni cataloghi ad oggi espongono gia' access_right                             
                             if package_dict.get('holder_identifier')=='ispra_rm':
                               del package_schema['access_rights']
                             if package_dict.get('publisher_identifier')=='lispa':
                               del package_schema['access_rights']
                             if package_dict.get('publisher_identifier')=='cciaan':
                               del package_schema['access_rights']
                             if package_dict.get('publisher_identifier')=='piersoft':
                               del package_schema['access_rights']
                             package_dict.pop('access_rights',None)
                             existing_dataset['access_rights']='http://publications.europa.eu/resource/authority/access-right/PUBLIC'
                             package_dict['access_rights']='http://publications.europa.eu/resource/authority/access-right/PUBLIC'
                        if 'applicable_legislation' in package_schema:
                            del package_schema['applicable_legislation']
                            # log.warning('2.1 esiste applicable_legislation')
                            package_dict.pop('applicable_legislation',None)
                        if 'hvd_category' in package_schema:
                             #log.warning('2.0  esiste hvd_category')
                            del package_schema['hvd_category']
                        if 'applicableLegislation' in package_schema:
                            del package_schema['applicableLegislation']
                             #log.warning('2.1 esiste applicableLegislation')
                            package_dict.pop('applicableLegislation',None)
 #                            dataset['extras'].append({'key':'applicableLegislation','value':'http://data.europa.eu/eli/reg_impl/2023/138/oj'})
                        # Save reference to the package on the object
                        harvest_object.package_id = package_dict['identifier']
                        harvest_object.add()

                        #p.toolkit.get_action('package_update')(context, dataset)
          #               if package_dict.get('access_rights') !='http://publications.europa.eu/resource/authority/access-right/PUBLIC':
                        #if dataset.get('access_rights'):
            #                   package_dict['access_rights']='http://publications.europa.eu/resource/authority/access-right/PUBLIC'
                        p.toolkit.get_action('package_update')(context, package_dict)
                    else:
                        log.info('Ignoring dataset %s' % existing_dataset['name'])
                        return 'unchanged'
                except p.toolkit.ValidationError as e:
                    self._save_object_error('Update validation Error: %s' % str(e.error_summary), harvest_object, 'Import')
                    return False

                for harvester in p.PluginImplementations(IDCATRDFHarvester):
                    err = harvester.after_update(harvest_object, package_dict, harvester_tmp_dict)

                    if err:
                         self._save_object_error('RDFHarvester plugin error: %s' % err, harvest_object, 'Import')
                         return False

            log.info('Updated dataset %s' % package_dict['name'])

 #                log.info('%s dataset with id %s', message_status, package_id)
        except Exception as e:
            dataset = json.loads(harvest_object.content)
            dataset_name = dataset.get('name', '')

            self._save_object_error('Error importing dataset %s: %r / %s' % (dataset_name, e, traceback.format_exc()), harvest_object, 'Import')
            return False

        finally:
             model.Session.commit()

        return True

def copy_across_resource_ids(existing_dataset, harvested_dataset):
    '''Compare the resources in a dataset existing in the CKAN database with
    the resources in a freshly harvested copy, and for any resources that are
    the same, copy the resource ID into the harvested_dataset dict.
    '''
    # take a copy of the existing_resources so we can remove them when they are
    # matched - we don't want to match them more than once.
    existing_resources_still_to_match = \
        [r for r in existing_dataset.get('resources')]

    # we match resources a number of ways. we'll compute an 'identity' of a
    # resource in both datasets and see if they match.
    # start with the surest way of identifying a resource, before reverting
    # to closest matches.
    resource_identity_functions = [
        lambda r: r['uri'],  # URI is best
        lambda r: (r['url'], r['title'], r['format']),
        lambda r: (r['url'], r['title']),
        lambda r: r['url'],  # same URL is fine if nothing else matches
    ]

    for resource_identity_function in resource_identity_functions:
        # calculate the identities of the existing_resources
        existing_resource_identities = {}
        for r in existing_resources_still_to_match:
            try:
                identity = resource_identity_function(r)
                existing_resource_identities[identity] = r
            except KeyError:
                pass

        # calculate the identities of the harvested_resources
        for resource in harvested_dataset.get('resources'):
            try:
                identity = resource_identity_function(resource)
            except KeyError:
                identity = None
            if identity and identity in existing_resource_identities:
                # we got a match with the existing_resources - copy the id
                matching_existing_resource = \
                    existing_resource_identities[identity]
                resource['id'] = matching_existing_resource['id']
 #                if not 'rights' in resource:
   #                 resource['rights'] ='http://publications.europa.eu/resource/authority/access-right/PUBLIC'
     #            if not 'license' in resource:
       #             resource['license']='https://creativecommons.org/licenses/by/4.0/'
         #           resource['license_type']='https://creativecommons.org/licenses/by/4.0/'
                # make sure we don't match this existing_resource again
                del existing_resource_identities[identity]
                existing_resources_still_to_match.remove(
                    matching_existing_resource)
        if not existing_resources_still_to_match:
            break

