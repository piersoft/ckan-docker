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
if [[ $CKAN__PLUGINS == *"dcatapit_pkg"* ]]; then
   # dcatapit_pkg settings have been configured in the .env file
   # Set API token if necessary
   echo "Set up ckanext.dcat.rdf.profiles in the CKAN config file"
   ckan config-tool $CKAN_INI "ckanext.dcat.rdf.profiles=euro_dcat_ap it_dcat_ap"
   ckan config-tool $CKAN_INI "ckanext.dcat.base_uri=$CKAN_SITE_URL"
fi

ckan config-tool $CKAN_INI "ckan.locale_default = it"
ckan config-tool $CKAN_INI "ckan.locales_offered = it en"
ckan config-tool $CKAN_INI "ckan.auth.create_user_via_web = false"
ckan config-tool $CKAN_INI "ckanext.dcat.expose_subcatalogs = True"

echo -e "\nCKAN init completed successfully"

fi

if grep -q "finitigruppi" $CKAN_INI; then
echo "Not configuring DCATAPIT already done"
else

ckan config-tool $CKAN_INI "ckanext.dcatapit.theme_group_mapping.file = ${APP_DIR}/patches/theme_to_group.ini"
ckan config-tool $CKAN_INI "ckanext.dcatapit.nonconformant_themes_mapping.file= ${APP_DIR}/patches/topics.json"
ckan config-tool $CKAN_INI "ckanext.dcatapit.theme_group_mapping.add_new_groups= true"
ckan config-tool $CKAN_INI "geonames.username=piersoft"
ckan config-tool $CKAN_INI "ckanext.multilang.localized_resources = true"

  for file in "${APP_DIR}/patches/groups/"*.json; do
   echo "Creating group from file ${file}"
   curl -i -H "X-CKAN-API-Key: $(ckan user token add ckan_admin gruppi | tail -n 1 | tr -d '\t')" -XPOST -d @$file http://0.0.0.0:5000/api/3/action/group_create
  done

ckan config-tool $CKAN_INI "ckan.build_groups = "finitigruppi" "

echo -e "\nCKAN init groups completed successfully"


