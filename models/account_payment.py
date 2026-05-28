from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools.misc import format_date, formatLang

# Includes Inherit Classes for: AccountPayment, AccountPaymentRegister, AccountPaymentTerm

class AccountPayment(models.Model):
    _inherit = ["account.payment"]

    delivery_date = fields.Date(string="Delivery Date", store=True, readonly=False)
    can_reconcile = fields.Boolean(
        string="Can Reconcile",
        compute="_compute_can_reconcile",
        help="Indicates if this payment can be reconciled (bank or cash journal)"
    )
    
    @api.depends('state', 'journal_id', 'journal_id.type')
    def _compute_can_reconcile(self):
        """Compute if the payment can be reconciled (only for posted payments with bank, cash, or credit card journals)."""
        for payment in self:
            payment.can_reconcile = (
                payment.state == 'posted' and
                payment.journal_id and
                payment.journal_id.type in ('bank', 'cash', 'general')
            )
    
    def _get_related_bills(self):
        """Get vendor bills related to this payment"""
        self.ensure_one()
        bills = self.env['account.move']
        
        # Only process vendor payments (supplier bills)
        if self.partner_type != 'supplier':
            return bills
        
        # Get bills from reconciled invoice lines
        if self.move_id and self.move_id.line_ids:
            payment_lines = self.move_id.line_ids.filtered(
                lambda l: l.account_id.account_type == 'liability_payable'
            )
            
            for line in payment_lines:
                # Get matched debit lines (when we pay, we debit the payable account)
                # The credit side of the reconciliation is the bill's payable line
                if line.matched_credit_ids:
                    for matched in line.matched_credit_ids:
                        bill = matched.credit_move_id.move_id
                        if bill.move_type == 'in_invoice' and bill not in bills:
                            bills |= bill
                
                # Also check matched debit (for refunds or other cases)
                if line.matched_debit_ids:
                    for matched in line.matched_debit_ids:
                        bill = matched.debit_move_id.move_id
                        if bill.move_type == 'in_invoice' and bill not in bills:
                            bills |= bill
        
        return bills
    
    def _log_payment_details_to_bill(self, bill):
        """Log payment details to the message history of a specific vendor bill.
        Called at reconciliation time, so all payment data is guaranteed to be available.
        """
        self.ensure_one()
        payment_date = format_date(self.env, self.date) if self.date else 'N/A'
        payment_amount = formatLang(self.env, self.amount, currency_obj=self.currency_id) if self.amount else 'N/A'
        payment_ref = self.memo or self.payment_reference or 'N/A'
        check_number = getattr(self, 'check_number', False) or 'N/A'
        bank_account = self.journal_id.name if self.journal_id else 'N/A'

        message_body = f"""
            <div style="background-color: #D6EBF0; color: #000000; padding: 15px; margin: 10px; border-radius: 10px; border: 1px solid #AED9E1">
                <h3 style="margin-top: 0; color: #007bff;"><b>Payment Details</b></h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 5px; font-weight: bold; width: 40%;">Payment Number:</td>
                        <td style="padding: 5px;">{self.name or 'N/A'}</td>
                    </tr>
                    <tr>
                        <td style="padding: 5px; font-weight: bold;">Bank / Credit Card:</td>
                        <td style="padding: 5px;">{bank_account}</td>
                    </tr>
                    <tr>
                        <td style="padding: 5px; font-weight: bold;">Payment Date:</td>
                        <td style="padding: 5px;">{payment_date}</td>
                    </tr>
                    <tr>
                        <td style="padding: 5px; font-weight: bold;">Amount:</td>
                        <td style="padding: 5px;">{payment_amount}</td>
                    </tr>
                    <tr>
                        <td style="padding: 5px; font-weight: bold;">Check Number:</td>
                        <td style="padding: 5px;">{check_number}</td>
                    </tr>
                    <tr>
                        <td style="padding: 5px; font-weight: bold;">Memo / Reference:</td>
                        <td style="padding: 5px;">{payment_ref}</td>
                    </tr>
                </table>
            </div>
        """
        bill.message_post(
            body=message_body,
            subject=f"Payment Details - {self.name or 'Payment'}",
            message_type='notification',
        )

    def _log_payment_details_to_bills(self):
        """Log payment details to all vendor bills currently reconciled with this payment.
        Kept for backward compatibility; prefer _log_payment_details_to_bill(bill) called
        from account.partial.reconcile so the log fires at reconciliation time.
        """
        for payment in self:
            if payment.partner_type != 'supplier':
                continue
            for bill in payment._get_related_bills():
                payment._log_payment_details_to_bill(bill)
    

    @api.constrains("ref", "payment_method_line_id")
    def _check_ref(self):
        for payment in self:
            if not payment.memo and payment.payment_method_code == "new_ach_fast_payment":
                raise ValidationError(_("Payments require a memo"))

    @api.model
    def _get_method_codes_using_bank_account(self):
        res = super(AccountPayment, self)._get_method_codes_using_bank_account()
        res.append('new_ach_fast_payment')
        return res

    @api.model
    def _get_method_codes_needing_bank_account(self):
        res = super(AccountPayment, self)._get_method_codes_needing_bank_account()
        res.append('new_ach_fast_payment')
        return res

    
    def action_open_reconcile(self):
        """Open the bank reconciliation widget for bank, cash, and credit card journal payments."""
        self.ensure_one()
        
        if not self.journal_id:
            raise ValidationError(_("No journal is set on this payment."))
        
        if self.journal_id.type not in ('bank', 'cash', 'general'):
            raise ValidationError(_("Reconciliation is only available for bank, cash, and credit card journals."))
        
        if self.state != 'posted':
            raise ValidationError(_("Only posted payments can be reconciled."))
        
        return self.env['account.bank.statement.line']._action_open_bank_reconciliation_widget(
            default_context={
                'default_journal_id': self.journal_id.id,
                'search_default_journal_id': self.journal_id.id,
                'search_default_not_matched': True,
            },
        )


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account')

    def _post_payments(self, to_process, edit_mode=False):
        """ Post the newly created payments.

        :param to_process:  A list of python dictionary, one for each payment to create, containing:
                            * create_vals:  The values used for the 'create' method.
                            * to_reconcile: The journal items to perform the reconciliation.
                            * batch:        A python dict containing everything you want about the source journal items
                                            to which a payment will be created (see '_get_batches').
        :param edit_mode:   Is the wizard in edition mode.
        """

        payments = self.env['account.payment']
        for vals in to_process:
            if self.analytic_account_id:
                ar = vals['to_reconcile'][0]
                move = ar.move_id
                products = move.line_ids.filtered(lambda l: l.display_type == 'product').product_id
                        

                payment_id = vals['payment']
                if len(products.ids) == 1:
                    payment_id.move_id.line_ids.write({
                        'analytic_distribution': {str(self.analytic_account_id.id):100.00},
                        'product_id': products.id
                    })
                else:
                     payment_id.move_id.line_ids.write({
                        'analytic_distribution': {str(self.analytic_account_id.id):100.00}
                    })

            payments |= vals['payment']
        payments.action_post()



class AccountPartialReconcile(models.Model):
    """Hook into reconciliation to log payment details to vendor bill chatter.

    This fires at the exact moment a payment is matched to a bill line, which is
    AFTER action_post() completes, making it the only reliable trigger point.
    """
    _inherit = 'account.partial.reconcile'

    @api.model_create_multi
    def create(self, vals_list):
        result = super().create(vals_list)
        logged_pairs = set()

        # Batch-fetch all moves involved in these reconciliations
        all_move_ids = set()
        for rec in result:
            all_move_ids.add(rec.debit_move_id.move_id.id)
            all_move_ids.add(rec.credit_move_id.move_id.id)
        all_move_ids.discard(False)

        # Map move_id → payment for all relevant moves in one query
        payments_by_move = {
            p.move_id.id: p
            for p in self.env['account.payment'].search(
                [('move_id', 'in', list(all_move_ids))]
            )
        }

        for rec in result:
            debit_move = rec.debit_move_id.move_id
            credit_move = rec.credit_move_id.move_id

            if payments_by_move.get(debit_move.id) and credit_move.move_type == 'in_invoice':
                payment = payments_by_move[debit_move.id]
                bill = credit_move
            elif payments_by_move.get(credit_move.id) and debit_move.move_type == 'in_invoice':
                payment = payments_by_move[credit_move.id]
                bill = debit_move
            else:
                continue

            if payment.partner_type != 'supplier':
                continue

            pair = (payment.id, bill.id)
            if pair not in logged_pairs:
                logged_pairs.add(pair)
                payment._log_payment_details_to_bill(bill)

        return result


class AccountPaymentTerm(models.Model):
    _inherit = 'account.payment.term'

    anticipated_payment = fields.Boolean(string='Anticipated Payment', default=False)
    utility_payment = fields.Boolean("Utility Payment", default=False)
    material_payment = fields.Boolean("Material Payment", default=False)