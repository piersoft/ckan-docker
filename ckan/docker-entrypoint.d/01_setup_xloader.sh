#!/bin/bash
   # Xloader settings have been configured in the .env file
   # Set API token if necessary
if grep -q "finito" $CKAN_INI; then
echo "Not configuring token xloader.. already done"
else
      echo "Set up ckan.xloader api_token in the CKAN config file"
      ckan config-tool $CKAN_INI "ckanext.xloader.api_token=$(ckan -c $CKAN_INI user token add ckan_admin xloader | tail -n 1 | tr -d '\t')"
      ckan config-tool $CKAN_INI "ckanext.xloader.jobs_db.uri = postgresql://ckandbuser:ckandbpassword@db/ckandb?sslmode=disable"
fi
