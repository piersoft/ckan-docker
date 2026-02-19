import ckan.plugins as plugins

# Provides a stable set of classes and functions that plugins can use safe
# in the knowledge that this interface will remain stable, backward-compatible
# and with clear deprecation guidelines when new versions of CKAN are released.
import ckan.plugins.toolkit as toolkit
from ckan.lib.base import render

from flask import Blueprint, request
from flask import Response
from .ckan_oai_pmh_server_wrapper import CKANOAIPMHServerWrapper

import logging

log = logging.getLogger(__name__)

BLUEPRINT_NAME = "oai_pmh_server"
BLUEPRINT_OAI_ACTION_NAME = "oai_action"
# BATCH_SIZE = 3 # Use of BATCH_SIZE variable for development purposes


def oai_action():
    params = dict(toolkit.request.args)

    # se non c'è verb, mostra la pagina html di esempio
    if "verb" not in params:
        return render("ckanext/oaipmh/oaipmh.html")

    serv = CKANOAIPMHServerWrapper()
    xml = serv.handleRequest(toolkit.request.args)

    # pyoai può tornare bytes o str
    if isinstance(xml, str):
        xml = xml.encode("utf-8")

    return Response(xml, status=200, content_type="text/xml; charset=utf-8")

class OaiPmhServerPlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IConfigurer)
    plugins.implements(plugins.IBlueprint)

    # IConfigurer

    def update_config(self, config_):
        toolkit.add_template_directory(config_, "templates")
        toolkit.add_public_directory(config_, "public")
        toolkit.add_resource("fanstatic", "oai_pmh_server")

    # IBlueprint

    # Use IBlueprint instead of the former IController
    # https://ckan.org/blog/migrating-ckan-28-to-ckan-29
    # https://github.com/ckan/ckan/wiki/Migration-from-Pylons-to-Flask
    # https://medium.com/@pooya.oladazimi/how-to-develop-a-plugin-for-ckan-part-one-45e7ca1f2270
    def get_blueprint(self):
        """Controller to be used for OAI-PMH using Blueprint."""

        blueprint = Blueprint(BLUEPRINT_NAME, self.__module__)
        blueprint.add_url_rule(
            "/oai", BLUEPRINT_OAI_ACTION_NAME, oai_action, methods=["GET"]
        )

        return blueprint
