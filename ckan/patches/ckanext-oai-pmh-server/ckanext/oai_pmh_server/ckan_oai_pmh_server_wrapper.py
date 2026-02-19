"""OAI-PMH implementation for CKAN datasets and groups for the European Data Portal (edp).
"""

from datetime import datetime, timedelta

import ckan.plugins as p

import oaipmh.metadata as oaimd
import oaipmh.server as oaisrv
from oaipmh import common, metadata, validation, error

from urllib.parse import urlencode, quote, unquote, parse_qs

from .oaipmh_server import CKANServer
from .metadata_registry import availableMetadataPrefix
from .external.rdftools import rdf_reader, dcat2rdf_writer

import logging

log = logging.getLogger(__name__)

from lxml import etree


RESUMPTION_TOKEN_BATCH_SIZE_CONFIG_OPTION= 'ckanext.oai_pmh_server.resumption_token_batch_size'
DEFAULT_RESUMPTION_TOKEN_BATCH_SIZE = 4

RESUMPTION_TOKEN_VALIDITY_CONFIG_OPTION = 'ckanext.oai_pmh_server.resumption_token_validity'
DEFAULT_RESUMPTION_TOKEN_VALIDITY = 60  # seconds

class CKANOAIPMHServerWrapper:
    def __init__(self, resumption_batch_size=0, resumption_validity=0) -> None:
        client = CKANServer()
        metadata_registry = oaimd.MetadataRegistry()
        metadata_registry.registerReader("oai_dc", oaimd.oai_dc_reader)
        metadata_registry.registerWriter("oai_dc", oaisrv.oai_dc_writer)
        for k, v in availableMetadataPrefix.items():
            # TODO: Check how to pass function/dict as value in dictionary
            # metadata_registry.registerReader(k, v.get("reader"))
            metadata_registry.registerReader(k, rdf_reader)
            # metadata_registry.registerWriter(k, v.get("writer"))
            metadata_registry.registerWriter(k, dcat2rdf_writer)

        if resumption_batch_size == 0:
            resumption_batch_size = p.toolkit.asint(p.toolkit.config.get(
                RESUMPTION_TOKEN_BATCH_SIZE_CONFIG_OPTION, DEFAULT_RESUMPTION_TOKEN_BATCH_SIZE
            ))

        if resumption_validity == 0:
            self.resumption_validity = p.toolkit.asint(p.toolkit.config.get(
                RESUMPTION_TOKEN_VALIDITY_CONFIG_OPTION, DEFAULT_RESUMPTION_TOKEN_VALIDITY
            ))
        else:
            self.resumption_validity = resumption_validity

        self.server = oaisrv.BatchingServer(
            client,
            metadata_registry=metadata_registry,
            resumption_batch_size=resumption_batch_size,
        )
        self.params = {}

    # Requires Pylons params
    def handleRequest(self, params):
        # BatchingServer requires a dictionary containing request parameters
        cleaned_params = self.cleanParams(params)
    
        return self.server.handleRequest(cleaned_params)

    def validateResumptionToken(self, resumptionToken):
        resumptionToken = parse_qs(unquote(resumptionToken))

        # Remove or validate informative parameters (completeListSize)
        resumptionToken.pop("completeListSize", None)

        if self.resumption_validity > 0:
            # Validate expirationDate
            expirationDate = resumptionToken.pop("expirationDate", None)
            try:
                expirationDate = expirationDate[0]
                expirationDate = datetime.fromtimestamp(int(expirationDate))
                # expirationDate = datetime.fromisoformat(expirationDate)

            except ValueError:
                raise error.BadArgumentError(
                    "expirationDate is not in a valid format"
                )

            currentDate = datetime.now().replace(microsecond=0)        
            if expirationDate < currentDate:
                raise error.BadArgumentError(
                    "expirationDate is in the past"
                )

        # Get first value for each key
        resumptionToken = {key:value[0] for key, value in resumptionToken.items()}

        return urlencode(resumptionToken)
        # return quote(resumptionToken)

    def cleanParams(self, params):
        # Simple way is flaten
        # Create dict with first entry for each key
        p = params.to_dict(flat=True)

        if p.get("resumptionToken", None):
            p["resumptionToken"] = self.validateResumptionToken(
                p["resumptionToken"]
            )
            ## WARNING: resumptionToken is an exclusive argument --> http://www.openarchives.org/OAI/openarchivesprotocol.html#ListRecords
            ## This is a workaround to be compliant with the current implementation of the importing-oaipmh (https://gitlab.com/dataeuropa/harvester/importing-oaipmh)
            p = { "verb": p["verb"], "resumptionToken": p["resumptionToken"] }
        return p


    def handleResponse(self, res):
        root = etree.fromstring(res)

        # Not the optimal way but it is an idea to pass values back without
        # having to touch pyoai library
        e_verb = root.xpath(
            "//oai:ListRecords|//oai:ListIdentifiers|//oai:ListSets",
            namespaces={"oai": oaisrv.NS_OAIPMH},
        )
        # e_verb = root.xpath(
        #     "//*[local-name() = 'ListRecors']|//*[local-name() = 'LisIdentifiers']"
        # )
        # e_verb = root.find(oaisrv.nsoai("ListRecords")) or root.find(
        #     oaisrv.nsoai("ListIdentifiers") or None
        # )
        if len(e_verb) == 0:
            # Nothing to be done if not ListRecords or Identifiers (for the moment)
            return res

        # Get first element in the list of verb elements
        e_verb = e_verb[0]
        
        # Always retrieve the additional record added
        e_added = e_verb[0]

        # Search for spec element (we intentionally modified its behaviour)
        expr = "//*[local-name() = $name]"
        # xpath returns a list
        e_nt = e_added.xpath(expr, name="setSpec")
        if e_nt is not None:
            nt = qsToSingleDict(e_nt[0].text)

        e_verb.remove(e_added)

        # Retrieve resumptionToken
        e_resumptionToken = e_verb.find(oaisrv.nsoai("resumptionToken"))
        if e_resumptionToken is not None:
            token, cursor = oaisrv.decodeResumptionToken(e_resumptionToken.text)
            # Create new resumptionToken
            # https://stackoverflow.com/a/26853961/422680
            token = {**token, **nt}

            # Add expirationDate to resumptionToken
            # Decide wether to use ISO8601 or timestamp
            if self.resumption_validity > 0:
                d = datetime.now().replace(microsecond=0) + timedelta(seconds=self.resumption_validity)
                expirationDate = int(round(d.timestamp()))
                # expirationDate = d.isoformat(sep='T')
                token["expirationDate"] = expirationDate

            new_resumptionToken = oaisrv.encodeResumptionToken(token, cursor)
            e_new_resumptionToken = etree.Element(
                oaisrv.nsoai("resumptionToken")
            )
            e_new_resumptionToken.text = new_resumptionToken
            e_new_resumptionToken.attrib['cursor'] = str(cursor).encode('utf-8')
            e_new_resumptionToken.attrib['completeListSize'] = token['completeListSize']
            e_verb.replace(e_resumptionToken, e_new_resumptionToken)

        res = etree.tostring(root)
        return res


# https://stackoverflow.com/a/1024164/422680
def qsToSingleDict(qs):
    qsdata = str(unquote(qs))
    return dict(
        (k, v if len(v) > 1 else v[0]) for k, v in parse_qs(qsdata).items()
    )
    # The above is similar to this
    # for key, value in qsdata.items():
    #   if len(v) > 1:
    #     value = value[0]
