from odoo import api, fields, models, tools


class Vendor1099Compliance(models.Model):
    _name = "vendor.1099.compliance"
    _description = "1099 Compliance Monitor"
    _auto = False
    _order = "ytd_total desc"

    partner_id = fields.Many2one("res.partner", readonly=True, string="Vendor")
    partner_vat = fields.Char(readonly=True, string="Tax ID (TIN/EIN)")
    partner_street = fields.Char(readonly=True, string="Address")
    box_1099_id = fields.Many2one("l10n_us.1099_box", readonly=True, string="1099 Box")
    ytd_total = fields.Float(readonly=True, string="YTD Payments")
    last_payment_date = fields.Date(readonly=True, string="Last Payment")
    payment_count = fields.Integer(readonly=True, string="# Payments")
    compliance_status = fields.Selection([
        ('ok', 'Compliant'),
        ('at_risk', 'Approaching $600'),
        ('non_compliant', 'Missing 1099 Box (>$600)'),
        ('missing_tin', 'Missing TIN/EIN'),
        ('missing_address', 'Missing Address'),
    ], readonly=True, string="Status")
    company_id = fields.Many2one("res.company", readonly=True, string="Company")
    fiscal_year = fields.Char(readonly=True, string="Fiscal Year")

    @property
    def _table_query(self):
        return f"""
            SELECT
                rp.id AS id,
                rp.id AS partner_id,
                rp.vat AS partner_vat,
                rp.street AS partner_street,
                rp.box_1099_id AS box_1099_id,
                COALESCE(pay.ytd_total, 0) AS ytd_total,
                pay.last_payment_date AS last_payment_date,
                COALESCE(pay.payment_count, 0) AS payment_count,
                pay.company_id AS company_id,
                COALESCE(pay.fiscal_year, EXTRACT(YEAR FROM CURRENT_DATE)::TEXT) AS fiscal_year,
                CASE
                    WHEN rp.box_1099_id IS NULL AND COALESCE(pay.ytd_total, 0) >= 600
                        THEN 'non_compliant'
                    WHEN rp.vat IS NULL AND rp.supplier_rank > 0
                        THEN 'missing_tin'
                    WHEN rp.street IS NULL AND rp.supplier_rank > 0
                        THEN 'missing_address'
                    WHEN rp.box_1099_id IS NULL AND COALESCE(pay.ytd_total, 0) >= 400
                        THEN 'at_risk'
                    ELSE 'ok'
                END AS compliance_status
            FROM res_partner rp
            LEFT JOIN (
                SELECT
                    aml.partner_id,
                    aml.company_id,
                    EXTRACT(YEAR FROM aml.date)::TEXT AS fiscal_year,
                    SUM(aml.balance) AS ytd_total,
                    MAX(aml.date) AS last_payment_date,
                    COUNT(DISTINCT aml.move_id) AS payment_count
                FROM account_move_line aml
                INNER JOIN account_account aa ON aml.account_id = aa.id
                WHERE aa.account_type IN ('expense', 'expense_depreciation', 'expense_direct_cost')
                    AND aml.parent_state = 'posted'
                    AND EXTRACT(YEAR FROM aml.date) = EXTRACT(YEAR FROM CURRENT_DATE)
                GROUP BY aml.partner_id, aml.company_id, EXTRACT(YEAR FROM aml.date)::TEXT
            ) pay ON rp.id = pay.partner_id
            WHERE rp.supplier_rank > 0
                AND rp.active = true
        """

    def action_open_partner(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'res_id': self.partner_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    @api.model
    def run_compliance_check(self):
        non_compliant = self.search([
            ('compliance_status', 'in', ('non_compliant', 'missing_tin', 'missing_address')),
        ])
        if not non_compliant:
            return

        accounting_group = self.env.ref('account.group_account_manager', raise_if_not_found=False)
        if not accounting_group:
            return

        users = accounting_group.users
        if not users:
            return

        body_lines = []
        for rec in non_compliant:
            status_label = dict(self._fields['compliance_status'].selection).get(rec.compliance_status, '')
            body_lines.append(
                f"<li><b>{rec.partner_id.name}</b> — ${rec.ytd_total:,.2f} YTD — {status_label}</li>"
            )

        body = (
            f"<p><b>1099 Compliance Alert — {len(non_compliant)} vendor(s) require attention:</b></p>"
            f"<ul>{''.join(body_lines)}</ul>"
            f"<p>Please review and update the 1099 Box classification, TIN, or address on these vendors.</p>"
        )

        for user in users:
            self.env['mail.message'].create({
                'subject': f'1099 Compliance Alert: {len(non_compliant)} vendor(s) at risk',
                'body': body,
                'message_type': 'notification',
                'subtype_id': self.env.ref('mail.mt_note').id,
                'partner_ids': [(4, user.partner_id.id)],
                'model': 'vendor.1099.compliance',
            })
