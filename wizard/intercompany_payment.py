import logging
_logger = logging.getLogger(__name__)
import base64
from collections import defaultdict
from contextlib import ExitStack, contextmanager
from datetime import date, timedelta, datetime
from hashlib import sha256
from json import dumps
import re
from textwrap import shorten
from unittest.mock import patch
from odoo.tools.misc import clean_context, format_date
from odoo import http
from odoo import api, fields, models, _, Command
from odoo.addons.base.models.decimal_precision import DecimalPrecision
import ast
from collections import defaultdict
from contextlib import contextmanager
from datetime import date, timedelta
from functools import lru_cache
import requests
import json
import io
import zipfile
from odoo import api, fields, models, Command, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools import frozendict, formatLang, format_date, float_compare, Query
from odoo.tools.sql import create_index
from odoo.addons.web.controllers.utils import clean_action
from werkzeug import urls
from odoo.addons.account.models.account_move import MAX_HASH_VERSION

from odoo import api, fields, models, _, Command
from odoo.osv import expression
from odoo.tools.float_utils import float_round
from odoo.exceptions import UserError, ValidationError
from odoo.tools.misc import formatLang
from odoo.tools import frozendict

from collections import defaultdict
import math
import re
import base64
import collections
import datetime
import hashlib
import pytz
import threading
import re

import requests
from collections import defaultdict
from random import randint
from werkzeug import urls

from odoo import api, fields, models, tools, SUPERUSER_ID, _, Command
from odoo.osv.expression import get_unaccent_wrapper
from odoo.exceptions import RedirectWarning, UserError, ValidationError

class IntercompanyWizardCC(models.TransientModel):
    _name = "intercompany.wizard"
    _description = "Intercompany Wizard"

    company_to_pay = fields.Many2one('res.company', string='Company to Pay', required=True)
    card_journal = fields.Many2one('account.journal', string='Payment Journal', required=True, domain="[('company_id', '=', company_to_pay), ('type', 'in', ['cash', 'bank'])]")
    payment_date = fields.Date(string='Payment Date', required=True, default=fields.Date.today)
    amount_total = fields.Float(string='Bill Total', readonly=True)
    amount_due = fields.Float(string='Amount Due', readonly=True)
    amount = fields.Float(string='Amount to Pay', required=True,
                          help="Enter a partial amount to register an installment payment. "
                               "Cannot exceed the current Amount Due.")

    def _find_account(self, code, company_id):
        """Find an account by code using the target company context."""
        account = self.env['account.account'].sudo().with_company(company_id).search(
            [('code', '=', code)], limit=1,
        )
        if not account:
            raise UserError(
                _("Account with code '%s' not found for company %s.", code, self.env['res.company'].browse(company_id).name)
            )
        return account

    def make_intercompany_payment(self):
        main_company = self._context.get('default_company_id')
        display_amount = self.amount
        provider = self._context.get('default_provider')
        record_id = self._context.get('default_id')
        reference = self._context.get('references')

        _logger.info("=== INTERCOMPANY PAYMENT DEBUG ===")
        _logger.info("main_company=%s, provider=%s, record_id=%s, amount=%s, reference=%s",
                      main_company, provider, record_id, display_amount, reference)

        if display_amount <= 0:
            raise UserError(_('The amount to pay must be greater than zero.'))
        if display_amount > self.amount_due + 0.01:
            raise UserError(_('The amount to pay cannot exceed the amount due (%.2f).') % self.amount_due)

        amount = abs(display_amount)

        loan_main = self._find_account('200401', main_company)
        payable_main = self._find_account('211000', main_company)
        loan_other = self._find_account('200401', self.company_to_pay.id)

        main_company_partner = self.env['res.company'].browse(main_company).partner_id

        outstanding_lines = self.card_journal.outbound_payment_method_line_ids.filtered(
            lambda l: l.payment_method_id.code == 'manual'
        )
        if not outstanding_lines:
            outstanding_lines = self.card_journal.outbound_payment_method_line_ids[:1]
        outstanding_account = outstanding_lines.payment_account_id
        if not outstanding_account:
            outstanding_account = self.card_journal.default_account_id
        if not outstanding_account:
            raise UserError(_('No outstanding payments account found for journal %s.') % self.card_journal.name)

        bill = self.env['account.move'].browse(record_id)
        is_refund = bill.move_type in ('in_refund', 'out_refund')

        if is_refund:
            main_journal_entry_lines = [
                (0, 0, {
                    'name': 'Loan between related companies',
                    'partner_id': self.company_to_pay.partner_id.id,
                    'account_id': loan_main.id,
                    'debit': amount,
                    'credit': 0.0,
                }),
                (0, 0, {
                    'name': 'Account Payable',
                    'partner_id': provider,
                    'account_id': payable_main.id,
                    'debit': 0.0,
                    'credit': amount,
                }),
            ]
        else:
            main_journal_entry_lines = [
                (0, 0, {
                    'name': 'Loan between related companies',
                    'partner_id': self.company_to_pay.partner_id.id,
                    'account_id': loan_main.id,
                    'debit': 0.0,
                    'credit': amount,
                }),
                (0, 0, {
                    'name': 'Account Payable',
                    'partner_id': provider,
                    'account_id': payable_main.id,
                    'debit': amount,
                    'credit': 0.0,
                }),
            ]

        main_journal_entry = self.env['account.move'].sudo().create({
            'move_type': 'entry',
            'partner_id': provider,
            'company_id': main_company,
            'ref': reference,
            'date': self.payment_date,
            'line_ids': main_journal_entry_lines,
        })

        if is_refund:
            other_journal_entry_lines = [
                (0, 0, {
                    'name': 'Loan between related companies',
                    'partner_id': main_company_partner.id,
                    'account_id': loan_other.id,
                    'debit': 0.0,
                    'credit': amount,
                }),
                (0, 0, {
                    'name': 'Outstanding Payments',
                    'partner_id': provider,
                    'account_id': outstanding_account.id,
                    'debit': amount,
                    'credit': 0.0,
                }),
            ]
        else:
            other_journal_entry_lines = [
                (0, 0, {
                    'name': 'Loan between related companies',
                    'partner_id': main_company_partner.id,
                    'account_id': loan_other.id,
                    'debit': amount,
                    'credit': 0.0,
                }),
                (0, 0, {
                    'name': 'Outstanding Payments',
                    'partner_id': provider,
                    'account_id': outstanding_account.id,
                    'debit': 0.0,
                    'credit': amount,
                }),
            ]

        other_journal_entry = self.env['account.move'].sudo().create({
            'move_type': 'entry',
            'partner_id': provider,
            'ref': reference,
            'company_id': self.company_to_pay.id,
            'date': self.payment_date,
            'line_ids': other_journal_entry_lines,
        })

        main_journal_entry.action_post()
        other_journal_entry.action_post()
        _logger.info("Main JE: id=%s state=%s lines=%s", main_journal_entry.id, main_journal_entry.state,
                      [(l.account_id.code, l.debit, l.credit, l.account_id.account_type, l.partner_id.id) for l in main_journal_entry.line_ids])
        _logger.info("Other JE: id=%s state=%s lines=%s", other_journal_entry.id, other_journal_entry.state,
                      [(l.account_id.code, l.debit, l.credit, l.account_id.account_type, l.partner_id.id) for l in other_journal_entry.line_ids])

        domain = [
            ('parent_state', '=', 'posted'),
            ('account_type', 'in', ('asset_receivable', 'liability_payable')),
            ('reconciled', '=', False),
        ]
        bill = self.env['account.move'].browse(record_id)
        payment = self.env['account.move'].browse(main_journal_entry.id)
        bill_line = bill.line_ids.filtered_domain(domain)
        payment_line = payment.line_ids.filtered_domain(domain)

        _logger.info("Bill: id=%s state=%s lines_to_reconcile=%s",
                      bill.id, bill.state,
                      [(l.id, l.account_id.code, l.debit, l.credit, l.account_id.account_type, l.reconciled, l.partner_id.id) for l in bill_line])
        _logger.info("Payment lines_to_reconcile=%s",
                      [(l.id, l.account_id.code, l.debit, l.credit, l.account_id.account_type, l.reconciled, l.partner_id.id) for l in payment_line])

        if not payment_line:
            _logger.warning("NO payment lines found for reconciliation!")
        if not bill_line:
            _logger.warning("NO bill lines found for reconciliation!")

        for account in payment_line.account_id:
            lines_to_rec = (payment_line + bill_line).filtered_domain([('account_id', '=', account.id), ('reconciled', '=', False)])
            _logger.info("Reconciling account %s with %d lines: %s", account.code, len(lines_to_rec),
                          [(l.id, l.debit, l.credit, l.partner_id.id) for l in lines_to_rec])
            try:
                lines_to_rec.reconcile()
                _logger.info("Reconciliation SUCCESS")
            except Exception as e:
                _logger.error("Reconciliation FAILED: %s", e)
