from odoo import api, fields, models, _

import logging
_logger = logging.getLogger(__name__)

class Documents(models.Model):
    _inherit = ["documents.document"]

    invoice_number = fields.Char(string="Invoice Number")
    amount = fields.Float(string="Monto")
    concept = fields.Char(string="Concept")
    date = fields.Date(string="Fecha publicación recibo")
    real_date = fields.Date(string="Fecha real publicación recibo")
    payment_type = fields.Selection([("check", "Check/ACH"), ("online", "Online / CC"), ("material", "Material")], string="Payment Type", store=True, default="")
    customer = fields.Many2one("res.partner", string="Customer")
    company = fields.Many2one("res.company", string="Company*") # duplicate string
    invoice_link = fields.Char(string="Invoice Link")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('access_internal', 'none') == 'none':
                vals['access_internal'] = 'edit'
        return super().create(vals_list)

    def _sync_payment_type_to_bill(self):
        for doc in self:
            if doc.payment_type and doc.res_model == 'account.move' and doc.res_id:
                bill = self.env['account.move'].sudo().browse(doc.res_id)
                if bill.exists() and bill.move_type == 'in_invoice':
                    bill.write({'payment_type_bills': doc.payment_type})

    def write(self, vals):
        res = super().write(vals)
        if 'payment_type' in vals:
            self._sync_payment_type_to_bill()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        docs = super().create(vals_list)
        docs.filtered(lambda d: d.payment_type)._sync_payment_type_to_bill()
        return docs
