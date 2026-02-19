# ckanext-oai-pmh-server
This extension provides plugins that allow the CKAN to expose the metadata stored to be consumed using the [OAI-PMH protocol](https://www.openarchives.org/OAI/openarchivesprotocol.html). Hence, this plugin allow the descriptions (metadata) of the packages (datasets) stored in the CKAN portal to be available and accessible for harvesting processes.

## Endpoints
This plugin enable all the endpoints described in the OAI-PMH [documentation](https://www.openarchives.org/OAI/openarchivesprotocol.html). These are:
- `/oai?verb=Identify`: used to retrieve information about the CKAN instance.
- `/oai?verb=ListMetadataFormats&identifier=<item_id>`: used to retrieve the metadata formats available. It makes use of other aditional and optional argument: identifier. This parameter specifies the unique identifier of the item for which the available formats are being requested. Some common responses are: `oai_dc` or `dcat`.
- `/oai?verb=GetRecord&identifier=<dataset_id>&metadataPrefix=<metadata_prefix>`: used to retrieve the metadata from an individual dataset. It makes use of two other parameters: `identifier` and `metadataPrefix`. The first one, `identifier`, specifies the unique identifier of the CKAN dataset, while the second one, `metadataPrefix` determines the format in which the metadata should be represented. The available options for this last parameter can be obtained through the `ListMetadataFormats` request.
- `/oai?verb=ListRecords&metadataPrefix=<metadata_prefix>`: used to harvest datasets from a CKAN instance. It makes use of several additional arguments: `from`, `until`, `set`, `resumptionToken` and `metadataPrefix`. The first three are optional and used for selective harvesting. The fourth one, `resumptionToken`, is used for pagination and, the last argument, `metadataPrefix`, has been described in the previous request.
- `/oai?verb=ListIdentifiers&metadataPrefix=<metadata_prefix>`: is an abbreviated form of `ListRecords`, retrieving only headers rather than datasets. It makes use of the same additional arguments as its extended version: `from`, `until`, `set`, `resumptionToken` and `metadataPrefix`.
- `/oai?verb=ListSets`: used to retrieve the organizations structure of the CKAN instance. It makes use of one additional argument: `resumptionToken`. This parameter is used for pagination.

This extension is configurated to used the `dcat_ap_edp_mqa` profile described in [ckanext-dcat-ap-edp-mqa](https://github.com/tlmat-unican/ckanext-dcat-ap-edp-mqa/tree/main) when using `metadataPrefix=dcat` (this can be seen in `metadata_registry.py` file). However, this is customisable. You can either use another profile or even develop your own, like it is done in the [ckanext-dcat-ap-edp-mqa](https://github.com/tlmat-unican/ckanext-dcat-ap-edp-mqa/tree/main) extension and use it here.


## Requirements
- This extension has been developed using CKAN 2.10.1 version.
- It makes use of [ckanext-dcat-ap-edp-mqa](https://github.com/tlmat-unican/ckanext-dcat-ap-edp-mqa/tree/main).


## Installation - Docker-compose
### Production environment
To install `ckanext-oai-pmh-server`:
1. Add the extension to the Dockerfile and add these lines at the end (folder path: `ckan-docker/ckan/`):
    ```bash
    RUN pip3 install -e git+https://github.com/tlmat-unican/ckanext-oai-pmh-server.git@main#egg=ckanext-oai-pmh-server && \
    pip3 install -r ${APP_DIR}/src/ckanext-oai-pmh-server/requirements.txt
    ```
    **Note**: Make sure to install [ckanext-dcat-ap-edp-mqa](https://github.com/tlmat-unican/ckanext-dcat-ap-edp-mqa/tree/main) too.

2. Add parameters to `.env` file(folder path: `ckan-docker/`):
    ```bash
    CKAN__PLUGINS = "envvars <plugins> oai_pmh_server"
    CKANEXT__OAI_PMH_SERVER__RESUMPTION_TOKEN_BATCH_SIZE = <set_value>
    CKANEXT__OAI_PMH_SERVER__RESUMPTION_TOKEN_VALIDITY = <set_value> # seconds
    ```
    **Notes**: 
    - `<plugins>` is a placeholder for the rest of your plugins.
    - change `<set_value>` to whatever you want.

3. Run your docker-compose file (folder path: `ckan-docker/`):
    ```bash
    docker-compose -f <docker-compose file> build --no-cache 
    docker-compose -f <docker-compose file> up
    ```
    With the `--no-cache` parameter, you are specifying to do not use cache when building the image. This parameter is optional.

### Development environment
To install `ckanext-oai-pmh-server`:
1. Clone the GitHub repository(folder path: `ckan-docker/src/`):
    ```bash
    git clone https://github.com/tlmat-unican/ckanext-oai-pmh-server.git
    ```
    **Notes**: 
    - if `src/` folder does not exist, create it.
    - make sure to install [ckanext-dcat-ap-edp-mqa](https://github.com/tlmat-unican/ckanext-dcat-ap-edp-mqa/tree/main) too.

2. Add parameters to `.env` file (folder path: `ckan-docker/`):
    ```bash
    CKAN__PLUGINS = "envvars <plugins> oai_pmh_server"
    CKANEXT__OAI_PMH_SERVER__RESUMPTION_TOKEN_BATCH_SIZE = <set_value>
    CKANEXT__OAI_PMH_SERVER__RESUMPTION_TOKEN_VALIDITY = <set_value> # seconds
    ```
    **Notes**: 
    - `<plugins>` is a placeholder for the rest of your plugins.
    - change `<set_value>` to whatever you want.

3. Run your docker-compose file (folder path: `ckan-docker/`):
    ```bash
    docker-compose -f <docker-compose-dev file> up --build
    ```


## Authors
The ckanext-oai-pmh-server extension has been written by:
- [Laura Martín](https://github.com/lauramartingonzalezzz)
- [Jorge Lanza](https://github.com/jlanza)
- [Víctor González](https://github.com/vgonzalez7)
- [Juan Ramón Santana](https://github.com/juanrasantana)
- [Pablo Sotres](https://github.com/psotres)
- [Luis Sánchez](https://github.com/sanchezgl)


## Acknowledgement
This work was supported by the European Commission CEF Programme by means of the project SALTED "Situation-Aware Linked heTerogeneous Enriched Data" under the Action Number 2020-EU-IA-0274.


## License
This material is licensed under the GNU Lesser General Public License v3.0 whose full text may be found at the *LICENSE* file.

It mainly makes use of the following libraries and frameworks (dependencies of dependencies have been omitted):

| Library / Framework |   License    |
|---------------------|--------------|
| Flask                 | Apache 2.0          |
| iso639                 | MIT          |
| lxml                 | BSD-3-Clause          |
| setuptools                 | MIT          |
| SQLAlchemy          |  MIT          |
| pyoai          |  [License](https://github.com/infrae/pyoai/blob/4800af53b2ed096a0305eed1d6710138a65eabcd/LICENSE.txt)          |
