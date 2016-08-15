# -*- coding: utf-8 -*-
import time
import datetime
import dateutil
import openerp
from openerp import workflow
from openerp import models, fields, api, _
from openerp.exceptions import Warning as UserError


class PaymentExport(models.Model):
    _name = 'payment.export'
    _description = 'Payment Export'

    name = fields.Char(
        string='Number',
        required=True,
        copy=False,
        readonly=True,
        states={'draft': [('readonly', False)]},
        default="/",
    )
    journal_id = fields.Many2one(
        'account.journal',
        string='Payment Method',
        domain=[('type', '=', 'bank')],
        required=True,
        readonly=True,
        states={'draft': [('readonly', False)]},
    )
    date_value = fields.Date(
        string='Value/Cheque Date',
        required=True,
        readonly=True,
        states={'draft': [('readonly', False)]},
    )
    bank_id = fields.Many2one(
        'res.partner.bank',
        related='journal_id.bank_id',
        string='Bank Account',
    )
    is_cheque_lot = fields.Boolean(
        string='Is Cheque Lot Available',
        compute='_compute_is_cheque_lot',
    )
    cheque_lot_id = fields.Many2one(
        'cheque.lot',
        string='Cheque Lot',
        domain="[('bank_id', '=', bank_id), "
        "('journal_id', '=', journal_id),('state', '=', 'active')]",
        ondelete='restrict',
        readonly=True,
        states={'draft': [('readonly', False)]},
    )
    cheque_number_from = fields.Char(
        string='Cheque Number From',
        compute='_compute_cheque_number',
    )
    cheque_number_to = fields.Char(
        string='Cheque Number From',
        compute='_compute_cheque_number',
    )
    user_id = fields.Many2one(
        'res.users',
        string='Responsible',
        required=True,
        default=lambda self: self._uid,
    )
    line_ids = fields.One2many(
        'payment.export.line',
        'export_id',
        string='Payment Export Lines',
    )
    state = fields.Selection(
        [('draft', 'Draft'),
         ('done', 'Done'),
         ('cancel', 'Cancelled'),
         ],
        string='Status',
        default='draft',
        required=True,
    )
    cheque_register_id = fields.Many2one(
        'cheque.register',
        related='line_ids.cheque_register_id',
        string='Cheque Number',
        help='Search line for Cheque',
    )
    voucher_id = fields.Many2one(
        'account.voucher',
        related='line_ids.voucher_id',
        string='Supplier Payment',
        help='Search line for Payment',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.user.company_id,
    )
    sum_amount = fields.Float(
        compute="_compute_sum_amount",
        string="Sum Amount",
        store=True,
        copy=False,
    )
    sum_total = fields.Float(
        compute="_compute_sum_amount",
        string="Sum Total",
        store=True,
        copy=False,
    )
    cancel_reason_txt = fields.Char(
        string="Description",
        readonly=True)

    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            vals['name'] = self.env['ir.sequence'].get('payment.export') or '/'
        return super(PaymentExport, self).create(vals)

    @api.depends('line_ids',
                 'line_ids.amount',
                 'line_ids.use_export_line',
                 'line_ids.amount_total')
    def _compute_sum_amount(self):
        for export in self:
            sum_amount = 0.0
            sum_total = 0.0
            for line in export.line_ids:
                if line.use_export_line:
                    sum_amount += line.amount
                    sum_total += line.amount_total
            export.sum_amount = sum_amount
            export.sum_total = sum_total

    @api.multi
    @api.depends()
    def _compute_cheque_number(self):
        for export in self:
            self._cr.execute("""
                select min(cr.number) min, max(cr.number) max
                from payment_export_line pel
                join cheque_register cr on cr.id = pel.cheque_register_id
                where pel.export_id = %s
            """, (export.id,))
            res = self._cr.fetchone()
            export.cheque_number_from = res[0]
            export.cheque_number_to = res[1]

    @api.one
    @api.depends('bank_id', 'journal_id')
    def _compute_is_cheque_lot(self):
        Lot = self.env['cheque.lot']
        lots = Lot.search([('bank_id', '=', self.bank_id.id),
                           ('journal_id', '=', self.journal_id.id)])
        self.is_cheque_lot = lots and True or False

    @api.onchange('journal_id')
    def _onchange_journal_id(self):
        self.cheque_lot_id = False

    @api.onchange('journal_id', 'cheque_lot_id', 'date_value')
    def _onchange_compute_payment_export_line(self):
        self.line_ids = False
        self.line_ids = []
        if not self.journal_id or not self.date_value:  # At least
            return
        if self.is_cheque_lot and not self.cheque_lot_id:  # Case Lot
            return
        Voucher = self.env['account.voucher']
        dom = [('journal_id', '=', self.journal_id.id),
               ('date_value', '=', self.date_value),
               ('state', '=', 'posted')]
        ExportLine = self.env['payment.export.line']
        # Case Cheque, make sure it has not been in any valid cheque before
        if self.is_cheque_lot:
            chequed_voucher_ids = [x.voucher_id.id
                                   for x in self.cheque_lot_id.line_ids
                                   if x.voucher_id and not x.void]
            dom.append(('cheque_lot_id', '=', self.cheque_lot_id.id))
            dom.append(('id', 'not in', chequed_voucher_ids))
        else:  # Other cases, make sure it has not been exported before
            lines = ExportLine.search(
                [('exported', '=', True),
                 ('export_id.date_value', '=', self.date_value)],
            )
            exported_voucher_ids = [x.voucher_id.id for x in lines]
            dom.append(('id', 'not in', exported_voucher_ids))
        vouchers = Voucher.search(dom, order='id',
                                  limit=self.cheque_lot_id.remaining)
        for voucher in vouchers:
            export_line = ExportLine.new()
            export_line.use_export_line = True
            export_line.voucher_id = voucher
            export_line.amount = voucher.amount
            self.line_ids += export_line

    @api.multi
    def action_assign_cheque_number(self):
        if not self.is_cheque_lot:
            return
        ChequeLot = self.env['cheque.lot']
        for rec in self:
            limit = len(filter(lambda l: (l.use_export_line), rec.line_ids))
            cheque_lot_id = rec.cheque_lot_id.id
            res = ChequeLot.get_draft_cheque_register_range(cheque_lot_id,
                                                            limit)
            for i in range(limit):
                if rec.line_ids[i].use_export_line:
                    rec.line_ids[i].cheque_register_id = res[i]

    @api.multi
    def action_done(self):
        for export in self:
            if not export.line_ids:
                raise UserError(_('No Export Lines'))
            for line in export.line_ids:
                if line.use_export_line:
                    voucher = line.voucher_id
                    export_voucher_ids =\
                        self.env['payment.export.line'].\
                        search([('voucher_id', '=', voucher.id)])
                    voucher_done_export = [(e, e.voucher_id)
                                           for e in export_voucher_ids
                                           if e.export_id.state == 'done']
                    if voucher_done_export:
                        raise UserError(
                            _("Supplier Payment %s has been exported by %s:")
                            % (voucher_done_export[1].number,
                               voucher_done_export[0].name))
            # Case Cheque only
            if export.is_cheque_lot:
                for line in export.line_ids:
                    if line.use_export_line:
                        if not line.cheque_register_id:
                            raise UserError(
                                _('Some Payments is not assigned with Cheque '
                                  'Number!\nPlease click Assign Cheque Number.'
                                  ))
                        if line.cheque_register_id.voucher_id:
                            raise UserError(
                                _('Cheque Number %s is occupied, \
                                    please reassign again!')
                                % (line.cheque_register_id.number))
                        if line.cheque_register_id.void:
                            raise UserError(
                                _('Cheque Number %s is voided, please reassign'
                                  ' again!')
                                % (line.cheque_register_id.number))
                        line.cheque_register_id.write(
                            {'voucher_id': line.voucher_id.id,
                             'payment_export_id': export.id}
                        )
                        cheque_register = line.cheque_register_id
                        cheque_lot = cheque_register.cheque_lot_id
                        cheque_number = cheque_register.number
                        cheque_date = export.date_value
                        bank_name = cheque_lot.bank_id.name
                        bank_branch = cheque_lot.bank_id.branch_cheque
                        line.voucher_id.write({
                            'date_cheque': cheque_date,
                            'number_cheque': cheque_number,
                            'bank_cheque': bank_name,
                            'branch_cheque': bank_branch,
                        })
                        line.write({'exported': True})
        self.write({'state': 'done'})

    @api.multi
    def action_cancel(self):
        self.write({'state': 'cancel'})
        for rec in self:
            for line in rec.line_ids:
                if line.use_export_line:
                    line.cheque_register_id.write(
                        {'voucher_id': False,
                         'payment_export_id': False}
                    )
                    line.write({'exported': False})

    @api.multi
    def action_draft(self):
        self.write({'state': 'draft'})


class PaymentExportLine(models.Model):
    _name = 'payment.export.line'
    _description = 'Payment Export Line'

    export_id = fields.Many2one(
        'payment.export',
        string='Payment Export',
        ondelete='cascade',
        index=True,
    )
    cheque_register_id = fields.Many2one(
        'cheque.register',
        string='Cheque Number',
        readonly=True,
    )
    voucher_id = fields.Many2one(
        'account.voucher',
        string='Supplier Payment',
        readonly=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        related='voucher_id.partner_id',
        string='Supplier',
        readonly=True,
    )
    amount = fields.Float(
        string='Amount',
        readonly=True,
    )
    void = fields.Boolean(
        string='Void',
        related='cheque_register_id.void',
        readonly=True,
    )
    exported = fields.Boolean(
        string='Exported',
        default=False,
    )
    use_export_line = fields.Boolean(
        string="Use line",
        default=True,
        copy=False,
    )
    amount_fee = fields.Float(
        string="Fee",
        copy=False,
    )
    amount_total = fields.Float(
        compute="_compute_total",
        string="Total",
        store=True,
        copy=False,
    )

    @api.depends('amount', 'amount_fee')
    def _compute_total(self):
        for line in self:
            line.amount_total = line.amount + line.amount_fee
