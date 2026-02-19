# ckanext-dcat-ap-edp-mqa
This extension provides plugins that allow the CKAN to expose metadata using RDF documents serialized using DCAT. It takes [ckanext-dcat](https://github.com/ckan/ckanext-dcat/tree/master) as a basis and extend its profiles to be compliant with DCAT-AP v2.1.1. 

## Profiles
This extension takes [ckanext-dcat](https://github.com/ckan/ckanext-dcat/tree/master) extension as a basis. Therefore the available endpoints are the same. The main difference is the Profile generated in our extension. This profile is `dcat_ap_edp_mqa`, and it offers full compliance with DCAT-AP v2.1.1. 

Use this profile like this:
`https://{ckan-instance-host}/dataset/{dataset-id}.{format}?profiles=dcat_ap_edp_mqa`


## Requirements
- This extension has been developed using CKAN 2.10.1 version.
- It makes use of the well-known [ckanext-dcat](https://github.com/ckan/ckanext-dcat/tree/master).


## Installation - Docker-compose
### Production environment
To install `ckanext-dcat-ap-edp-mqa`:
1. Add the extension to the Dockerfile and add these lines at the end (folder path: `ckan-docker/ckan/`):
    ```bash
    RUN pip3 install -e git+https://github.com/tlmat-unican/ckanext-dcat-ap-edp-mqa.git@main#egg=ckanext-dcat-ap-edp-mqa && \
    pip3 install -r ${APP_DIR}/src/ckanext-dcat-ap-edp-mqa/requirements.txt
    ```
    **Note:**: Make sure to install [ckanext-dcat](https://github.com/ckan/ckanext-dcat/tree/master) too.

2. Add parameters to `.env` file (folder path: `ckan-docker/`):
    ```bash
    CKAN__PLUGINS = "envvars <plugins> structured_data dcat_ap_edp_mqa"
    CKAN__RDF__PROFILES = "dcat_ap_edp_mqa"
    ```
    **Note:**: `<plugins>` is a placeholder for the rest of your plugins.

3. Run your docker-compose file (folder path: `ckan-docker/`):
    ```bash
    docker-compose -f <docker-compose file> build --no-cache 
    docker-compose -f <docker-compose file> up
    ```
    With the `--no-cache` parameter, you are specifying to do not use cache when building the image. This parameter is optional.

### Development environment
To install `ckanext-dcat-ap-edp-mqa`:
1. Clone the GitHub repository (folder path: `ckan-docker/src/`):
    ```bash
    git clone https://github.com/tlmat-unican/ckanext-dcat-ap-edp-mqa.git
    ```
    **Notes**: 
    - if `src/` folder do not exist, create it.
    - make sure to install [ckanext-dcat](https://github.com/ckan/ckanext-dcat/tree/master) too.

2. Add parameters to `.env` file (folder path: `ckan-docker/`):
    ```bash
    CKAN__PLUGINS = "envvars <plugins> structured_data dcat_ap_edp_mqa"
    CKAN__RDF__PROFILES = "dcat_ap_edp_mqa"
    ```
    **Note:**: `<plugins>` is a placeholder for the rest of your plugins.

3. Run your docker-compose file (folder path: `ckan-docker/`):
    ```bash
    docker-compose -f <docker-compose-dev file> up --build
    ```


## Authors
The ckanext-dcat-ap-edp-mqa extension has been written by:
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
| Requests                 | Apache 2.0          |
| rdflib                 | BSD-3-Clause          |
| setuptools          |  MIT          |
