# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)

_PMS_SEARCH_INHERIT_NAME = 'cc.programmed.payment.search.pms.paid_to_pay'


def _ensure_cc_programmed_payment_search_filters(env):
    if 'cc.programmed.payment' not in env:
        _logger.info('pms hooks: model cc.programmed.payment not loaded; skip')
        return
    Model = env['cc.programmed.payment']
    if 'state' not in Model._fields:
        _logger.warning('pms hooks: cc.programmed.payment has no field "state"; skip')
        return
    View = env['ir.ui.view'].sudo()
    base = View.search(
        [('model', '=', 'cc.programmed.payment'), ('type', '=', 'search')],
        order='priority desc, id desc',
        limit=1,
    )
    if not base:
        _logger.warning('pms hooks: no search view found for cc.programmed.payment')
        return
    if View.search([('name', '=', _PMS_SEARCH_INHERIT_NAME)], limit=1):
        return
    arch = """
        <data>
            <xpath expr="//search" position="inside">
                <separator/>
                <filter string="Paid" name="pms_paid" domain="[('state', '=', 'paid')]"/>
                <filter string="To pay" name="pms_to_pay" domain="[('state', '!=', 'paid')]"/>
            </xpath>
        </data>
    """
    View.create({
        'name': _PMS_SEARCH_INHERIT_NAME,
        'model': 'cc.programmed.payment',
        'inherit_id': base.id,
        'arch': arch.strip(),
        'priority': 99,
    })
    _logger.info('pms hooks: Request Payments filters ensured on view id=%s', base.id)


def _clean_analytic_distribution_update_key(cr):
    """Remove the __update__ sentinel key from analytic_distribution JSONB field."""
    cr.execute("""
        UPDATE account_move_line
        SET analytic_distribution = analytic_distribution - '__update__'
        WHERE analytic_distribution ? '__update__'
    """)
    count = cr.rowcount
    if count:
        _logger.info('pms hooks: cleaned __update__ key from %d account_move_line rows', count)


def post_init_hook(cr, registry):
    from odoo import api, SUPERUSER_ID
    env = api.Environment(cr, SUPERUSER_ID, {})
    _ensure_cc_programmed_payment_search_filters(env)
    _clean_analytic_distribution_update_key(cr)
