#FROM postgres:12-alpine
#se si usa PG16 serve ?sslmode=disable nel docker yml

FROM postgres:16-alpine 
# Include extra setup scripts (eg datastore)
COPY --chown=postgres:postgres docker-entrypoint-initdb.d /docker-entrypoint-initdb.d
