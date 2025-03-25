import logging
from ckan.common import _
from ckan.plugins import PluginImplementations

from ckanext.dcatapit.interfaces import ICustomSchema

FIELD_THEMES_AGGREGATE = 'themes_aggregate'

log = logging.getLogger(__name__)

def get_custom_config_schema(show=True):
    if show:
        return [
            {
                'name': 'ckanext.dcatapit_configpublisher_name',
                'validator': ['not_empty'],
                'element': 'input',
                'type': 'text',
                'label': _('Dataset Editor'),
                'placeholder': _('dataset editor'),
                'description': _('The responsible organization of the catalog'),
                'is_required': True
            },
            {
                'name': 'ckanext.dcatapit_configpublisher_code_identifier',
                'validator': ['not_empty'],
                'element': 'input',
                'type': 'text',
                'label': _('Catalog Organization Code'),
                'placeholder': _('IPA/IVA'),
                'description': _('The IVA/IPA code of the catalog organization'),
                'is_required': True
            },
            {
                'name': 'ckanext.dcatapit_config.catalog_issued',
                'validator': ['ignore_missing'],
                'element': 'input',
                'type': 'date',
                'label': _('Catalog Release Date'),
                'format': '%d-%m-%Y',
                'placeholder': _('catalog release date'),
                'description': _('The creation date of the catalog'),
                'is_required': False
            }
        ]
    else:
        return [
            {
                'name': 'ckanext.dcatapit_configpublisher_name',
                'validator': ['not_empty']
            },
            {
                'name': 'ckanext.dcatapit_configpublisher_code_identifier',
                'validator': ['not_empty']
            },
            {
                'name': 'ckanext.dcatapit_config.catalog_issued',
                'validator': ['ignore_missing']
            }
        ]


def get_custom_organization_schema():
    org_schema = [
        {
            'name': 'email',
            'validator': ['ignore_missing'],
            'element': 'input',
            'type': 'email',
            'label': _('EMail'),
            'placeholder': _('organization email'),
            'is_required': True
        },
        {
            'name': 'telephone',
            'validator': ['ignore_missing'],
            'element': 'input',
            'type': 'text',
            'label': _('Telephone'),
            'placeholder': _('organization telephone'),
            'is_required': False
        },
        {
            'name': 'site',
            'validator': ['ignore_missing'],
            'element': 'input',
            'type': 'url',
            'label': _('Site URL'),
            'placeholder': _('organization site url'),
            'is_required': False
        },
        {
            'name': 'region',
            'validator': ['ignore_missing', 'not_empty'],
            'element': 'region',
            'type': 'vocabulary',
            'vocabulary_name': 'regions',
            'label': _('Region'),
            'multiple': False,
            'placeholder': _('region name'),
            'data_module_source': '/api/2/util/vocabulary/autocomplete?vocabulary_id=regions&incomplete=?',
            'is_required': False
        },
        {

            # field become required by https://github.com/geosolutions-it/ckanext-dcatapit/pull/213#pullrequestreview-139966344
            'name': 'identifier',
            'label': _('IPA/IVA'),
            'validator': ['not_empty'],
            'element': 'input',
            'type': 'text',
            'is_required': True,
            'placeholder': _('organization IPA/IVA code')
        }
    ]

    from ckanext.dcatapit.helpers import get_icustomschema_org_fields
    org_schema.extend(get_icustomschema_org_fields())
    return org_schema


def get_custom_package_schema():
    package_schema = [
        {
            'name': 'identifier',
            'validator': ['not_empty', 'dcatapit_id_unique'],
            'element': 'input',
            'type': 'text',
            'label': _('Dataset Identifier'),
            'placeholder': _('dataset identifier'),
            'is_required': True,
            'help': _('package_identifier_help'),
        },
	{
            'name': 'access_rights',
            'validator': ['ignore_missing'],
            'element': 'select',
            'type': 'text',
            'label': _('Access Rights'),
            'placeholder': _('http://publications.europa.eu/resource/authority/access-right/PUBLIC'),
            'is_required': False,
            'help': _(u"""Proprietà che confluisce in dcat:accessRights"""),
            'options': [
                {   'text': 'PUBBLICO',
                    'name': 'accessrights',
                    'validator': ['ignore_missing'],
                    'label': 'Access Rights',
                    'placeholder': 'Access Rights',
                    'localized': True,
                    'value': 'http://publications.europa.eu/resource/authority/access-right/PUBLIC'
                },
                {   'text': 'RISERVATO',
                    'name': 'accessrights',
                    'validator': ['ignore_missing'],
                    'label': 'Access Rights',
                    'placeholder': 'Access Rights',
                    'localized': True,
                    'value': 'http://publications.europa.eu/resource/authority/access-right/RESTRICTED'
                }
            ],
        },
        {
            'name': 'hvd_category',
            'validator': ['ignore_missing'],
            'element': 'select',
            'options': [
                {   'text': 'Not HVD Category',
                    'name': 'nonhvd',
                    'validator': ['ignore_missing'],
                    'label': 'nonhhvd',
                    'placeholder': 'Non HVD',
                    'localized': True
                },
                {   'text': 'Dati metereologici',
                    'name': 'Metereologia',
                    'validator': ['ignore_missing'],
                    'label': 'Metereologia',
                    'value': 'http://data.europa.eu/bna/asd487ae75',
                    'placeholder': 'Metereologia',
                    'localized': True
                },
                {   'text': 'Dati relativi alle imprese e alla proprietà delle imprese',
                    'name': 'http://data.europa.eu/bna/c_a9135398',
                    'validator': ['ignore_missing'],
                    'label': _('Dati relativi alle imprese e alla proprietà delle imprese'),
                    'value': 'http://data.europa.eu/bna/c_a9135398',
                    'placeholder': _('Dati relativi alle imprese e alla proprietà delle imprese'),
                    'localized': True
                },
                {   'text': 'Dati geospaziali',
                    'name': 'http://data.europa.eu/bna/c_ac64a52d',
                    'validator': ['ignore_missing'],
                    'label': _('Dati geospaziali'),
                    'value': 'http://data.europa.eu/bna/c_ac64a52d',
                    'placeholder': _('publisher name'),
                    'localized': True
                },
                {   'text': _('Dati relativi alla mobilità'),
                    'name': _('http://data.europa.eu/bna/c_b79e35eb'),
                    'validator': ['ignore_missing'],
                    'label': _('Dati relativi alla mobilità'),
                    'value': 'http://data.europa.eu/bna/c_b79e35eb',
                    'placeholder': _('Dati relativi alla mobilità'),
                    'localized': True
                },
                {   'text': 'Dati relativi a osservazione della terra e ad ambiente',
                    'name': 'http://data.europa.eu/bna/c_dd313021',
                    'validator': ['ignore_missing'],
                    'label': _('Dati relativi a osservazione della terra e ad ambiente'),
                    'value': 'http://data.europa.eu/bna/c_dd313021',
                    'placeholder': _('publisher name'),
                    'localized': True
                },
                {   'text': 'Dati statistici',
                    'name': 'http://data.europa.eu/bna/c_e1da4e07',
                    'validator': ['ignore_missing'],
                    'label': _('Dati statistici'),
                    'value': 'http://data.europa.eu/bna/c_e1da4e07',
                    'placeholder': _('Dati statistici'),
                    'localized': True
                }
             ],
#            'type': 'text',
#            'vocabulary_name': 'dcatapit_hvdcategory',
            'label': 'Categoria HVD',
#            'label': 'Categoria High Value Dataset. Esempio: http://data.europa.eu/bna/ seguito dal codice asd487ae75 (Metereologia), c_a9135398 (Dati relativi alle imprese e alla proprietà delle imprese), c_ac64a52d (Dati geospaziali), c_b79e35eb (Dati relativi alla mobilità), c_dd313021 (Dati relativi a osservazione della terra e ad ambiente), c_e1da4e07 (Dati statistici)',
            'placeholder': _('hvd_category'),
            'is_required': False,
            'localized': True,
            'help': _(u"""Proprietà che confluisce in dcatap:hvdCategory""")
        },
        {
            'name': 'applicable_legislation',
            'validator': ['ignore_missing'],
            'element': 'select',
            'label': _('Applicable legislation'),
            'placeholder': _('http://data.europa.eu/eli/reg_impl/2023/138/oj'),
            'is_required': False,
            'options': [
                {   'text': 'Not Applicable legislation',
                    'name': 'nonapleg',
                    'validator': ['ignore_missing'],
                    'label': 'noapleg',
                    'placeholder': 'Non AppLeg',
                    'localized': True
                },
                {   'text': 'http://data.europa.eu/eli/reg_impl/2023/138/oj',
                    'name': 'applicable_legislation',
                    'validator': ['ignore_missing'],
                    'label': 'EU Applicable Legislation',
                    'value': 'http://data.europa.eu/eli/reg_impl/2023/138/oj',
                    'placeholder': 'Metereologia',
                    'localized': True
                }
             ],
            'help': _(u"""Questa proprietà si riferisce alla licenza con cui viene """
                      u"""pubblicato il dataset. Scegliere una delle due licenze """
                      u"""Creative Commons proposte.""")
        },
        {
            'name': 'alternate_identifier',
            'validator': ['ignore_missing', 'no_number', 'dcatapit_alternate_identifier'],
            'element': 'alternate_identifier',
            'type': 'text',
            'label': _('Other Identifier'),
            'placeholder': _('other identifier'),
            'is_required': False,
            'help': _('package_alternate_identifier_help'),
        },
        {
            # aggregation of themes and subthemes
            # Format: [ {'theme' : theme_short_name, 'subthemes': [subthemes URIs...]}, ...]
            'name': FIELD_THEMES_AGGREGATE,
            # 'validator': ['not_empty', 'dcatapit_subthemes'],
            'validator': ['dcatapit_subthemes'],
            'element': 'themes',
            'type': 'vocabulary',
            'vocabulary_name': 'eu_themes',
            'label': _('Dataset Themes'),
            'sublabel': _('Subthemes'),
            'placeholder': _('eg. education, agriculture, energy'),
            'data_module_source': '/api/2/util/vocabulary/autocomplete?vocabulary_id=eu_themes&incomplete=?',
            'is_required': True,
            'help': _('package_theme_help'),
        },
        {
            'name': 'publisher',
            'element': 'couple',
            'label': _('Dataset Editor'),
            'is_required': False,
            'couples': [
                {
                    'name': 'publisher_name',
                    'validator': ['ignore_missing'],
                    'label': _('Name'),
                    'type': 'text',
                    'placeholder': _('publisher name'),
                    'localized': True
                },
                {
                    'name': 'publisher_identifier',
                    'validator': ['ignore_missing'],
                    'label': _('IPA/IVA'),
                    'type': 'text',
                    'placeholder': _('publisher identifier')
                }
            ],
            'help': _('package_publisher_help'),
        },
        {
            'name': 'issued',
            'validator': ['ignore_missing'],
            'element': 'input',
            'type': 'date',
            'label': _('Release Date'),
            'format': '%Y-%m-%d',
            'placeholder': _('release date'),
            'is_required': False,
            'help': _('package_issued_help'),
        },
        {
            'name': 'modified',
            'validator': ['not_empty'],
            'element': 'input',
            'type': 'date',
            'label': _('Modification Date'),
            'format': '%Y-%m-%d',
            'placeholder': _('modification date'),
            'is_required': True,
            'help': _('package_modified_help')
        },
        {
            'name': 'geographical_name',
            'validator': ['ignore_missing'],
            'element': 'vocabulary',
            'type': 'vocabulary',
            'vocabulary_name': 'places',
            'label': _('Geographical Name'),
            'placeholder': _('geographical name'),
            'data_module_source': '/api/2/util/vocabulary/autocomplete?vocabulary_id=places&incomplete=?',
            'is_required': False,
            'default': _('Organizational Unit Responsible Competence Area'),
            'help': _('package_geographical_name_help')
        },
        {
            'name': 'geographical_geonames_url',
            'validator': ['ignore_missing'],
            'element': 'geonames',
            'type': 'geonames',
            'label': _('GeoNames URL'),
            'placeholder_url': _('Enter geonames URL'),
            'placeholder_name': _('Enter name of place'),
            'is_required': False,
            'help': _('package_geographical_geonames_url_help')
        },
        {
            'name': 'language',
            'validator': ['ignore_missing'],
            'element': 'vocabulary',
            'type': 'vocabulary',
            'vocabulary_name': 'languages',
            'label': _('Dataset Languages'),
            'placeholder': _('eg. italian, german, english'),
            'data_module_source': '/api/2/util/vocabulary/autocomplete?vocabulary_id=languages&incomplete=?',
            'is_required': False,
            'help': _('package_language_help')
        },
        {
            'name': 'temporal_coverage',
            'element': 'temporal_coverage',
            'label': _('Temporal Coverage'),
            'validator': ['ignore_missing', 'dcatapit_temporal_coverage'],
            'is_required': False,
            'format': '%d-%m-%Y',
            '_couples': [
                {
                    'name': 'temporal_start',
                    'label': _('Start Date'),
                    'validator': ['ignore_missing'],
                    'type': 'date',
                    'placeholder': _('temporal coverage')
                },
                {
                    'name': 'temporal_end',
                    'label': _('End Date'),
                    'validator': ['ignore_missing'],
                    'type': 'date',
                    'placeholder': _('temporal coverage')
                }
            ],

            'help': _('package_temporal_coverage_help')
        },

        {
            'name': 'rights_holder',
            'element': 'rights_holder',
            'label': _('Rights Holder'),
            'is_required': False,
            'read_only': True,
            'couples': [
                {
                    'name': 'holder_name',
                    'label': _('Name'),
                    'validator': ['ignore_missing'],
                    'type': 'text',
                    'placeholder': _('rights holder of the dataset'),
                    'localized': True

                },
                {
                    'name': 'holder_identifier',
                    'label': _('IPA/IVA'),
                    'validator': ['ignore_missing'],
                    'type': 'text',
                    'placeholder': _('rights holder of the dataset')
                }
            ],
            'help': _('package_rights_holder_name_help'),
            'help_create': _('package_rights_holder_name_create_help')
        },
        {
            'name': 'frequency',
            'validator': ['not_empty'],
            'element': 'select',
            'type': 'vocabulary',
            'vocabulary_name': 'frequencies',
            'label': _('Frequency'),
            'placeholder': _('accrual periodicity'),
            'data_module_source': '/api/2/util/vocabulary/autocomplete?vocabulary_id=frequencies&incomplete=?',
            'is_required': True,
            'help': _('package_frequency_help')
        },
        {
            'name': 'is_version_of',
            'validator': ['ignore_missing'],
            'element': 'input',
            'type': 'url',
            'label': _('Version Of'),
            'placeholder': _('is version of a related dataset URI'),
            'is_required': False,
            'help': _('package_is_version_of_help')
        },
        {
            'name': 'conforms_to',
            'validator': ['ignore_missing', 'dcatapit_conforms_to'],
            'element': 'conforms_to',
            'type': 'conforms_to',
            'label': _('Conforms To'),
            'placeholder': _('conforms to'),
            'is_required': False,
            'help': _('package_conforms_to_help')
        },
        {
            'name': 'creator',
            'element': 'creator',
            'label': _('Creator'),
            'type': 'creator',
            'placeholder': '-',
            'validator': ['ignore_missing', 'dcatapit_creator'],
            'is_required': False,
            '_couples': [
                {
                    'name': 'creator_name',
                    'label': _('Name'),
                    'validator': ['ignore_missing'],
                    'type': 'text',
                    'placeholder': _('creator of the dataset'),
                    'localized': True
                },
                {
                    'name': 'creator_identifier',
                    'label': _('IPA/IVA'),
                    'validator': ['ignore_missing'],
                    'type': 'text',
                    'placeholder': _('creator of the dataset')
                }
                    ],
            'help': _('package_creator_help')
        }
    ]

    _update_schema_fields(package_schema)

    from ckanext.dcatapit.helpers import get_icustomschema_fields
    package_schema.extend(get_icustomschema_fields())
    return package_schema


def _update_schema_fields(package_schema: dict):
    for plugin in PluginImplementations(ICustomSchema):
        if hasattr(plugin, 'get_schema_updates'):
            schema_updates = plugin.get_schema_updates()
            for field in package_schema:
                if field['name'] in schema_updates:
                    log.debug(f'Plugin "{plugin.name}" updating schema field "{field["name"]}"')
                    field.update(schema_updates[field['name']])
                    field['tainted'] = True


def get_custom_resource_schema():
    return [
        {
            'name': 'distribution_format',
            'validator': ['ignore_missing'],
            'element': 'select',
            'type': 'vocabulary',
            'vocabulary_name': 'filetype',
            'label': _('Distribution Format'),
            'placeholder': _('distribution format'),
            'data_module_source': '/api/2/util/vocabulary/autocomplete?vocabulary_id=filetype&incomplete=?',
            'is_required': False
        },
        {
            'name': 'license_type',
            'validator': ['ignore_missing'],
            'element': 'licenses_tree',
            'label': _('License'),
            'placeholder': _('license type'),
            'is_required': True,
            'help': _(u"""Questa proprietà si riferisce alla licenza con cui viene """
                      u"""pubblicato il dataset. Scegliere una delle due licenze """
                      u"""Creative Commons proposte.""")
        },
        {
            'name': 'rights',
            'validator': ['ignore_missing'],
            'element': 'select',
            'options': [
                {   'text': 'http://publications.europa.eu/resource/authority/access-right/PUBLIC',
                    'name': 'rights',
                    'validator': ['ignore_missing'],
                    'label': 'rights',
                    'placeholder': 'Rights',
                    'localized': True,
                    'value': 'http://publications.europa.eu/resource/authority/access-right/PUBLIC'
                }
            ],
            'label': _('Rights'),
            'placeholder': _('http://publications.europa.eu/resource/authority/access-right/PUBLIC'),
            'is_required': False,
            'help': _(u"""Questa proprietà si riferisce alla licenza con cui viene """
                      u"""pubblicato il dataset. Scegliere una delle due licenze """
                      u"""Creative Commons proposte.""")
        },
        {
            'name': 'access_services',
            'validator': ['ignore_missing'],
            'element': 'input',
            'label': _('Access Service'),
            'placeholder': _('Access Service'),
            'is_required': False,
            'help': _(u"""pubblicato il dataset. Scegliere una delle due licenze """
                      u"""Creative Commons proposte.""")
        },
        {
            'name': 'applicable_legislation',
            'validator': ['ignore_missing'],
            'element': 'input',
            'label': _('Applicable legislation'),
            'placeholder': _('http://data.europa.eu/eli/reg_impl/2023/138/oj'),
            'is_required': False,
            'help': _(u"""Questa proprietà si riferisce alla licenza con cui viene """
                      u"""pubblicato il dataset. Scegliere una delle due licenze """
                      u"""Creative Commons proposte.""")
        },
        {
            'name': 'availability',
            'label': 'Disponibilità del dato nel tempo',
            'validator': ['ignore_missing'],
            'element': 'select',
            'options': [
                {   'text': 'Stabile a lungo termine',
                    'name': 'Stabile',
                    'validator': ['ignore_missing'],
                    'label': 'Dati relativi disponibilità a lungo termine',
                    'value': 'https://publications.europa.eu/resource/authority/planned-availability/STABLE',
                    'placeholder': 'Dati relativi disponibilità a lungo termine',
                    'localized': True
                },
                {   'text': 'Disponibile a medio termine',
                    'name': 'http://data.europa.eu/bna/c_a9135398',
                    'validator': ['ignore_missing'],
                    'label': _('Dati relativi disponibilità a medio termine'),
                    'value': 'https://publications.europa.eu/resource/authority/planned-availability/AVAILABLE',
                    'placeholder': _('Dati relativi disponibilità a medio termine'),
                    'localized': True
                },
             ],
            'help': _(u"""Questa proprietà si riferisce alla disponibilità con cui viene """
                      u"""pubblicato il dato. diventa dcat:availability""")
        }
    ]
