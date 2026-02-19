# The format vocabulary can be found in the data.europa.eu [GitLab repository](https://gitlab.com/european-data-portal/edp-vocabularies).

import os
from urllib.parse import urljoin
from typing import Union
from rdflib import Graph, URIRef, Literal

import traceback

import logging

log = logging.getLogger(__name__)


class DataEuropaVocabulary:
    __prefix: str = None
    __file_types = []

    def __init__(
        self,
        file_types,
        prefix,
    ):
        self.__file_types = file_types
        self.__prefix = prefix

    def getUri(self, media_type) -> Union[URIRef, Literal]:
        if isinstance(media_type, URIRef):
            return media_type

        if str(media_type) in self.__file_types:
            return URIRef(urljoin(self.__prefix, str(media_type)))

        # log.warn("Unable to properly format value to be complaing with MQA")
        return media_type


class DataEuropaVocabularyBuilder:
    def __init__(self):
        self.__instance = None

    def __call__(
        self,
        urls=[
            "https://gitlab.com/dataeuropa/vocabularies/-/raw/master/piveau-non-proprietary-format.rdf",
            "https://gitlab.com/dataeuropa/vocabularies/-/raw/master/piveau-machine-readable-format.rdf",
        ],
        prefix="http://publications.europa.eu/resource/authority/file-type/",
        filename="/srv/app/patches/edp-vocabularies.rdf”",
    ):
        if not self.__instance:
            # Create local file
            try:
                self._create_local_file(urls, filename)
            except Exception as err:
                traceback.print_exc()
                # log.warn("Using local file")

            file_types = self._read_local_file(filename)
            self.__instance = DataEuropaVocabulary(file_types, prefix)

        return self.__instance

    def _create_local_file(self, urls, filename):
        g = Graph()
        for url in urls:
            # log.info(f"Downloading information from {url}")
            g.parse(format="xml", location=url)

        g.serialize(format="pretty-xml", destination=filename)

    def _read_local_file(self, filename):
        g = Graph()
        g.parse(filename)

        # for s, p, o in g:
        file_types = []
        for s in g.subjects():
            file_types.append(os.path.split(s)[1])

        return list(set(file_types))
