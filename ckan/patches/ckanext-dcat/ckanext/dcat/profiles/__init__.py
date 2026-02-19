from .base import RDFProfile, CleanedURIRef
from .base import (
    RDF,
    XSD,
    SKOS,
    RDFS,
    DCAT,
    DCATAP,
    DCT,
    ADMS,
    VCARD,
    FOAF,
    SCHEMA,
    LOCN,
    GSP,
    OWL,
    SPDX,
    GEOJSON_IMT,
)

from .euro_dcat_ap import EuropeanDCATAPProfile
from .euro_dcat_ap_2 import EuropeanDCATAP2Profile
from .schemaorg import SchemaOrgProfile

DISTRIBUTION_LICENSE_FALLBACK_CONFIG = 'ckanext.dcat.resource.inherit.license'
