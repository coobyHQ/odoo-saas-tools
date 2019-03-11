{
    'name': 'SaaS Portal Support Team',
    'version': '11.0.1.0.0',
    'author': 'Ivan Yelizariev, Nicolas JEUDY, Lucas Huber',
    'license': 'LGPL-3',
    'category': 'SaaS',
    'support': 'apps@it-projects.info',
    'website': 'https://it-projects.info',
    'summary': 'Module that ads Support teams to client instances in SaaS Portal.',

    'depends': [
        'saas_portal',
    ],
    'data': [
        'views/saas_portal_support_team.xml',
        'views/saas_portal_client.xml',
        'views/res_users.xml',
        'data/support_team.xml',
        'data/res_users.xml',
        'data/subtype.xml',
        'security/ir.model.access.csv',
    ],
    'application': False,
    'installable': True,
}
