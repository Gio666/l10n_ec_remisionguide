# -*- coding: utf-8 -*-
# <2017> <Miguel Albalat & Eduardo Firvida>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging
import re
import utils
import os

from jinja2 import Environment, FileSystemLoader
from datetime import datetime, timedelta
from random import choice

from ..xades.sri import DocumentXML
from ..xades.xades import Xades

from odoo import (api, fields, models)
from odoo.exceptions import (Warning as UserError)


class RemissionGuideShippingType(models.Model):
    _name = 'account.remission_guide.type'
    __logger = logging.getLogger(_name)

    name = fields.Char(string="Nombre",
                       store=True,
                       readonly=False)

    remission_guide_id = fields.One2many('account.remission_guide',
                                         'shipping_type_id')

class RemissionGuideShippingType(models.Model):
    _name = 'account.remission_guide.tranfer.reason'
    __logger = logging.getLogger(_name)

    name = fields.Char(string="Nombre",
                       store=True,
                       readonly=False)

    remission_guide_id = fields.One2many('account.remission_guide',
                                         'shipping_type_id')


class RemissionGuide(models.Model):
    _name = 'account.remission_guide'
    _logger = logging.getLogger(_name)

    name = fields.Char(string='Secuencial', 
                           index=True, 
                           readonly=True)

    start_delivery_date = fields.Date('Start delivery date',
                                      required=True,
                                      default=fields.Date.today)

    end_delivery_date = fields.Date('End delivery date',
                                    required=True,
                                    default=datetime.today() + timedelta(days=1))

    start_delivery_address = fields.Char('Start delivery address',
                                         help='Address from items are picket',
                                         size=255,
                                         required=True)

    reason_for_transfer = fields.Many2one('account.remission_guide.tranfer.reason',
                                      help='Reason to move items to the especified route',
                                      required=True)

    route = fields.Char('Route',
                        help='Route take it to move the items',
                        size=300,
                        required=True)

    rise = fields.Char('RISE',
                        help='Contribuyente Regimen Simplificado RISE',
                        size=40)

    contribuyenteEspecial = fields.Char('Contribuyente Especial',
                        help='Contribuyente Especial',
                        size=13)
    
    access_key = fields.Char('Access Key',
                        help='Access Key',
                        size=49,
                        required=True,
                        readonly=True,
                        default=lambda self: ''.join(choice('0123456789') for i in range(29)) + re.sub('[^0-9]','', str(datetime.now())))

    products = fields.Integer('Products in the Vehicle',
                              help='Amount of products',
                              compute='_compute_products')

    total_products_weigth = fields.Float('Total Products Weight',
                                         help='Amount of products',
                                         compute='_compute_products',
                                         default=0.0)

    company_id = fields.Many2one('res.company', 
                                  default=lambda self: self.env['res.users'].browse(self._uid).company_id)

    authorization_id = fields.Many2one('account.authorisation')

    transporting_truck_id = fields.Many2one('fleet.vehicle',
                                            required=True)

    transporting_truck_capacity = fields.Float(related='transporting_truck_id.capacity',
                                              help="Truck Capacity [kg]", 
                                              readonly=True)

    transporting_truck_capacity_remain = fields.Char(related='transporting_truck_id.capacity_remain',
                                                     help="Truck capacity remain [kg]", 
                                                     readonly=True)

    transporting_truck_total_weigth = fields.Float(related='transporting_truck_id.total_weigth',
                                                  help="Truck total products weight [kg]", 
                                                  readonly=True)

    shipping_type_id = fields.Many2one('account.remission_guide.type',
                                       required=True)

    invoices_to_ship = fields.One2many('account.invoice',
                                       'remission_guide_id',
                                       required=True)

    state = fields.Selection([('draft', "Draft"),
                              ('confirmed', "Confirmed"),
                              ('sri', "SRI Approved"),
                              ('done', "Done"), ],
                               default='draft')
    
    @api.constrains('start_delivery_date', 'end_delivery_date')
    def _check_date(self):
        if self.start_delivery_date > self.end_delivery_date:
            raise UserError("The start date must be anterior to the end date.")
        if self.start_delivery_date < fields.Date.to_string(datetime.today()):
            raise UserError("You can't create a remision guide on past date")

    @api.onchange('invoices_to_ship')
    def _recalculate_weight(self):
        self._compute_products()

    def _compute_products(self):
        self.total_products_weigth = 0
        self.products = 0
        for invoice in self.invoices_to_ship:
            for product in invoice.invoice_line_ids:
                self.products += product.quantity
                self.total_products_weigth += product.product_id.weight * product.quantity

    @api.multi
    def action_draft(self):
        self.state = 'draft'

    @api.multi
    def action_confirm(self):
        self.state = 'confirmed'

    @api.multi
    def action_done(self):
        self.state = 'done'

    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code('account.remission_guide.sequence')
        return super(RemissionGuide, self).create(vals)

    def action_generate_remission_guide(self):
        tmpl_path = os.path.join(os.path.dirname(__file__), 'templates')
        env = Environment(loader=FileSystemLoader(tmpl_path))
        remission_tmpl = env.get_template('remission_guide.xml')
        data = {}
        data.update(self._info_tributaria())
        data.update(self._info_guia_remision())
        data.update({'destinatarios':self._info_destinatarios()})
        document = remission_tmpl.render(data)
        file_pk12 = self.company_id.electronic_signature
        password = self.company_id.password_electronic_signature

        #FIXME hay que probarlo 
        inv_xml = DocumentXML(document)
        inv_xml.validate_xml()
        
        xades = Xades()
        signed_document = xades.sign(document, file_pk12, password)
        ok, errores = inv_xml.send_receipt(signed_document)
        if not ok:
            raise UserError(errores)
        else:
            self.state = 'sri'
        auth, m = inv_xml.request_authorization(access_key)
        if not auth:
            msg = ' '.join(list(itertools.chain(*m)))
            raise UserError(msg)
        
        auth_remission = self.render_authorized_remission(auth)
        self.update_document(auth, [self.access_key, self.company_id.emission_code])
        attach = self.add_attachment(auth_einvoice, auth)
        message = """
        DOCUMENTO ELECTRONICO GENERADO <br><br>
        CLAVE DE ACCESO: %s <br>
        NUMERO DE AUTORIZACION %s <br>
        FECHA AUTORIZACION: %s <br>
        ESTADO DE AUTORIZACION: %s <br>
        AMBIENTE: %s <br>
        """ % (
            self.clave_acceso,
            self.numero_autorizacion,
            self.fecha_autorizacion,
            self.estado_autorizacion,
            self.ambiente
        )
        self.message_post(body=message)
        self.send_document(
            attachments=[a.id for a in attach],
            tmpl='l10n_ec_einvoice.email_template_einvoice'
        )

    def render_authorized_remission(self, autorizacion):
        tmpl_path = os.path.join(os.path.dirname(__file__), 'templates')
        env = Environment(loader=FileSystemLoader(tmpl_path))
        einvoice_tmpl = env.get_template('authorized_remission.xml')
        auth_xml = {
            'estado': autorizacion.estado,
            'numeroAutorizacion': autorizacion.numeroAutorizacion,
            'ambiente': autorizacion.ambiente,
            'fechaAutorizacion': str(autorizacion.fechaAutorizacion.strftime("%d/%m/%Y %H:%M:%S")),  # noqa
            'comprobante': autorizacion.comprobante
        }
        auth_invoice = einvoice_tmpl.render(auth_xml)
        return auth_invoice


    @api.multi
    def update_document(self, auth, codes):
        fecha = auth.fechaAutorizacion.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        self.write({
            'numero_autorizacion': auth.numeroAutorizacion,
            'estado_autorizacion': auth.estado,
            'ambiente': auth.ambiente,
            'fecha_autorizacion': fecha,  # noqa
            'autorizado_sri': True,
            'clave_acceso': codes[0],
            'emission_code': codes[1]
        })

    @api.one
    def add_attachment(self, xml_element, auth):
        buf = StringIO.StringIO()
        buf.write(xml_element.encode('utf-8'))
        document = base64.encodestring(buf.getvalue())
        buf.close()
        attach = self.env['ir.attachment'].create(
            {
                'name': '{0}.xml'.format(self.access_key),
                'datas': document,
                'datas_fname':  '{0}.xml'.format(self.access_key),
                'res_model': self._name,
                'res_id': self.id,
                'type': 'binary'
            },
        )
        return attach


    def _info_tributaria(self):
        company = self.company_id
        infoTributaria = {
            'ambiente': company.env_service,
            'tipoEmision': company.emission_code,
            'razonSocial': company.name,
            'nombreComercial': company.name,
            'ruc': company.partner_id.identifier,
            'claveAcceso':  self.access_key,
            'codDoc': '06',
            'estab': self.authorization_id.serie_entidad,
            'ptoEmi': self.authorization_id.serie_emision,
            'secuencial': self.name,
            'dirMatriz': company.street
        }
        return infoTributaria
    
    def _info_guia_remision(self):
        company = self.company_id
        infoGuiaRemision = {
            'dirEstablecimiento': company.street,
            'dirPartida': self.start_delivery_address,
            'razonSocialTransportista': self.transporting_truck_id.driver_id.name,
            'tipoIdentificacionTransportista': utils.tipoIdentificacion[self.transporting_truck_id.driver_id.type_identifier],
            'rucTransportista': self.transporting_truck_id.driver_id.identifier,
            'rise':  self.rise,
            'obligadoContabilidad': 'SI',
            'contribuyenteEspecial': self.contribuyenteEspecial,
            'fechaIniTransporte': '/'.join(self.start_delivery_date.split('-')[::-1]),
            'fechaFinTransporte': '/'.join(self.end_delivery_date.split('-')[::-1]),
            'placa': self.transporting_truck_id.license_plate
        }
        if company.company_registry:
            infoGuiaRemision.update({'contribuyenteEspecial': company.company_registry})
        return infoGuiaRemision
    
    def _info_destinatarios(self):
        import pprint 
        destinatarios = []
        for invoice in self.invoices_to_ship:
            destinatario = {
                'identificacionDestinatario' : invoice.partner_id.identifier,
                'razonSocialDestinatario' : invoice.partner_id.name,
                'dirDestinatario' : invoice.partner_id.street,
                'motivoTraslado' : self.reason_for_transfer,
                'docAduaneroUnico' : invoice.docAduaneroUnico,
                'codEstabDestino' : invoice.auth_inv_id.serie_entidad, #FIXME no estoy seguro que sea esto
                'ruta' : self.route,
                'codDocSustento' : '01', #FIXME 01 para factura
                'numDocSustento' : '',    #FIXME no se que es
                'numAutDocSustento' : '', #FIXME no se que es
                'fechaEmisionDocSustento' : '', #FIXME no se que es
                'detalles' : [],
            }
            detalles = []
            for product in invoice.invoice_line_ids:
                detalle = {
                    'codigoInterno': product.product_id.default_code,
                    'codigoAdicional': '',
                    'descripcion': product.product_id.name,
                    'cantidad': product.quantity,
                }
                detalles.append(detalle)
                destinatario.update({'detalles': detalles})
            destinatarios.append(destinatario)
        return destinatarios


class RemissionGuideInvoices(models.Model):
    _inherit = 'account.invoice'

    remission_guide_id = fields.Many2one('account.remission_guide',
                                         ondelete='set null',
                                         string="Invoices",
                                         index=True)

    customer_street = fields.Char(related='partner_id.street', help="Address")

    customer_city = fields.Char(related='partner_id.city', help="City")

    customer_state = fields.Char(related='partner_id.state_id.name', help="State")

    customer_country = fields.Char(related='partner_id.country_id.name', help="Country")

    customer_zip = fields.Char(related='partner_id.zip',  help="Zip Code")
    
    docAduaneroUnico =  fields.Char('Documento aduanero Unico',  required=True)

class RemissionGuideVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    remission_guide_id = fields.One2many('account.remission_guide',
                                         'transporting_truck_id')

    capacity = fields.Float('Vehicle Capacity',
                            help='Car/Truck capacity in kg',
                            required=True,
                            defaults=0.0)

    capacity_remain = fields.Char('Remaining Vehicle Capacity',
                                  help='Car/Truck capacity in Tons',
                                  compute='_compute_capacity')

    products = fields.Integer('Products in the Vehicle',
                              help='Amount of products',
                              compute='_compute_capacity')

    total_weigth = fields.Float('Total Products Weight',
                                help='Sum of weight of the products',
                                compute='_compute_capacity')

    @api.onchange('remission_guide_id', 'capacity')
    def _validate(self):
        warning = self._compute_capacity()
        print warning
        if warning:
            raise UserError("The vehicle has more weight [%s kg] than it can carry [%s kg]" % (
                abs(self.capacity - self.total_weigth), self.capacity))

    def _compute_capacity(self):
        self.products = 0
        self.total_weigth = 0.0
        for guide in self.remission_guide_id:
            self.products += guide.products
            self.total_weigth += guide.total_products_weigth

        load = self.capacity - self.total_weigth

        if not load:
            val = 'Vehicle Full'
            warning = False
        elif load < 0:
            val = 'Vehicle overloaded [%s kg]' % abs(load)
            warning = True
        elif not self.products:
            val = 'Vehicle Empty'
            warning = False
        else:
            val = str(load) + ' kg'
            warning = False

        self.capacity_remain = val
        return warning


class RemissionGuideCompany(models.Model):
    
    _inherit = 'res.company'

    remission_guide_id = fields.One2many('account.remission_guide',
                                         'company_id')

class RemissionGuideAuthorization(models.Model):
    
    _inherit = 'account.authorisation'

    remission_guide_id = fields.One2many('account.remission_guide',
                                         'authorization_id')

