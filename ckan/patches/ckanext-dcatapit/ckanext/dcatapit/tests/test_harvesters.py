import json
import os
import unittest

import pytest
from ckan import model
from ckan.lib.munge import munge_name
from ckan.model import User, Group, Session
from ckanext.dcatapit.tests.utils import (
    LICENSES_FILE,
    load_graph,
    get_voc_file,
)

try:
    from ckan.tests import helpers
except ImportError:
    from ckan.new_tests import helpers

from ckanext.dcat.harvesters.rdf import DCATRDFHarvester
from ckanext.dcatapit.harvesters.ckanharvester import CKANMappingHarvester
from ckanext.dcatapit.model.license import (
    License,
)
from ckanext.dcatapit.commands.vocabulary import load_licenses as load_licenses
from ckanext.harvest.model import HarvestObject
from ckan.tests.helpers import call_action


# @pytest.mark.usefixtures('with_request_context', 'clean_postgis', 'spatial_setup')
@pytest.mark.usefixtures('with_request_context')
class HarvestersTestCase(unittest.TestCase):

    def setUp(self):
        licenses = get_voc_file(LICENSES_FILE)
        load_licenses(load_graph(licenses))
        Session.flush()

        user = User.get('dummy')

        if not user:
            user = call_action('user_create',
                               name='dummy',
                               password='dummydummy',
                               email='dummy@dummy.com')
            user_name = user['name']
        else:
            user_name = user.name
        org = Group.by_name('dummy')
        if org:
            self.org = org.__dict__
        else:
            self.org = call_action('organization_create',
                              context={'user': user_name},
                              name='dummy',
                              identifier='aaaaaa')

    def _create_harvest_source(self, ctx, mock_url, **kwargs):

        source_dict = {
            'title': 'Test Source',
            'name': 'test-source',
            'url': mock_url,
            'source_type': 'dcat_rdf',
        }
        source_dict.update(**kwargs)
        harvest_source = helpers.call_action('harvest_source_create',
                                             context=ctx, **source_dict)
        return harvest_source

    def _create_harvest_job(self, ctx, harvest_source_id):

        harvest_job = helpers.call_action('harvest_job_create',
                                          context=ctx, source_id=harvest_source_id)
        return harvest_job

    def _create_harvest_obj(self, mock_url, **kwargs):
        ctx = {'session': Session,
               'model': model,
               }
        s = self._create_harvest_source(ctx, mock_url, **kwargs)
        Session.flush()
        j = self._create_harvest_job(ctx, s['id'])
        Session.flush()
        h = helpers.call_action('harvest_object_create',
                                context=ctx,
                                job_id=j['id'],
                                source_id=s['id'])
        return h

    def test_ckan_harvester_license(self):

        dataset = {'title': 'some title',
                   'id': 'sometitle',
                   'resources': [
                            {
                                'id': 'resource/1111',
                                'url': 'http://resource/1111',
                                'license_type': 'invalid',
                            },
                       {
                                'id': 'resource/2222',
                                'url': 'http://resource/2222',
                                'license_type': 'https://w3id.org/italia/controlled-vocabulary/licences/A311_GFDL13'
                            }
                   ]
                   }

        data = json.dumps(dataset)
        harvest_dict = self._create_harvest_obj('http://mock/source/', name='testpkg', owner_org=self.org['id'])
        harvest_obj = HarvestObject.get(harvest_dict['id'])
        harvest_obj.content = data
        h = CKANMappingHarvester()
        h.import_stage(harvest_obj)
        Session.flush()

        pkg_dict = helpers.call_action('package_show', context={}, name_or_id='sometitle')
        self.assertTrue(len(pkg_dict['resources']) == 2)

        resources = pkg_dict['resources']
        r = dataset['resources']
        for res in resources:
            if res['id'] == r[0]['id']:
                self.assertEqual(res['license_type'], License.get(License.DEFAULT_LICENSE).uri)
            else:
                self.assertEqual(res['license_type'], r[1]['license_type'])

    @pytest.mark.usefixtures('remove_harvest_stuff', 'remove_dataset_groups')
    def test_remote_orgs(self):
        dataset = {'title': 'some title 2',
                   'owner_id': self.org['id'],
                   'id': 'sometitle2',
                   'name': 'somename',
                   'holder_name': 'test holder',
                   'holder_identifier': 'abcdef',
                   'notes': 'some notes',
                   'modified': '2000-01-01',
                   'theme': 'AGRI',
                   'frequency': 'UNKNOWN',
                   'publisher_name': 'publisher',
                   'identifier': 'identifier2',
                   'publisher_identifier': 'publisher',
                   }

        # no org creation, holder_identifier should be assigned to dataset
        data = json.dumps(dataset)
        harvest_dict = self._create_harvest_obj('http://mock/source/a',
                                                name='testpkg_2',
                                                config=json.dumps({'remote_orgs': 'no-create'}),
                                                owner_org=self.org['id'],
                                                )
        harvest_obj = HarvestObject.get(harvest_dict['id'])
        harvest_obj.content = data

        h = DCATRDFHarvester()
        out = h.import_stage(harvest_obj)
        self.assertTrue(out, harvest_obj.errors)

        pkg = helpers.call_action('package_show', context={}, name_or_id='some-title-2')

        for k in ('holder_name', 'holder_identifier',):
            self.assertEqual(pkg.get(k), dataset[k])

        # check for new org
        dataset.update({'id': 'sometitle3',
                        'name': munge_name('some title 3'),
                        'title': 'some title 3',
                        'holder_name': 'test test holder',
                        'holder_identifier': 'abcdefg',
                        'identifier': 'identifier3',
                        })

        harvest_dict = self._create_harvest_obj('http://mock/source/b',
                                                name='testpkg_3',
                                                config=json.dumps({'remote_orgs': 'create'}),
                                                owner_org=self.org['id'],
                                                )
        harvest_obj = HarvestObject.get(harvest_dict['id'])
        harvest_obj.content = json.dumps(dataset)

        out = h.import_stage(harvest_obj)
        self.assertTrue(out, harvest_obj.errors)
        pkg = helpers.call_action('package_show', context={}, name_or_id='testpkg_3')
        self.assertTrue(out)
        self.assertTrue(isinstance(out, bool))
        pkg = helpers.call_action('package_show', context={}, name_or_id=dataset['name'])

        org_id = pkg['owner_org']

        self.assertIsNotNone(org_id)
        org = helpers.call_action('organization_show', context={}, id=org_id)
        self.assertEqual(org['identifier'], dataset['holder_identifier'])

        # package's holder should be updated with organization's data
        for k in (('holder_name', 'title',), ('holder_identifier', 'identifier',)):
            self.assertEqual(pkg.get(k[0]), org[k[1]])

        # check for existing org

        dataset.update({'id': 'sometitle4',
                        'name': munge_name('some title 4'),
                        'title': 'some title 4',
                        'identifier': 'identifier4',
                        })

        harvest_dict = self._create_harvest_obj('http://mock/source/c',
                                                name='testpkg_4',
                                                config=json.dumps({'remote_orgs': 'create'}),
                                                owner_org=self.org['id'],
                                                )
        harvest_obj = HarvestObject.get(harvest_dict['id'])
        harvest_obj.content = json.dumps(dataset)

        out = h.import_stage(harvest_obj)
        self.assertTrue(out, harvest_obj.errors)
        pkg = helpers.call_action('package_show', context={}, name_or_id='testpkg_4')
        self.assertTrue(isinstance(out, bool))
        pkg = helpers.call_action('package_show', context={}, name_or_id=dataset['name'])

        org_id = pkg['owner_org']

        self.assertIsNotNone(org_id)
        org = helpers.call_action('organization_show', context={}, id=org_id)
        self.assertEqual(org['identifier'], dataset['holder_identifier'])

    @pytest.mark.usefixtures('remove_harvest_stuff', 'remove_dataset_groups')
    def test_ckan_duplicated_name(self):
        dataset0 = {
            'owner_org': self.org['id'],
            'holder_name': 'test holder',
            'holder_identifier': 'abcdef',
            'notes': 'some notes',
            'modified': '2000-01-01',
            'theme': 'AGRI',
            'frequency': 'UNKNOWN',
            'publisher_name': 'publisher',
            'identifier': 'aasdfa',
            'publisher_identifier': 'publisher',
            'resources': [],
            'extras': [],
        }

        dataset1 = {
            'owner_org': self.org['id'],
            'title': 'duplicated title',
            'name': 'duplicated-title',
            'id': 'dummyid'
        }
        dataset1.update(dataset0)
        data = json.dumps(dataset1)

        harvest_dict = self._create_harvest_obj('http://mock/source/', name='dupname1', owner_org=self.org['id'])
        harvest_obj = HarvestObject.get(harvest_dict['id'])
        harvest_obj.content = data
        h = DCATRDFHarvester()
        import_successful = h.import_stage(harvest_obj)
        self.assertTrue(import_successful, harvest_obj.errors)
        Session.flush()
        dataset1['_id'] = harvest_obj.package_id

        dataset2 = {'title': 'duplicated title',
                    'name': 'duplicated-title',
                    'id': 'dummyid2'}

        dataset2.update(dataset0)
        dataset2['identifier'] = 'otherid'
        data = json.dumps(dataset2)

        harvest_dict = self._create_harvest_obj('http://mock/source/', name='dupname2', owner_org=self.org['id'])
        harvest_obj = HarvestObject.get(harvest_dict['id'])
        harvest_obj.content = data
        h = DCATRDFHarvester()
        import_successful = h.import_stage(harvest_obj)
        self.assertTrue(import_successful, harvest_obj.errors)
        Session.flush()
        dataset2['_id'] = harvest_obj.package_id

        # duplicated names are mangled, one should have numeric suffix
        pkg_dict = helpers.call_action('package_show', context={}, name_or_id=dataset1['_id'])
        self.assertEqual(pkg_dict['title'], dataset1['title'])
        self.assertEqual(pkg_dict['name'], 'duplicated-title')

        pkg_dict = helpers.call_action('package_show', context={}, name_or_id=dataset2['_id'])
        self.assertEqual(pkg_dict['title'], dataset2['title'])
        self.assertEqual(pkg_dict['name'], 'duplicated-title1')

