# -*- coding: utf-8 -*-
{
    'name': "Factura Global",

    'summary': """
        Complemento factura global""",

    'description': """
        Complemento factura global
    """,

    'author': "silvau",
    'website': "http://www.zeval.com.mx",

    'category': 'account',
    'version': '14.1',
    'depends': ['factura_global'],

    'data': [
        'security/groups.xml',
        'security/rules.xml',
        'wizard/factura_global_view.xml',
        'views/account_invoice_view.xml',
    ],
}
