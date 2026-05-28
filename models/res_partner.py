from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

import logging
_logger = logging.getLogger(__name__)
import base64
import imghdr

class ResPartnerInherit(models.Model):
    _inherit = 'res.partner'

    liability_insurance = fields.One2many("contact.liabilityinsurance", "original_partner", string="Liability Insurance")
    ytd_1099_payments = fields.Float(
        string="YTD 1099 Payments",
        compute="_compute_ytd_1099_payments",
        store=False,
    )
    missing_1099_box = fields.Boolean(
        string="Missing 1099 Classification",
        compute="_compute_missing_1099_box",
        store=False,
    )
    approaching_1099_threshold = fields.Boolean(
        string="Approaching 1099 Threshold",
        compute="_compute_missing_1099_box",
        store=False,
    )

    @api.depends('supplier_rank', 'box_1099_id')
    def _compute_ytd_1099_payments(self):
        from datetime import date
        current_year = date.today().year
        for partner in self:
            if partner.supplier_rank > 0 and partner.id:
                self.env.cr.execute("""
                    SELECT COALESCE(SUM(aml.balance), 0)
                    FROM account_move_line aml
                    INNER JOIN account_account aa ON aml.account_id = aa.id
                    WHERE aml.partner_id = %s
                        AND aa.account_type IN ('expense', 'expense_depreciation', 'expense_direct_cost')
                        AND aml.parent_state = 'posted'
                        AND EXTRACT(YEAR FROM aml.date) = %s
                """, (partner.id, current_year))
                result = self.env.cr.fetchone()
                partner.ytd_1099_payments = result[0] if result else 0.0
            else:
                partner.ytd_1099_payments = 0.0

    @api.depends('supplier_rank', 'box_1099_id', 'vat')
    def _compute_missing_1099_box(self):
        for partner in self:
            is_vendor = partner.supplier_rank > 0
            has_box = bool(partner.box_1099_id)
            ytd = partner.ytd_1099_payments
            partner.missing_1099_box = is_vendor and not has_box and ytd >= 600
            partner.approaching_1099_threshold = is_vendor and not has_box and 400 <= ytd < 600

    @api.constrains('vat', 'street', 'supplier_rank')
    def _check_vendor_required_fields(self):
        for record in self:
            if record.supplier_rank > 0:
                if not record.vat:
                    raise ValidationError(_("Tax ID is required for vendors."))
                if not record.street:
                    raise ValidationError(_("Address is required for vendors."))
    authorized_signature  = fields.Binary(string="Authorized Signature")
    check_history = fields.One2many("check.maker.payment", "contact", string="Check History")
    # partner_daily_report = fields.Many2one('pms.daily.report', string='Daily Report Properties')

    bank_name = fields.Char(string="Bank Name", size=30)
    bank_address = fields.Char(string="Bank Address", size=30)
    bank_2address = fields.Char(string="Second Bank Address", size=30)
    bank_account_number = fields.Char(string="Bank Account Number*") # duplicate string
    bank_routing_number = fields.Char(string="Bank Routing Number")
    last_check_number = fields.Char(string="Last Check Number")
    call_day = fields.Selection( string="Visit Day", selection=[
        ("monday", "Monday"), ("tuesday", "Tuesday"), ("wednesday", "Wednesday"), 
        ("thursday", "Thursday"), ("friday", "Friday"), ("saturday", "Saturday"), 
        ("sunday", "Sunday"), ("any", "Any")], default="any"
    )

    contact_id = fields.Char(string="Contact ID")

    contractor_payment_terms = fields.Many2one('account.payment.term', string='Contractor Payment Terms')
        
    # Dashboard fields for auth
    # contractor_portal = fields.Boolean(string="Contractor Portal", readonly=True, default=False)
    # customer_portal = fields.Boolean(string="Customer Portal", readonly=True, default=False)
    # portal_key = fields.Char(string="Portal Key", readonly=True)

    def print_all_checks(self):
        self.ensure_one()

        if self.check_history:
            # Capture the action dictionary returned by create_checks
            action = self.check_history.create_checks(skip_printed=True)
            
            # This print statement will appear in the Odoo server logs
            _logger.info("Generated Action:", action) 
            
            # Return the action to the client
            return action

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'No Checks',
                'message': 'This contact has no checks to print.',
                'sticky': False,
            }
        }

    def create_check_button(self):
        wizard_view = self.env.ref('pms.create_check_wizard_view_form')
        return {
            'view_mode': 'form',
            'res_model': 'create.check.wizard',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'view_id': wizard_view.id,
            'context': {
                'default_bank_name': self.bank_name,
                'default_bank_address': self.bank_address,
                'default_bank_2address': self.bank_2address,
                'default_bank_account_number': self.bank_account_number,
                'default_bank_routing_number': self.bank_routing_number,
                'default_partner_id': self.id,
                'default_authorized_signature': self.authorized_signature,
            },
        }

    @api.constrains('authorized_signature')
    def _check_authorized_signature_format(self):
        for record in self:
            if record.authorized_signature:
                authorized_signature_data = base64.b64decode(record.authorized_signature)
                authorized_signature_type = imghdr.what(None, authorized_signature_data)
                if authorized_signature_type != 'png':
                    raise ValidationError("Only PNG images are allowed.")
                

    def open_message_crm_wizard(self):
        for record in self:
            if not record.email:
                raise ValidationError(_("Email field cannot be empty."))
            if not record.phone and not record.mobile:
                raise ValidationError(_("Either phone or mobile field must be filled."))

        wizard_view = self.env.ref('pms.view_message_crm_wizard_form')
        name_parts = record.display_name.split(' ', 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ''
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'message.crm.wizard',
            'view_id': wizard_view.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_partner_id': self.id,
                'default_invoice_id': None,
                'default_contact_id': self.contact_id if self.contact_id else None,
                'default_first_name': first_name,
                'default_last_name': last_name,
                'default_email': self.email,
                'default_phone_number': self.phone or self.mobile,
            },
        }

    


