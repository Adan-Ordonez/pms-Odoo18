from odoo import models, fields, tools, _, api
from odoo.exceptions import ValidationError, UserError

import logging
_logger = logging.getLogger(__name__)

class BillInvoiceGroupedReport(models.Model):
    _name = "bill.invoice.grouped.report"
    _description = "Bill-Invoice Grouped Report"
    _auto = False
    _order = "bill_date desc"
    
    id = fields.Integer(string="ID", readonly=True)
    bill_id = fields.Many2one("account.move", string="Bill", readonly=True)
    bill_name = fields.Char(string="Bill Number", readonly=True)
    bill_date = fields.Date(string="Bill Date", readonly=True)
    bill_partner = fields.Char(string="Vendor", readonly=True)
    bill_amount = fields.Float(string="Bill Amount", readonly=True)
    bill_ref = fields.Char(string="Bill Reference", readonly=True)
    
    invoice_ids = fields.Char(string="Invoice IDs", readonly=True)
    invoice_names = fields.Char(string="Invoice Numbers", readonly=True)
    invoice_count = fields.Integer(string="# Invoices", readonly=True)
    
    total_sales = fields.Float(string="Total Sales", readonly=True)
    total_purchases = fields.Float(string="Total Purchases", readonly=True)
    profit = fields.Float(string="Profit", readonly=True)
    margin = fields.Float(string="Margin %", readonly=True)
    
    analytic_accounts = fields.Char(string="Analytic Accounts", readonly=True)
    product_inv = fields.Char(string="Products", readonly=True)
    house_model = fields.Many2one("pms.housemodels", string="House Model", readonly=True)
    
    state = fields.Selection(string="Status", readonly=True, selection=[
        ('draft', 'Draft'),
        ('posted', 'Posted'),
        ('cancel', 'Cancelled'),
    ])
    payment_state = fields.Selection(string="Payment Status", readonly=True, selection=[
        ('not_paid', 'Not Paid'),
        ('in_payment', 'In Payment'),
        ('paid', 'Paid'),
        ('partial', 'Partially Paid'),
        ('reversed', 'Reversed'),
        ('invoicing_legacy', 'Invoicing App Legacy'),
    ])
    
    def open_bill(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Bill',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.bill_id.id,
            'target': 'current',
        }
    
    def open_related_invoices(self):
        self.ensure_one()
        if not self.invoice_ids:
            raise UserError(_("No related invoices found."))
        
        invoice_id_list = [int(id_str) for id_str in self.invoice_ids.split(',') if id_str]
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Related Invoices',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', invoice_id_list)],
            'target': 'current',
        }
    
    def init(self):
        tools.drop_view_if_exists(self._cr, 'bill_invoice_grouped_report')
        self._cr.execute("""
            CREATE OR REPLACE VIEW bill_invoice_grouped_report AS (
                SELECT
                    am.id AS id,
                    am.id AS bill_id,
                    am.name AS bill_name,
                    am.invoice_date AS bill_date,
                    am.invoice_partner_display_name AS bill_partner,
                    ABS(am.amount_total_signed) AS bill_amount,
                    am.ref AS bill_ref,
                    am.state AS state,
                    am.payment_state AS payment_state,
                    
                    (
                        SELECT STRING_AGG(CAST(rel.invoice_id AS TEXT), ',')
                        FROM account_move_invoice_bill_rel AS rel
                        WHERE rel.bill_id = am.id
                    ) AS invoice_ids,
                    
                    (
                        SELECT STRING_AGG(inv.name, ', ')
                        FROM account_move_invoice_bill_rel AS rel
                        INNER JOIN account_move AS inv ON rel.invoice_id = inv.id
                        WHERE rel.bill_id = am.id
                    ) AS invoice_names,
                    
                    (
                        SELECT COUNT(DISTINCT rel.invoice_id)
                        FROM account_move_invoice_bill_rel AS rel
                        WHERE rel.bill_id = am.id
                    ) AS invoice_count,
                    
                    (
                        SELECT COALESCE(SUM(inv.amount_total_signed), 0)
                        FROM account_move_invoice_bill_rel AS rel
                        INNER JOIN account_move AS inv ON rel.invoice_id = inv.id
                        WHERE rel.bill_id = am.id AND inv.move_type = 'out_invoice'
                    ) AS total_sales,
                    
                    ABS(am.amount_total_signed) AS total_purchases,
                    
                    (
                        SELECT COALESCE(SUM(inv.amount_total_signed), 0) - ABS(am.amount_total_signed)
                        FROM account_move_invoice_bill_rel AS rel
                        INNER JOIN account_move AS inv ON rel.invoice_id = inv.id
                        WHERE rel.bill_id = am.id AND inv.move_type = 'out_invoice'
                    ) AS profit,
                    
                    (
                        SELECT 
                            CASE 
                                WHEN COALESCE(SUM(inv.amount_total_signed), 0) != 0 
                                THEN ((COALESCE(SUM(inv.amount_total_signed), 0) - ABS(am.amount_total_signed)) / COALESCE(SUM(inv.amount_total_signed), 0)) * 100
                                ELSE 0
                            END
                        FROM account_move_invoice_bill_rel AS rel
                        INNER JOIN account_move AS inv ON rel.invoice_id = inv.id
                        WHERE rel.bill_id = am.id AND inv.move_type = 'out_invoice'
                    ) AS margin,
                    
                    (
                        SELECT STRING_AGG(DISTINCT aaa.name::text, ',')
                        FROM account_move_line AS aml
                        CROSS JOIN jsonb_each(aml.analytic_distribution) AS analytic_entry  
                        INNER JOIN account_analytic_account AS aaa ON aaa.id = analytic_entry.key::int 
                        WHERE aml.move_id = am.id
                        GROUP BY aml.move_id  
                    ) AS analytic_accounts,
                    
                    (
                        SELECT STRING_AGG(COALESCE(pt.name->>'en_US', pt.name::text), ',')
                        FROM account_move_line AS aml
                        INNER JOIN product_product AS pp ON aml.product_id = pp.id
                        INNER JOIN product_template AS pt ON pp.product_tmpl_id = pt.id
                        WHERE aml.move_id = am.id
                    ) AS product_inv,
                    
                    (
                        SELECT MAX(pp.house_model)
                        FROM account_move_line AS aml
                        CROSS JOIN jsonb_each(aml.analytic_distribution) AS analytic_entry
                        INNER JOIN account_analytic_account AS aaa ON aaa.id = analytic_entry.key::int
                        LEFT JOIN pms_property AS pp ON pp.analytical_account = aaa.id
                        WHERE aml.move_id = am.id
                        AND pp.house_model IS NOT NULL
                    ) AS house_model
                    
                FROM account_move am
                WHERE am.move_type = 'in_invoice'
            )
        """)


class InvoiceBillGroupedReport(models.Model):
    _name = "invoice.bill.grouped.report"
    _description = "Invoice-Bill Grouped Report"
    _auto = False
    _order = "invoice_date desc"
    
    id = fields.Integer(string="ID", readonly=True)
    invoice_id = fields.Many2one("account.move", string="Invoice", readonly=True)
    invoice_name = fields.Char(string="Invoice Number", readonly=True)
    invoice_date = fields.Date(string="Invoice Date", readonly=True)
    invoice_partner = fields.Char(string="Customer", readonly=True)
    invoice_amount = fields.Float(string="Invoice Amount", readonly=True)
    invoice_ref = fields.Char(string="Invoice Reference", readonly=True)
    
    bill_ids = fields.Char(string="Bill IDs", readonly=True)
    bill_names = fields.Char(string="Bill Numbers", readonly=True)
    bill_count = fields.Integer(string="# Bills", readonly=True)
    
    total_sales = fields.Float(string="Total Sales", readonly=True)
    total_purchases = fields.Float(string="Total Purchases", readonly=True)
    profit = fields.Float(string="Profit", readonly=True)
    margin = fields.Float(string="Margin %", readonly=True)
    
    analytic_accounts = fields.Char(string="Analytic Accounts", readonly=True)
    product_inv = fields.Char(string="Products", readonly=True)
    house_model = fields.Many2one("pms.housemodels", string="House Model", readonly=True)
    
    state = fields.Selection(string="Status", readonly=True, selection=[
        ('draft', 'Draft'),
        ('posted', 'Posted'),
        ('cancel', 'Cancelled'),
    ])
    payment_state = fields.Selection(string="Payment Status", readonly=True, selection=[
        ('not_paid', 'Not Paid'),
        ('in_payment', 'In Payment'),
        ('paid', 'Paid'),
        ('partial', 'Partially Paid'),
        ('reversed', 'Reversed'),
        ('invoicing_legacy', 'Invoicing App Legacy'),
    ])
    
    def open_invoice(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Invoice',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.invoice_id.id,
            'target': 'current',
        }
    
    def open_related_bills(self):
        self.ensure_one()
        if not self.bill_ids:
            raise UserError(_("No related bills found."))
        
        bill_id_list = [int(id_str) for id_str in self.bill_ids.split(',') if id_str]
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Related Bills',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', bill_id_list)],
            'target': 'current',
        }
    
    def init(self):
        tools.drop_view_if_exists(self._cr, 'invoice_bill_grouped_report')
        self._cr.execute("""
            CREATE OR REPLACE VIEW invoice_bill_grouped_report AS (
                SELECT
                    am.id AS id,
                    am.id AS invoice_id,
                    am.name AS invoice_name,
                    am.invoice_date AS invoice_date,
                    am.invoice_partner_display_name AS invoice_partner,
                    ABS(am.amount_total_signed) AS invoice_amount,
                    am.ref AS invoice_ref,
                    am.state AS state,
                    am.payment_state AS payment_state,
                    
                    (
                        SELECT STRING_AGG(CAST(rel.bill_id AS TEXT), ',')
                        FROM account_move_invoice_bill_rel AS rel
                        WHERE rel.invoice_id = am.id
                    ) AS bill_ids,
                    
                    (
                        SELECT STRING_AGG(bill.name, ', ')
                        FROM account_move_invoice_bill_rel AS rel
                        INNER JOIN account_move AS bill ON rel.bill_id = bill.id
                        WHERE rel.invoice_id = am.id
                    ) AS bill_names,
                    
                    (
                        SELECT COUNT(DISTINCT rel.bill_id)
                        FROM account_move_invoice_bill_rel AS rel
                        WHERE rel.invoice_id = am.id
                    ) AS bill_count,
                    
                    ABS(am.amount_total_signed) AS total_sales,
                    
                    (
                        SELECT COALESCE(SUM(ABS(bill.amount_total_signed)), 0)
                        FROM account_move_invoice_bill_rel AS rel
                        INNER JOIN account_move AS bill ON rel.bill_id = bill.id
                        WHERE rel.invoice_id = am.id AND bill.move_type = 'in_invoice'
                    ) AS total_purchases,
                    
                    (
                        SELECT ABS(am.amount_total_signed) - COALESCE(SUM(ABS(bill.amount_total_signed)), 0)
                        FROM account_move_invoice_bill_rel AS rel
                        INNER JOIN account_move AS bill ON rel.bill_id = bill.id
                        WHERE rel.invoice_id = am.id AND bill.move_type = 'in_invoice'
                    ) AS profit,
                    
                    (
                        SELECT 
                            CASE 
                                WHEN ABS(am.amount_total_signed) != 0 
                                THEN ((ABS(am.amount_total_signed) - COALESCE(SUM(ABS(bill.amount_total_signed)), 0)) / ABS(am.amount_total_signed)) * 100
                                ELSE 0
                            END
                        FROM account_move_invoice_bill_rel AS rel
                        INNER JOIN account_move AS bill ON rel.bill_id = bill.id
                        WHERE rel.invoice_id = am.id AND bill.move_type = 'in_invoice'
                    ) AS margin,
                    
                    (
                        SELECT STRING_AGG(DISTINCT aaa.name::text, ',')
                        FROM account_move_line AS aml
                        CROSS JOIN jsonb_each(aml.analytic_distribution) AS analytic_entry  
                        INNER JOIN account_analytic_account AS aaa ON aaa.id = analytic_entry.key::int 
                        WHERE aml.move_id = am.id
                        GROUP BY aml.move_id  
                    ) AS analytic_accounts,
                    
                    (
                        SELECT STRING_AGG(COALESCE(pt.name->>'en_US', pt.name::text), ', ')
                        FROM account_move_line AS aml
                        INNER JOIN product_product AS pp ON aml.product_id = pp.id
                        INNER JOIN product_template AS pt ON pp.product_tmpl_id = pt.id
                        WHERE aml.move_id = am.id
                    ) AS product_inv,
                    
                    (
                        SELECT MAX(pp.house_model)
                        FROM account_move_line AS aml
                        CROSS JOIN jsonb_each(aml.analytic_distribution) AS analytic_entry
                        INNER JOIN account_analytic_account AS aaa ON aaa.id = analytic_entry.key::int
                        LEFT JOIN pms_property AS pp ON pp.analytical_account = aaa.id
                        WHERE aml.move_id = am.id
                        AND pp.house_model IS NOT NULL
                    ) AS house_model
                    
                FROM account_move am
                WHERE am.move_type = 'out_invoice'
            )
        """)

