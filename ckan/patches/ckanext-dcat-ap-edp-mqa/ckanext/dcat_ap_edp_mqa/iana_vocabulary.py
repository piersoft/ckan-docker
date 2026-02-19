# The media type is check against the [IANA list](https://www.iana.org/assignments/media-types/media-types.xhtml)
# IANA types can be accessed in [CSV format](https://www.iana.org/assignments/media-types/application.csv)

import os
import requests
import csv
from urllib.parse import urljoin
from typing import Union
from rdflib import URIRef, Literal

import traceback

import logging

log = logging.getLogger(__name__)


class IanaVocabulary:
    __prefix: str = None
    __media_types = {}

    def __init__(
        self,
        media_types,
        prefix,
    ):
        self.__media_types = media_types
        self.__prefix = prefix

    def getUri(self, media_type) -> Union[URIRef, Literal]:
        if isinstance(media_type, URIRef):
            return media_type

        if str(media_type) in self.__media_types:
            return URIRef(urljoin(self.__prefix, str(media_type)))

        log.warn("Unable to properly format value to be complaing with MQA")
        return media_type


class IanaVocabularyBuilder:
    def __init__(self):
        self.__instance = None

    def __call__(
        self,
        urls=[
            "https://www.iana.org/assignments/media-types/application.csv",
            "https://www.iana.org/assignments/media-types/audio.csv",
            "https://www.iana.org/assignments/media-types/font.csv",
            "https://www.iana.org/assignments/media-types/image.csv",
            "https://www.iana.org/assignments/media-types/message.csv",
            "https://www.iana.org/assignments/media-types/model.csv",
            "https://www.iana.org/assignments/media-types/multipart.csv",
            "https://www.iana.org/assignments/media-types/text.csv",
            "https://www.iana.org/assignments/media-types/video.csv",
        ],
        prefix="https://www.iana.org/assignments/media-types/",
        filename="/srv/app/patches/application.csv",
        **_ignored,
    ):
        if not self.__instance:
            # Create local file
            try:
                self._create_local_file(urls, filename)
            except Exception as err:
                traceback.print_exc()
                #print("Using local file")

            media_types = self._read_local_file(filename)
            self.__instance = IanaVocabulary(media_types, prefix)

        return self.__instance

    # Create local file
    def _create_local_file(self, urls, filename):
        tmpfile = f"{filename}.tmp"
        # Start from scratch
        if os.path.isfile(tmpfile):
            os.remove(tmpfile)
        for url in urls:
            #log.info(f"Downloading information from {url}")
            with requests.get(url, stream=True) as r:
                r.raise_for_status()
                with open(tmpfile, "a+b") as f:
                    for line in r.iter_lines():
                        # TODO: Check as some lines as left blank
                        f.write(line + "\n".encode())

        os.rename(tmpfile, filename)

    def _read_local_file(self, filename):
        media_types = []

        # Use always the last stored file
        with open(filename, newline="") as csvfile:
            reader = csv.DictReader(csvfile, delimiter=",")
            for row in reader:
                media_types.append(row["Template"])

        return media_types
