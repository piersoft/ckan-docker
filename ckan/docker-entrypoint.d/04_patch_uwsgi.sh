#!/bin/bash
# /docker-entrypoint.d/01_patch_uwsgi.sh
echo "Patching start_ckan.sh per aggiungere EXTRA_UWSGI_OPTS..."

sed -i 's/uwsgi \$UWSGI_OPTS/if [ -n "$EXTRA_UWSGI_OPTS" ]; then UWSGI_OPTS="$UWSGI_OPTS $EXTRA_UWSGI_OPTS"; fi\n    uwsgi $UWSGI_OPTS/' /srv/app/start_ckan.sh

echo "Verifica patch:"
grep -A3 "EXTRA_UWSGI" /srv/app/start_ckan.sh
