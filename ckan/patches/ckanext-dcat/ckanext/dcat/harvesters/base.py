import ssl
import urllib3
import requests
from urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)
ssl._create_default_https_context = ssl._create_unverified_context
from urllib3.util.ssl_ import create_urllib3_context
from requests.adapters import HTTPAdapter

class CustomSslContextHttpAdapter(HTTPAdapter):
        """"Transport adapter" that allows us to use a custom ssl context object with the requests."""
        def init_poolmanager(self, connections, maxsize, block=False):
            ctx = create_urllib3_context()
            ctx.load_default_certs()
            ctx.options |= 0x4  # ssl.OP_LEGACY_SERVER_CONNECT
            self.poolmanager = urllib3.PoolManager(ssl_context=ctx)



import os
import logging

import requests
import rdflib

from ckan import plugins as p
from ckan import model

from ckantoolkit import config
import ckan.plugins.toolkit as toolkit

from ckanext.harvest.harvesters import HarvesterBase
from ckanext.harvest.model import HarvestObject

from ckanext.dcat.interfaces import IDCATRDFHarvester


log = logging.getLogger(__name__)


class DCATHarvester(HarvesterBase):

    DEFAULT_MAX_FILE_SIZE_MB = 80
    CHUNK_SIZE = 1024 * 512

    force_import = False

    def _get_content_and_type(self, url, harvest_job, page=1,
                              content_type=None):
        '''
        Gets the content and type of the given url.

        :param url: a web url (starting with http) or a local path
        :param harvest_job: the job, used for error reporting
        :param page: adds paging to the url
        :param content_type: will be returned as type
        :return: a tuple containing the content and content-type
        '''
        url = url.replace("https://dati.regione.calabria.it", "http://dati.regione.calabria.it/opendata")
        url = url.replace("https://opendata.uniba.it", "http://opendata.uniba.it")
        url = url.replace("https://dati.regione.campania.it/", "http://dati.regione.campania.it/")
                                      
        if not url.lower().startswith('http'):
            # Check local file
            if os.path.exists(url):
                with open(url, 'r') as f:
                    content = f.read()
                content_type = content_type or rdflib.util.guess_format(url)
                return content, content_type
            else:
                self._save_gather_error('Could not get content for this url',
                                        harvest_job)
                return None, None

        try:

            if page > 1:
                url = url + '&' if '?' in url else url + '?'
                url = url + 'page={0}'.format(page)

            log.debug('Getting file %s', url)

            # get the `requests` session object
            session = requests.Session()
            session.mount(url, CustomSslContextHttpAdapter())
         
            for harvester in p.PluginImplementations(IDCATRDFHarvester):
                session = harvester.update_session(session)

            # first we try a HEAD request which may not be supported
            did_get = False
            r = session.head(url)

            if r.status_code == 405 or r.status_code == 400:
                r = session.get(url, stream=True, verify=False)
                did_get = True
            r.raise_for_status()

            max_file_size = 1024 * 1024 * toolkit.asint(config.get('ckanext.dcat.max_file_size', self.DEFAULT_MAX_FILE_SIZE_MB))
            cl = r.headers.get('content-length')
            if cl and int(cl) > max_file_size:
                msg = '''Remote file is too big. Allowed
                    file size: {allowed}, Content-Length: {actual}.'''.format(
                    allowed=max_file_size, actual=cl)
                self._save_gather_error(msg, harvest_job)
                return None, None

            if not did_get:
                r = session.get(url, stream=True, verify=False)

            length = 0
            content = b''
            for chunk in r.iter_content(chunk_size=self.CHUNK_SIZE):
                content = content + chunk

                length += len(chunk)

                if length >= max_file_size:
                    self._save_gather_error('Remote file is too big.',
                                            harvest_job)
                    return None, None

            content = content.decode('utf-8')

            if content_type is None and r.headers.get('content-type'):
                content_type = r.headers.get('content-type').split(";", 1)[0]
            content_type=content_type.replace('octet-stream','rdf+xml')
            content_type=content_type.replace('text/plain','application/rdf+xml')
            log.debug('content-type in base.py: %s',content_type)
            return content, content_type

        except requests.exceptions.HTTPError as error:
            if page > 1 and error.response.status_code == 404:
                # We want to catch these ones later on
                raise

            msg = 'Could not get content from %s. Server responded with %s %s'\
                % (url, error.response.status_code, error.response.reason)
            self._save_gather_error(msg, harvest_job)
            return None, None
        except requests.exceptions.ConnectionError as error:
            msg = '''Could not get content from %s because a
                                connection error occurred. %s''' % (url, error)
            self._save_gather_error(msg, harvest_job)
            return None, None
        except requests.exceptions.Timeout as error:
            msg = 'Could not get content from %s because the connection timed'\
                ' out.' % url
            self._save_gather_error(msg, harvest_job)
            return None, None

    def _get_object_extra(self, harvest_object, key):
        '''
        Helper function for retrieving the value from a harvest object extra,
        given the key
        '''
        for extra in harvest_object.extras:
            if extra.key == key:
                if 'file-type' in extra.value:
                 log.debug('prova disperata in _get_object_extra')
                 extra.value=extra.value.replace('http://publications.europa.eu/resource/authority/file-type/','')
                return extra.value
        return None

    def _get_package_name(self, harvest_object, title):

        package = harvest_object.package
        if package is None or package.title != title:
            name = self._gen_new_name(title)
            if not name:
                raise Exception(
                    'Could not generate a unique name from the title or the '
                    'GUID. Please choose a more unique title.')
        else:
            name = package.name

        return name

    def get_original_url(self, harvest_object_id):
        obj = model.Session.query(HarvestObject). \
            filter(HarvestObject.id == harvest_object_id).\
            first()
        if obj:
            return obj.source.url
        return None

    def _read_datasets_from_db(self, guid):
        '''
        Returns a database result of datasets matching the given guid.
        '''

        datasets = model.Session.query(model.Package.id) \
                                .join(model.PackageExtra) \
                                .filter(model.PackageExtra.key == 'guid') \
                                .filter(model.PackageExtra.value == guid) \
                                .filter(model.Package.state == 'active') \
                                .all()
        return datasets

    def _get_existing_dataset(self, guid):
        '''
        Checks if a dataset with a certain guid extra already exists

        Returns a dict as the ones returned by package_show
        '''

        datasets = self._read_datasets_from_db(guid)

        if not datasets:
            return None
        elif len(datasets) > 1:
            log.error('Found more than one dataset with the same guid: {0}'
                      .format(guid))

        return p.toolkit.get_action('package_show')({}, {'id': datasets[0][0]})

    # Start hooks

    def modify_package_dict(self, package_dict, dcat_dict, harvest_object):
        '''
            Allows custom harvesters to modify the package dict before
            creating or updating the actual package.
        '''
        return package_dict

    # End hooks
