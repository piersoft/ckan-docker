from ckanext.dcat.processors import RDFSerializer

from .external.rdftools import rdf_reader, dcat2rdf_writer

availableMetadataPrefix = {
    "rdf": {
        "profiles": ["euro_dcat_ap"],
        "schema": "http://www.openarchives.org/OAI/2.0/oai_dc.xsd",
        "namespace": "http://www.openarchives.org/OAI/2.0/oai_dc/",
        "reader": rdf_reader,
        "writter": dcat2rdf_writer,
    },
    "dcat": {
        "profiles": ["dcat_ap_edp_mqa"],
        "schema": "http://www.openarchives.org/OAI/2.0/rdf.xsd",
        # "namespace": "http://www.w3.org/ns/dcat#",
        "namespace": "http://www.openarchives.org/OAI/2.0/rdf/",
        "reader": rdf_reader,
        "writter": dcat2rdf_writer,
    },
    "dcat_2.1.0": {
        "profiles": ["euro_dcat_ap_2"],
        "schema": "http://www.openarchives.org/OAI/2.0/oai_dc.xsd",
        "namespace": "http://www.openarchives.org/OAI/2.0/oai_dc/",
        "reader": rdf_reader,
        "writter": dcat2rdf_writer,
    },
    "dcat_1.1.1": {
        "profiles": ["euro_dcat_ap"],
        "schema": "http://www.openarchives.org/OAI/2.0/oai_dc.xsd",
        "namespace": "http://www.openarchives.org/OAI/2.0/oai_dc/",
        "reader": rdf_reader,
        "writter": dcat2rdf_writer,
    },
}

metadataFormats = [
    (
        "oai_dc",
        "http://www.openarchives.org/OAI/2.0/oai_dc.xsd",
        "http://www.openarchives.org/OAI/2.0/oai_dc/",
    ),
        (
        "oai_datacite",
        "http://schema.datacite.org/oai/oai-1.1/oai-1.1.xsd",
        "http://schema.datacite.org/oai/oai-1.1/",
    ),
]
for prefix in availableMetadataPrefix:
    metadataFormat = (
        prefix,
        availableMetadataPrefix[prefix]["schema"],
        availableMetadataPrefix[prefix]["namespace"],
    )
    metadataFormats.append(metadataFormat)
