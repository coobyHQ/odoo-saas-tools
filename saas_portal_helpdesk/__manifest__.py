# Copyright 2018 <CoobyTec>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    'name': 'SaaS Portal Helpdesk',
    'version': '11.0.1.0.0',
    'summary': 'Helpdesk module extensions for the SaaS Portal',
    'author': 'CoobyTec',
    'category': 'Tools',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'depends': [
        'website_support',
        'saas_portal',
    ],
    'data': [
        'security/ir.model.access.csv',
       # 'security/saas_portal_support_security.xml',
        'views/saas_portal_client_view.xml',
       # 'views/website_support_ticket_view.xml',
  ],
    'demo': [
    ],
}
