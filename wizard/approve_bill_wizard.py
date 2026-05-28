# -*- coding: utf-8 -*-
from odoo import fields, models, _


class ApproveBillsWizard(models.TransientModel):
    _name = 'approve.bills.wizard'
    _description = 'Approve Bills Wizard'

    user_ids = fields.Many2many("res.users", string="User", required=True)
    
    def generate_bill_approval_reports(self):
        self.ensure_one()
        # Return the saved action (with its database id) instead of an anonymous
        # inline dict. Odoo's web client uses the action id to encode the current
        # search state (filters, grouping, sort order) in the URL hash, so that
        # navigating into a bill and pressing Back in the breadcrumb restores the
        # exact list state the user had configured.
        action = self.env.ref('pms.approve_bills_action').sudo().read()[0]
        return action


    
