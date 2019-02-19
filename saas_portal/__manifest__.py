{
    'name': 'SaaS Portal',
    'version': '11.0.1.1.0',
    'author': 'Ivan Yelizariev, Nicolas JEUDY, Antonio Buric, Lucas Huber',
    'license': 'LGPL-3',
    'category': 'SaaS',
    'sequence': 1,
    'support': 'apps@it-projects.info',
    'website': 'https://it-projects.info',
    'summary': 'Module to manage databases, templates, products, clients and plans.',

    'depends': [
        'oauth_provider',
        'website',
        'auth_signup',
        'saas_base',
    ],
    'data': [
        'data/mail_template_data.xml',
        'data/plan_sequence.xml',
        'data/cron.xml',
        'wizard/client_login_request .xml',
        'wizard/client_manipulator.xml',
        'wizard/client_operator.xml',
        'wizard/client_creation.xml',
        'wizard/plan_client_creation.xml',
        'wizard/batch_delete.xml',
        'wizard/saas_duplicate_template_view.xml',
        'views/saas_portal_menu.xml',
        'views/saas_portal_client.xml',
        'views/saas_portal_plan.xml',
        'views/saas_portal_server_parameter.xml',
        'views/saas_portal_server_branch.xml',
        'views/saas_portal_server.xml',
        'views/saas_portal_database.xml',
        'views/saas_portal_configuration.xml',
        'views/website_templates.xml',
        'views/res_config.xml',
        'data/ir_config_parameter.xml',
        'data/subtype.xml',
        'security/portal_security.xml',
        'security/ir.model.access.csv',
    ],
    'application': True,
    'installable': True,
}
