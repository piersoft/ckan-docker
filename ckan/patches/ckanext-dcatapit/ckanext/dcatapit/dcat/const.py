from rdflib import Namespace

DCATAPIT = Namespace('http://dati.gov.it/onto/dcatapit#')
it_namespaces = {
    'dcatapit': DCATAPIT,
}
THEME_BASE_URI = 'http://publications.europa.eu/resource/authority/data-theme/'
LANG_BASE_URI = 'http://publications.europa.eu/resource/authority/language/'
FREQ_BASE_URI = 'http://publications.europa.eu/resource/authority/frequency/'
FORMAT_BASE_URI = 'http://publications.europa.eu/resource/authority/file-type/'
GEO_BASE_URI = 'http://publications.europa.eu/resource/authority/place/'

THEME_CONCEPTS = ('eu_themes', THEME_BASE_URI)
LANG_CONCEPTS = ('languages', LANG_BASE_URI)
GEO_CONCEPTS = ('places', GEO_BASE_URI)
FREQ_CONCEPTS = ('frequencies', FREQ_BASE_URI)
FORMAT_CONCEPTS = ('filetype', FORMAT_BASE_URI)

DEFAULT_VOCABULARY_KEY = 'OP_DATPRO'
DEFAULT_THEME_KEY = DEFAULT_VOCABULARY_KEY
DEFAULT_FORMAT_CODE = DEFAULT_VOCABULARY_KEY
DEFAULT_FREQ_CODE = 'UNKNOWN'

LOCALISED_DICT_NAME_BASE = 'DCATAPIT_MULTILANG_BASE'
LOCALISED_DICT_NAME_RESOURCES = 'DCATAPIT_MULTILANG_RESOURCES'

lang_mapping_ckan_to_voc = {
    'it': 'ITA',
    'de': 'DEU',
    'en': 'ENG',
    'en_GB': 'ENG',
    'fr': 'FRA',
}
lang_mapping_xmllang_to_ckan = {
    'it': 'it',
    'de': 'de',
    # 'en': 'en_GB',
    'en': 'en',
    'fr': 'fr',
}
lang_mapping_ckan_to_xmllang = {
    'en_GB': 'en',
    'uk_UA': 'ua',
    'en_AU': 'en',
    'es_AR': 'es',
}
format_mapping = {
    'HTML': 'HTML_SIMPL',
    'HTML_SIMPL': 'HTML_SIMPL',
    'URL': 'HTML_SIMPL',
    'WMS_SRVC': 'WMS_SRVC',
    'MAP_SRVC': 'WMS_SRVC',
    'CSV': 'CSV',
    'XLS': 'XLS',
    'ODS': 'ODS',
    'JSON': 'JSON',
    'WFS': 'MAP_SRVC',
    'XLSX': 'XLSX',
    'GEOJSON': 'GEOJSON',
    'XML': 'XML',
    'xlsx': 'XLSX',
    'GeoJson': 'GEOJSON',
    'GeoJSON': 'GEOJSON',
    'GEO JSON': 'GEOJSON',
    'geo json': 'GEOJSON',
    'API': 'API',
    'WCS': 'MAP_SRVC',
    'PDF': 'PDF',
    'DOC': 'DOC',
    'xls': 'XLS',
    'RDF': 'RDF_XML',
    'shp': 'SHP',
    'SHP': 'SHP',
    'kml': 'KML',
    'rdf': 'RDF',
    'RDF': 'RDF',
    'OpenData': 'XML',
    'ttl': 'RDF_TURTLE',
    'TTL': 'RDF_TURTLE',
    'kml': 'KML',
    'KML': 'KML',
    'kmz': 'KMZ',
    'KMZ': 'KMZ',
    'JSON_LD': 'JSON_LD',
    'jsonld': 'JSON_LD',
    'JSONLD': 'JSON_LD',
    'TXT': 'TXT',
    'txt': 'TXT',
    'TSV': 'TSV',
    'tsv': 'TSV',
    'gpx': 'GPX',
    'GPX': 'GPX',
    'JSONL': 'JSON',
    'jsonl': 'JSON',
    'n3': 'N3',
    'N3': 'N3',
    'RDFXML': 'RDF_XML',
    'rdfxml': 'RDF_XML',
    'rdf+xml': 'RDF_XML',
    'TURTLE': 'RDF_TURTLE',
    'turtle': 'RDF_TURTLE',
    'RDF_TURTLE': 'RDF_TURTLE',
    'RDF_turtle': 'RDF_TURTLE',
    'dwg': 'DWG',
    'DWG': 'DWG',
    'GPKG': 'GPKG',
    'gpkg': 'GPKG',
    'Documentazione': 'DOC',
    'Link':'HTML',
    'RDF_N_TRIPLES': 'RDF_N_TRIPLES',
    'OWL': 'OWL',
    'RDF_XML': 'RDF_XML',
    'DOCX': 'DOCX',
    'ODT': 'ODT',
    'DBF': 'DBF',
    'dBase': 'DBF',
    'png': 'PNG',
    'PNG': 'PNG',
    'OData': 'XML',
    'BWF': 'BWF',
    'grib': 'GRIB',
    'json_ld': 'JSON_LD',
    'public folder': 'HTML',
    'rtf': 'RTF',
    'web': 'HTML',
    'PARQUET': 'PARQUET',
    'ov2': 'BIN',
    'OV2': 'BIN',
    'FGB': 'SHP',
    'xsd': 'XML',
    'XSD': 'XML',
    'gml': 'GML',
    'GML': 'GML',
    'excel': 'XLSX',
    'WFS_SRVC': 'WFS_SRVC',
    'Moka': 'HTML',
    'MOKA': 'HTML',
    'SDMX': 'SDMX',
    'tif': 'TIFF',
    'TIFF': 'TIFF',
    'ZIP': 'ZIP',  # requires to be more specific, can't infer
}

