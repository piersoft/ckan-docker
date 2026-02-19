import ckan.plugins as plugins
import ckan.plugins.toolkit as toolkit

# from ckan.common import config

from ckanext.dcat.profiles import DISTRIBUTION_LICENSE_FALLBACK_CONFIG


class DcatApEdpMqaPlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IConfigurer)

    # IConfigurer

    def update_config(self, config_):
        toolkit.add_template_directory(config_, "templates")
        toolkit.add_public_directory(config_, "public")
        toolkit.add_resource("fanstatic", "dcat_ap_edp_mqa")

        # Inherit license from the dataset as fallback in distribution
        # From ckanext-dcat -> profiles.py
        # DISTRIBUTION_LICENSE_FALLBACK_CONFIG = 'ckanext.dcat.resource.inherit.license'
        # https://github.com/ckan/ckanext-dcat/blob/master/README.md#inherit-license-from-the-dataset-as-fallback-in-distributions
        config_.update({DISTRIBUTION_LICENSE_FALLBACK_CONFIG: "True"})
        # config_.update({"ckanext.dcat.resource.inherit.license": "true"})