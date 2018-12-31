{
    'name': 'SaaS Portal Shop Workflow',
    'version': '11.0.1.0.0',
    'author': 'Lucas Huber, Dave Cook, Antonio Buric',
    'license': 'LGPL-3',
    'category': 'SaaS',
    'support': 'apps@it-projects.info',
    'website': 'https://it-projects.info',
    'summary': 'Creates an instance after the payment for website order gets validated.',

    'depends': [
        'saas_portal_sale',
    ],
    'data': [
        'views/saas_portal_shop_extra_step.xml',
    ],
    'application': False,
    'installable': True,
}
