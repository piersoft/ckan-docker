#!/bin/bash

   # Datapusher settings have been configured in the .env file
   # Set API token if necessary

   ckan config-tool $CKAN_INI "ckan.datapusher.api_token=$(ckan -c $CKAN_INI user token add ckan_admin datapusher | tail -n 1 | tr -d '\t')"
