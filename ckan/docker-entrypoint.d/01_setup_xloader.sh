#!/bin/bash
   # Xloader settings have been configured in the .env file
   # Set API token if necessary
if grep -q "finito" $CKAN_INI; then
echo "Not configuring token xloader.. already done"
else
      echo "Set up ckan.xloader api_token in the CKAN config file"
      ckan config-tool $CKAN_INI "ckanext.xloader.api_token=$(ckan -c $CKAN_INI user token add ckan_admin xloader | tail -n 1 | tr -d '\t')"
      ckan config-tool $CKAN_INI "ckanext.xloader.jobs_db.uri=${CKAN_SQLALCHEMY_URL}"
      ckan config-tool $CKAN_INI "ckan.datastore.write_url=${CKAN_DATASTORE_WRITE_URL}"
      ckan config-tool $CKAN_INI "ckan.datastore.read_url=${CKAN_DATASTORE_READ_URL}"
      ckan config-tool $CKAN_INI "ckanext.xloader.site_url = http://ckan:5000"
fi

# URL base dell'OAI-PMH
ckan config-tool $CKAN_INI "ckan.oaipmh.base_url = https://192.168.0.93:8443/oai"

# Record set, se vuoi usare filtri o categorie
ckan config-tool $CKAN_INI "ckan.oaipmh.sets = dataset_authority, custom_tag_set"

# Metadata formats (oai_dc è standard)
ckan config-tool $CKAN_INI "ckan.oaipmh.metadata_formats = oai_dc"

# Mapping dei campi (se aggiungi altri profili)
ckan config-tool $CKAN_INI "ckan.oaipmh.dc_element_map = title,description,keyword,publisher,identifier"
ckan config-tool $CKAN_INI "ckanext.dcat.resource.inherit.license = True"
