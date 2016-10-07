# -*- coding: utf-8 -*-
from openerp import models, fields, api, _
from openerp.exceptions import ValidationError
from openerp.addons.l10n_th_account.models.res_partner \
    import INCOME_TAX_FORM


class PrintPNDFormWizard(models.TransientModel):
    _name = 'print.pnd.form.wizard'

    income_tax_form = fields.Selection(
        INCOME_TAX_FORM,
        string='Income Tax Form',
        required=True,
    )
    calendar_period_id = fields.Many2one(
        'account.period.calendar',
        string='Calendar Period',
        required=True,
    )

    @api.multi
    def run_report(self):
        data = {'parameters': {}}
        data_dict = {}
        report_name = False
        if self.income_tax_form == 'pnd53':
            report_name = 'report_pnd53_form'
        if self.income_tax_form == 'pnd3':
            report_name = 'report_pnd3_form'
        if not report_name:
            raise ValidationError(_('Selected form not found!'))
        data_dict['income_tax_form'] = self.income_tax_form
        data_dict['wht_period_id'] = self.calendar_period_id.period_id.id
        company = self.env.user.company_id.partner_id
        company_taxid = len(company.vat or '') == 13 and company.vat or ''
        company_branch = \
            len(company.taxbranch or '') == 5 and company.taxbranch or ''
        data_dict['company_taxid'] = company_taxid
        data_dict['company_branch'] = company_branch
        data_dict['print_name'] = \
            self.env.user.name
        data_dict['print_position'] = \
            self.env.user.employee_id.position_id.name
        data['parameters'] = data_dict
        res = {
            'type': 'ir.actions.report.xml',
            'report_name': report_name,
            'datas': data,
            'context': {'lang': 'th_TH'},
        }
        return res