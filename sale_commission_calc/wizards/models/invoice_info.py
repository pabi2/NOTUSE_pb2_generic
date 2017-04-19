# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from openerp import models, fields, api
import openerp.addons.decimal_precision as dp


class InvoiceInfo(models.TransientModel):

    _name = 'invoice.info'
    _description = 'Invoice Info'

    @api.model
    def _get_invoice_id(self):
        Line = self.env['commission.worksheet.line'].browse(self._context['active_id'])
        return Line.invoice_id and Line.invoice_id.id or False

    invoice_id = fields.Many2one(
        'account.invoice',
        'Invoice Number',
        readonly=True,
        default=_get_invoice_id
    )
    invoice_info_line = fields.One2many(
        'invoice.info.line',
        'invoice_info_id',
        'Invoice Info Lines',
        readonly=True
    )

    @api.onchange('invoice_id')
    def onchange_invoice_id(self):
        invoice = self.env['account.invoice'].browse(self.invoice_id.id)
        invoice_info_line = []
        for line in invoice.invoice_line:
            invoice_info_line.append([0, 0, {
                'product_id': line.product_id and line.product_id.id or False,
                'name': line.name,
                'quantity': line.quantity,
                'uos_id': line.uos_id and line.uos_id.id or False,
                'price_unit': line.price_unit,
                'price_subtotal': line.price_subtotal
            }])
        self.invoice_info_line = invoice_info_line


class InvoiceInfoLine(models.TransientModel):

    """Invoice Info Lines"""

    _name = 'invoice.info.line'
    _description = 'Invoice Info Lines'

    invoice_info_id = fields.Many2one(
        'invoice.info',
        'Invoice Info'
    )
    product_id = fields.Many2one(
        'product.product',
        'Product'
    )
    name = fields.Char(
        'Description'
    )
    quantity = fields.Float(
        'Quantity',
        digits_compute=dp.get_precision('Product Unit of Measure')
    )
    uos_id = fields.Many2one(
        'product.uom',
        'UoM'
    )
    price_unit = fields.Float(
        'Unit Price',
        digits_compute=dp.get_precision('Account')
    )
    price_subtotal = fields.Float(
        'Subtotal',
        digits_compute=dp.get_precision('Account')
    )

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
