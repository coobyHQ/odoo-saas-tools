{
    'name': "Saas Portal Sale",
    'author': "IT-Projects LLC, Ildar Nasyrov, Nicolas JEUDY, Cooby tec",
    'license': 'LGPL-3',
    'support': 'apps@it-projects.info',
    'website': 'https://it-projects.info',
    'category': 'SaaS',
    'summary': 'Sells SaaS products in the Webshop',
    'version': '11.0.1.1.0',
    'depends': [
        'sale',
        'website_sale',
        'saas_portal',
        'product_price_factor',
        'saas_portal_start',
        'contract',
    ],
    'data': [
        'wizard/change_plan_of_client_view.xml',
        'wizard/add_language_templates_view.xml',
        'views/product_template_views.xml',
        'views/product_attribute_views.xml',
        'views/saas_portal_menu.xml',
        'views/saas_portal_plan.xml',
        'views/saas_portal_client.xml',
        'data/mail_template_data.xml',
        'data/ir_config_parameter.xml',
        'data/product_uom_data.xml',
        'data/product_attribute_data.xml',
    ],
}
