# https://github.com/kangmoesss/ckanext-oaipmh-1/blob/55d1b73fe7da710410bf361d1e1d8b777b15a82a/ckanext/oaipmh/oaipmh_server.py

import json
from datetime import datetime
from lxml import etree
from urllib.parse import urlencode, quote

from oaipmh import common
from oaipmh.common import ResumptionOAIPMH
from oaipmh.error import IdDoesNotExistError

from ckan.logic import get_action
from ckan.model import Package, Session, Group
from ckan.plugins.toolkit import config
from ckan.lib.helpers import url_for

from sqlalchemy import between

import ckanext.oai_pmh_server.external.helpers as helpers
import ckanext.oai_pmh_server.external.utils as utils

from ckanext.dcat.processors import RDFSerializer

import ckanext.oai_pmh_server.plugin as internal_plugin
from .metadata_registry import availableMetadataPrefix, metadataFormats

import logging

log = logging.getLogger(__name__)


default_rdfserializer = RDFSerializer()


class CKANServer(ResumptionOAIPMH):
    """A OAI-PMH implementation class for CKAN."""

    def identify(self):
        """Return identification information for this server."""

        return common.Identify(
            repositoryName=config.get("ckan.site_title", "repository"),
            baseURL=config.get("ckan.site_url", None)
            + url_for(
                f"{internal_plugin.BLUEPRINT_NAME}.{internal_plugin.BLUEPRINT_OAI_ACTION_NAME}"
            ),
            protocolVersion="2.0",
            adminEmails=["support@tlmat.unican.es"],
            earliestDatestamp=utils.get_earliest_datestamp(),
            deletedRecord="no",
            granularity="YYYY-MM-DDThh:mm:ssZ",
            compression=["identity"],
        )

    def _get_json_content(self, js):
        """
        Gets all items from JSON
        :param js: json string
        :return: list of items
        """

        try:
            json_data = json.loads(js)
            json_titles = list()
            for key, value in json_data.iteritems():
                json_titles.append(value)
            return json_titles
        except:
            return [js]

    def _record_for_dataset_dcat(
        self, dataset, spec, profiles=None, compatibility_mode=False
    ):
        """Show a tuple of a header and metadata for this dataset.
        Note that dataset_xml (metadata) returned is just a string containing
        ready rdf xml. This is contrary to the common practice of pyoia's
        getRecord method.
        """

        package = get_action("package_show")({}, {"id": dataset.id})
        # We need to create a new RDF serializer every time, in order to
        # reset the internal graph. Otherwise, using always the same instance,
        # objects will be appended
        rdfserializer = RDFSerializer(profiles, compatibility_mode)
        dataset_xml = rdfserializer.serialize_dataset(package, _format="xml")
        return (
            common.Header(
                "", dataset.id, dataset.metadata_created, [spec], False
            ),
            dataset_xml,
            None,
        )

    """Default when no RDF metadataPrefix is supplied"""

    def _record_for_dataset(self, dataset, spec):
        """Show a tuple of a header and metadata for this dataset."""
        package = get_action("package_show")({}, {"id": dataset.id})

        coverage = []
        temporal_begin = package.get("temporal_coverage_begin", "")
        temporal_end = package.get("temporal_coverage_end", "")

        geographic = package.get("geographic_coverage", "")
        if geographic:
            coverage.extend(geographic.split(","))
        if temporal_begin or temporal_end:
            coverage.append("%s/%s" % (temporal_begin, temporal_end))

        pids = [
            pid.get("id")
            for pid in package.get("pids", {})
            if pid.get("id", False)
        ]
        pids.append(package.get("id"))
        pids.append(
            config.get("ckan.site_url")
            + url_for("dataset.read", id=package["name"])
        )

        meta = {
            "title": self._get_json_content(
                package.get("title", None) or package.get("name")
            ),
            "creator": [
                author["name"]
                for author in helpers.get_authors(package)
                if "name" in author
            ],
            "publisher": [
                agent["name"]
                for agent in (list(helpers.get_distributors(package) or []) + list(helpers.get_contacts(package) or []))
                if "name" in agent
            ],
            "contributor": [
                author["name"]
                for author in helpers.get_contributors(package)
                if "name" in author
            ],
            "identifier": pids,
            "type": ["dataset"],
            "language": [l.strip() for l in package.get("language").split(",")]
            if package.get("language", None)
            else None,
            "description": self._get_json_content(package.get("notes"))
            if package.get("notes", None)
            else None,
            "subject": [tag.get("display_name") for tag in package["tags"]]
            if package.get("tags", None)
            else None,
            "date": [dataset.metadata_created.strftime("%Y-%m-%d")]
            if dataset.metadata_created
            else None,
            "rights": [package["license_title"]]
            if package.get("license_title", None)
            else None,
            "coverage": coverage if coverage else None,
        }

        iters = dataset.extras.items()
        meta = dict(list(meta.items()) + list(iters))
#        meta = dict(iters + meta.items())
        metadata = {}
        # Fixes the bug on having a large dataset being scrambled to individual
        # letters
        for key, value in meta.items():
            if not isinstance(value, list):
                metadata[str(key)] = [value]
            else:
                metadata[str(key)] = value
        return (
            common.Header(
                "", dataset.id, dataset.metadata_created, [spec], False
            ),
            common.Metadata("", metadata),
            None,
        )

    @staticmethod
    def _filter_packages(set, cursor, from_, until, batch_size):
        """Get a part of datasets for "listNN" verbs."""

        packages = []
        group = None
        if not set:
            packages = (
                Session.query(Package)
                .filter(Package.type == "dataset")
                .filter(Package.state == "active")
                .filter(Package.private != True)
            )
            # https://github.com/ckan/ckan/blob/f58c0bcaea2184e18f2bed327873ba38c9bcbfe7/ckan/migration/revision_legacy_code.py
            # It seems that you have to use RevisionTableMappings.instance() L42
            # Another option is using the metadata_modified attribute
            if from_ and not until:
                packages = packages.filter(Package.metadata_modified > from_)
            if until and not from_:
                packages = packages.filter(Package.metadata_modified < until)
            if from_ and until:
                packages = packages.filter(
                    between(Package.metadata_modified, from_, until)
                )
            # packages = packages.order_by(Package.metadata_modified)
            packages = packages.all()
        else:
            group = Group.get(set)
            if group:
                # Note that group.packages never returns private datasets regardless of 'with_private' parameter.
                packages = (
                    group.packages(return_query=True, with_private=False)
                    .filter(Package.type == "dataset")
                    .filter(Package.state == "active")
                )
                if from_ and not until:
                    packages = packages.filter(
                        Package.metadata_modified > from_
                    )
                if until and not from_:
                    packages = packages.filter(
                        Package.metadata_modified < until
                    )
                if from_ and until:
                    packages = packages.filter(
                        between(Package.metadata_modified, from_, until)
                    )
                # packages = packages.order_by(Package.metadata_modified)
                packages = packages.all()

        total_len = len(packages)
        if cursor is not None:
            cursor_end = (
                cursor + batch_size
                if cursor + batch_size < total_len
                else total_len
            )
            packages = packages[cursor:cursor_end]
            
            # Issue with total_len when its multiple of batch_size not returning last package (and and doubling it when batch_size has a difference of +2 with total_len)
            # Workaround: add an extra package only if original_batch_size (= batch_size-1) is equal to the length of packages left
                        # at some point in the code, after inserting a header package, the last package is removed
                        # [internalHeader_package, ..., package(i-1), package(i)] --> [internalHeader_package, ..., package(i-1)], so package(i) is lost
            original_batch_size = batch_size - 1 # For coding purposes, the batch_size adds up one unit to value set in the configuration (.env)
            if original_batch_size ==  len(packages):
                packages.append(packages[-1])

        return packages, group, total_len

    def getRecord(self, metadataPrefix, identifier):
        """Simple getRecord for a dataset."""

        package = Package.get(identifier)
        if not package:
            raise IdDoesNotExistError("No dataset with id %s" % identifier)
        spec = package.name
        if package.owner_org:
            group = Group.get(package.owner_org)
            if group and group.name:
                spec = group.name

        if metadataPrefix in availableMetadataPrefix.keys():
            return self._record_for_dataset_dcat(
                package,
                spec,
                availableMetadataPrefix[metadataPrefix].get("profiles"),
            )
        return self._record_for_dataset(package, spec)

    def listIdentifiers(
        self,
        metadataPrefix=None,
        set=None,
        cursor=None,
        from_=None,
        until=None,
        batch_size=None,
    ):
        """List all identifiers for this repository."""
        data = []
        packages, group, total_len = self._filter_packages(
            set, cursor, from_, until, batch_size
        )
        for package in packages:
            spec = package.name
            if group:
                spec = group.name
            else:
                if package.owner_org:
                    group = Group.get(package.owner_org)
                    if group and group.name:
                        spec = group.name
            data.append(
                common.Header(
                    "", package.id, package.metadata_created, [spec], False
                )
            )

        # Create additional header to include extra resumptionToken information
        data.insert(0, self.generateInternalHeader(total_len))

        return data

    def listMetadataFormats(self, identifier=None):
        """List available metadata formats.
        Example of returned value
        <metadataFormat>
            <metadataPrefix>oai_dc</metadataPrefix>
            <schema>http://www.openarchives.org/OAI/2.0/oai_dc.xsd
            </schema>
            <metadataNamespace>http://www.openarchives.org/OAI/2.0/oai_dc/
            </metadataNamespace>
        </metadataFormat>
        """

        return metadataFormats

    def listRecords(
        self,
        metadataPrefix=None,
        set=None,
        cursor=None,
        from_=None,
        until=None,
        batch_size=None,
    ):
        """Show a selection of records, basically lists all datasets."""
        data = []
        # log.info("cursor: %s | batch_size: %s", cursor, batch_size)
        packages, group, total_len = self._filter_packages(
            set, cursor, from_, until, batch_size
        )
        for package in packages:
            spec = package.name
            if group:
                spec = group.name
            else:
                if package.owner_org:
                    group = Group.get(package.owner_org)
                    if group and group.name:
                        spec = group.name
            if metadataPrefix in availableMetadataPrefix.keys():
                data.append(
                    self._record_for_dataset_dcat(
                        package,
                        spec,
                        availableMetadataPrefix[metadataPrefix].get("profiles"),
                    )
                )
            else:
                data.append(self._record_for_dataset(package, spec))
        
        # Create additional header to include extra resumptionToken information
        data.insert(
            0,
            (
                self.generateInternalHeader(total_len),
                "<empty/>",
                None,
            ),
        )
        return data

    def listSets(self, cursor=None, batch_size=None):
        """List all sets in this repository, where sets are groups."""
        data = []
        groups = Session.query(Group).filter(Group.state == "active")
        total_len = groups.count()
        if cursor is not None:
            cursor_end = (
                cursor + batch_size
                if cursor + batch_size < groups.count()
                else groups.count()
            )
            groups = groups[cursor:cursor_end]
        for dataset in groups:
            data.append((dataset.name, dataset.title, dataset.description))

        # Create additional header to include extra resumptionToken information
        tmp = self.generateInternalHeader(total_len)
        data.insert(0, (tmp.setSpec()[0], tmp.identifier(), ""))

        return data

    def generateInternalHeader(self, total_len):
        metadata = {"completeListSize": total_len}
        oaipmh_server_extra = quote(urlencode(metadata))

        return common.Header(
            "",
            "oaipmh_server_extra for resumptionToken",
            datetime.now(),
            [oaipmh_server_extra],
            False,
        )
