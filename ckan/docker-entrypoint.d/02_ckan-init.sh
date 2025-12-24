#!/bin/env bash
#if [ $CKAN_INI "ckan.build" != false ]; then
if grep -q "finito" $CKAN_INI; then
echo "Not configuring DCATAPIT already done"
else
 # docker cp managed-schema solr:/var/solr/data/ckan/conf/managed-schema
 # docker cp supervisord.conf ckan:/etc/supervisord.conf

  # Initializes the database
  ckan db init

  # Initialize harvester database
  ckan db upgrade -p harvest

  # Inizialize dcat-ap-it database
  ckan dcatapit initdb

  # Setup multilang database
  ckan multilang initdb

ckan dcatapit load --filename="${APP_DIR}/src/ckanext-dcatapit/vocabularies/languages-filtered.rdf"

ckan dcatapit load --filename="${APP_DIR}/src/ckanext-dcatapit/vocabularies/data-theme-filtered.rdf"

ckan dcatapit load --filename="${APP_DIR}/src/ckanext-dcatapit/vocabularies/places-filtered.rdf"

ckan dcatapit load --filename="${APP_DIR}/src/ckanext-dcatapit/vocabularies/frequencies-filtered.rdf"

ckan dcatapit load --filename="${APP_DIR}/src/ckanext-dcatapit/vocabularies/filetypes-filtered.rdf"

 # curl https://raw.githubusercontent.com/italia/daf-ontologie-vocabolari-controllati/master/VocabolariControllati/territorial-classifications/regions/regions.rdf > regions.rdf
 # paster --plugin=ckanext-dcatapit vocabulary load --filename regions.rdf --name regions --config=/etc/ckan/default/production.ini

ckan dcatapit load --filename "${APP_DIR}/src/ckanext-dcatapit/vocabularies/theme-subtheme-mapping.rdf" --eurovoc "${APP_DIR}/src/ckanext-dcatapit/vocabularies/eurovoc-filtered.rdf"

ckan dcatapit load --filename "${APP_DIR}/src/ckanext-dcatapit/vocabularies/licences.rdf"

#wget "https://raw.githubusercontent.com/italia/daf-ontologie-vocabolari-controllati/master/VocabolariControllati/territorial-classifications/regions/regions.rdf" -O "/tmp/regions.rdf"
ckan dcatapit load --filename "${APP_DIR}/patches/regions.rdf" --name regions

ckan config-tool $CKAN_INI "ckan.build = "finito" "
echo -e "\nCKAN init completed successfully"

fi
if [[ $CKAN__PLUGINS == *"dcatapit_pkg"* ]]; then
   # dcatapit_pkg settings have been configured in the .env file
   # Set API token if necessary
   echo "Set up ckanext.dcat.rdf.profiles in the CKAN config file"
   ckan config-tool $CKAN_INI "ckanext.dcat.rdf.profiles=euro_dcat_ap_2 it_dcat_ap"
   ckan config-tool $CKAN_INI "ckanext.dcat.base_uri=$CKAN_SITE_URL"
   ckan config-tool $CKAN_INI "solr_timeout=500"
fi

ckan config-tool $CKAN_INI "ckan.locale_default = it"
ckan config-tool $CKAN_INI "ckan.locales_offered = it en"
ckan config-tool $CKAN_INI "ckan.auth.create_user_via_web = false"
# da mettere expose_subcatalog True per cataloghi federati. per CKAN singoli lasciare commmentato
#ckan config-tool $CKAN_INI "ckanext.dcat.expose_subcatalogs = True"
ckan config-tool $CKAN_INI "ckanext.dcat.normalize_ckan_format = true"
ckan config-tool $CKAN_INI "geonames.username = demo"
ckan config-tool $CKAN_INI "ckanext.dcat.clean_tags = True"
ckan config-tool $CKAN_INI "ckan.datapusher.url = http://datapusher:8800"
ckan config-tool $CKAN_INI "ckan.datapusher.callback_url_base = http://ckan:5000"




