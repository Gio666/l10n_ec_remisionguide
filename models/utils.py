# -*- coding: utf-8 -*-

import requests

tipoIdentificacion = {
    'ruc': '04',
    'cedula': '05',
    'pasaporte': '06',
    'venta_consumidor_final': '07',
    'identificacion_exterior': '08',
    'placa': '09',
}

MSG_SCHEMA_INVALID = u"El sistema generó el XML pero"
" el comprobante electrónico no pasa la validación XSD del SRI."

SITE_BASE_TEST = 'https://celcer.sri.gob.ec/'
SITE_BASE_PROD = 'https://cel.sri.gob.ec/'
WS_TEST_RECEIV = 'https://celcer.sri.gob.ec/comprobantes-electronicos-ws/RecepcionComprobantes?wsdl'  # noqa
WS_TEST_AUTH = 'https://celcer.sri.gob.ec/comprobantes-electronicos-ws/AutorizacionComprobantes?wsdl'  # noqa
WS_RECEIV = 'https://cel.sri.gob.ec/comprobantes-electronicos-ws/RecepcionComprobantes?wsdl'  # noqa
WS_AUTH = 'https://cel.sri.gob.ec/comprobantes-electronicos-ws/AutorizacionComprobantes?wsdl'  # noqa

def check_service(env='prueba'):
    flag = False
    if env == 'prueba':
        URL = WS_TEST_RECEIV
    else:
        URL = WS_RECEIV

    for i in [1, 2, 3]:
        try:
            res = requests.head(URL, timeout=3)
            flag = True
        except requests.exceptions.RequestException:
            return flag, False
    return flag, res