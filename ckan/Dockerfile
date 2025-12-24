FROM ckan/ckan-base:2.10.3

# Install any extensions needed by your CKAN instance
# See Dockerfile.dev for more details and examples
### Harvester ###
#RUN pip3 install -e 'git+https://github.com/ckan/ckanext-harvest.git@master#egg=ckanext-harvest' && \
COPY patches/ckanext-harvest ${APP_DIR}/src/ckanext-harvest
RUN    pip3 install -e ${APP_DIR}/src/ckanext-harvest/
RUN    pip3 install -r ${APP_DIR}/src/ckanext-harvest/requirements.txt
# will also require gather_consumer and fetch_consumer processes running (please see https://github.com/ckan/ckanext-harvest)

### Scheming ###
#RUN  pip3 install -e 'git+https://github.com/ckan/ckanext-scheming.git@master#egg=ckanext-scheming'

### Pages ###
#RUN  pip3 install -e git+https://github.com/ckan/ckanext-pages.git#egg=ckanext-pages

RUN pip3 install pylons
RUN pip3 install routes

# Install ckanext-dcat HVD
#RUN  pip3 install -e git+https://github.com/ckan/ckanext-dcat.git@56-tmp#egg=ckanext-dcat && \
COPY patches/ckanext-dcat ${APP_DIR}/src/ckanext-dcat
RUN     pip3 install -e ${APP_DIR}/src/ckanext-dcat/
RUN     pip3 install -r ${APP_DIR}/src/ckanext-dcat/requirements.txt

# Install ckanext-dcatapit
COPY patches/ckanext-dcatapit ${APP_DIR}/src/ckanext-dcatapit
RUN     pip3 install -e ${APP_DIR}/src/ckanext-dcatapit/

# Install ckanext-multilang
RUN  pip3 install -e git+https://github.com/geosolutions-it/ckanext-multilang.git@master#egg=ckanext-multilang  && \
     pip3 install -e ${APP_DIR}/src/ckanext-multilang/

# DCATAPIT theme to group mapping file
COPY patches/theme_to_group.ini "${APP_DIR}/patches/theme_to_group.ini"
RUN chmod 666 "${APP_DIR}/patches/theme_to_group.ini"

# CKAN group to DCATAPIT theme mapping file
COPY patches/topics.json "${APP_DIR}/patches/topics.json"
RUN chmod 666 "${APP_DIR}/patches/topics.json"

# CKAN group to DCATAPIT theme mapping file
COPY patches/regions.rdf "${APP_DIR}/patches/regions.rdf"
RUN chmod 666 "${APP_DIR}/patches/topics.json"

COPY patches/model_dictize.py ${APP_DIR}/src/ckan/ckan/lib/dictization/model_dictize.py
COPY patches/base.py ${APP_DIR}/src/ckan/ckan/lib/base.py

#patch per landing page . elimina il campo Origine nel form di editing del dataset
COPY patches/package_metadata_fields.html ${APP_DIR}/src/ckan/ckan/templates/package/snippets/package_metadata_fields.html

#COPY patches/package_basic_fields.html ${APP_DIR}/src/ckan/ckan/templates/package/snippets
#COPY patches/jeoquery.js ${APP_DIR}/src/ckanext-dcatapit/ckanext/dcatapit/fanstatic/jeoquery.js
COPY patches/xmlrpc.py /usr/lib/python3.10/site-packages/pylons/controllers/xmlrpc.py
COPY patches/jsonrpc.py /usr/lib/python3.10/site-packages/pylons/controllers/jsonrpc.py
COPY patches/core.py /usr/lib/python3.10/site-packages/pylons/controllers/core.py
COPY patches/supervisord.conf /etc/supervisord.conf
COPY patches/sprite-resource-icons.png "${APP_DIR}/src/ckan/ckan/public/base/images"
#COPY patches/ckanharvester.py ${APP_DIR}/src/ckanext-harvest/ckanext/harvest/harvesters/ckanharvester.py
# patch per user not auth to show in harvesting
COPY patches/__init__.py ${APP_DIR}/src/ckan/ckan/logic/__init__.py
# patch per avere il rating dal portale europeo dei dati aperti. Decommentare se si vuole il punteggio
#COPY patches/read.html "${APP_DIR}/src/ckan/ckan/templates/package/read.html"

# Min length resource = 5
COPY patches/validators.py ${APP_DIR}/src/ckan/ckan/logic/validators.py

# Copy custom initialization scripts
COPY docker-entrypoint.d/* /docker-entrypoint.d/

COPY patches/groups ${APP_DIR}/patches/groups


# Apply any patches needed to CKAN core or any of the built extensions (not the
# runtime mounted ones)
COPY patches ${APP_DIR}/patches

RUN for d in $APP_DIR/patches/*; do \
        if [ -d $d ]; then \
            for f in `ls $d/*.patch | sort -g`; do \
                cd $SRC_DIR/`basename "$d"` && echo "$0: Applying patch $f to $SRC_DIR/`basename $d`"; patch -p1 < "$f" ; \
            done ; \
        fi ; \
    done
RUN mkdir -p /var/run /var/log /etc/supervisord.d \
 && chown -R ckan:ckan /var/run /var/log
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisord.conf"]
RUN apk add supervisor
RUN apk add nano
