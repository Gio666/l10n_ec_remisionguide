# -*- coding: utf-8 -*-
{
    'name': 'Electronic Documents for Ecuador (Remissions Guide)',
    'version': '10.0.0.1.0',
    'author': 'efirvida & malbalat',
    'category': 'Localization',
    'license': 'AGPL-3',
    'complexity': 'normal',
    'data': [
        'data/remission_guide_data.xml',
        'views/remission_guide_menus.xml',
        'views/remission_guide_view.xml',
        'views/remission_guide_type_view.xml',
        'views/product_view.xml',
        'views/fleet_view.xml'
    ],
    'depends': [
        'l10n_ec_einvoice',
        'fleet',
    ]
}
