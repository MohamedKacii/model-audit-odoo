{
    'name': 'ITC Audit Log',
    'summary': "Journalisation des créations, modifications, suppressions et archivages",
    'version': '17.0.1.1.0',
    'author': 'mohamed kaci',
    'category': 'Tools',
    'depends': ['base', 'mail'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/audit_model_config_views.xml',
        'views/audit_log_views.xml',
        'views/audit_purge_views.xml',
        'views/audit_snapshot_views.xml',
        'views/audit_dashboard_views.xml',
        'views/menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'itc_audit_log/static/src/dashboard/audit_dashboard.js',
            'itc_audit_log/static/src/dashboard/audit_dashboard.xml',
            'itc_audit_log/static/src/dashboard/audit_dashboard.css',
        ],
        'web.assets_tests': [
            'itc_audit_log/static/tests/tours/*.js',
        ],
    },
    'license': 'LGPL-3',
    'application': True,
    'installable': True,
}
