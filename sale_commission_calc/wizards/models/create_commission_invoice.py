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


class CreateCommissionInvoice(models.TransientModel):

    """Create Commission Invoice"""

    @api.model
    def _get_commission_amt(self):
        worksheet = self.env['commission.worksheet'].browse(self._context['active_id'])
        if worksheet:
            return worksheet.amount_valid
        return False

    _name = 'create.commission.invoice'
    _description = 'Create Commission Invoice'

    commission_amt = fields.Float(
        'Commission Amount',
        digits_compute=dp.get_precision('Account'),
        readonly=True,
        default=_get_commission_amt
    )
    comment = fields.Text(
        'Comment'
    )

    @api.multi
    def create_commission_invoice(self):
        context = self._context.copy()
        form_data = self.with_context(context).read(['comment'])[0]
        context.update({'comment': form_data['comment']})
        commission_worksheet = self.env['commission.worksheet'].browse(context['active_id'])
        return commission_worksheet.with_context(context).action_create_invoice()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
