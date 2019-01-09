{
    'name': "Saas Portal Sale in Shop",
    'author': "IT-Projects LLC, Ildar Nasyrov, Nicolas JEUDY, Cooby tec",
    'license': 'LGPL-3',
    "support": "apps@it-projects.info",
    'website': 'https://it-projects.info',
    'category': 'SaaS',
    'summary': 'Sell views of SaaS products in the Webshop',
    'version': '11.0.1.0.0',
    'depends': ['website_sale', 'saas_portal', 'saas_portal_sale', 'website_sale_require_login'],
    'data': [
        'views/templates.xml',
        'views/saas_portal_shop_extra_step.xml',
    ],

    'installable': True,
}
