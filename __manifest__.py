{
    'name': 'Multi-Stage Approval System',
    'version': '18.0.1.0.0',
    'category': 'Purchases/Sales',
    'author': 'Moeed Nasir',
    'website': 'https://moeed-portfolio.netlify.app/',
    'summary': 'Multi-level approval workflow for Purchase and Sales',
    'depends': ['purchase', 'sale', 'mail', 'stock'],
    'data': [
        'security/ir.model.access.csv',
        'security/approval_rules.xml',
        'data/approval_stages.xml',
        'data/approval_demo.xml',
        'data/mail_templates.xml',
        'views/approval_flow_views.xml',
        'views/approval_stage_views.xml',
        'views/purchase_views.xml',
        'views/sale_views.xml',
        'views/approval_kanban_views.xml',
        'views/approval_menu_views.xml',
        'wizards/approval_report_wizard_views.xml',
        'report/approval_report_templates.xml',
        'report/approval_report_actions.xml',

    ],
    'demo': [
        'data/approval_demo.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'multi_stage_approval/static/src/css/approval.css',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}