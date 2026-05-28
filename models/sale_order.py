from collections import defaultdict
from contextlib import ExitStack, contextmanager
from datetime import date, timedelta
from hashlib import sha256
from json import dumps
import re
from textwrap import shorten
from unittest.mock import patch

from odoo import api, fields, models, _, Command
from odoo.addons.base.models.decimal_precision import DecimalPrecision
###from odoo.addons.account.tools import format_rf_reference


class SaleOrders(models.Model):
    _inherit = ["sale.order"]

    estimate_notes = fields.Text(string="Estimate Notes", help="Notes related to the estimate")
    
    custom_job_address = fields.Text(
        string="Custom Job Address",
        help="Editable job address field for external estimates not registered in Odoo"
    )
    
    @api.onchange('partner_shipping_id')
    def _onchange_partner_shipping_id(self):
        if self.partner_shipping_id:
            address_parts = []
            if self.partner_shipping_id.name:
                address_parts.append(self.partner_shipping_id.name)
            if self.partner_shipping_id.street:
                address_parts.append(self.partner_shipping_id.street)
            if self.partner_shipping_id.city or self.partner_shipping_id.zip:
                city_zip = ' '.join(filter(None, [str(self.partner_shipping_id.city or ''), str(self.partner_shipping_id.zip or '')]))
                if city_zip.strip():
                    address_parts.append(city_zip)
            
            self.custom_job_address = '\n'.join(address_parts) if address_parts else ''

    def action_cancel_button(self):
            self._action_cancel()
            """ Cancel SO after showing the cancel wizard when needed. (cfr :meth:`_show_cancel_wizard`)

            For post-cancel operations, please only override :meth:`_action_cancel`.

            note: self.ensure_one() if the wizard is shown.
            """
            '''for record in self:
                cancel_warning = record._show_cancel_wizard()
                if cancel_warning:
                    template_id = record.env['ir.model.data']._xmlid_to_res_id(
                        'sale.mail_template_sale_cancellation', raise_if_not_found=False
                    )
                    lang = record.env.context.get('lang')
                    template = record.env['mail.template'].browse(template_id)
                    if template.lang:
                        lang = template._render_lang(record.ids)[record.id]
                    ctx = {
                        'default_use_template': bool(template_id),
                        'default_template_id': template_id,
                        'default_order_id': record.id,
                        'mark_so_as_canceled': True,
                        'default_email_layout_xmlid': "mail.mail_notification_layout_with_responsible_signature",
                        'model_description': record.with_context(lang=lang).type_name,
                    }
                    return {
                        'name': _('Cancel %s', record.type_name),
                        'view_mode': 'form',
                        'res_model': 'sale.order.cancel',
                        'view_id': record.env.ref('sale.sale_order_cancel_view_form').id,
                        'type': 'ir.actions.act_window',
                        'context': ctx,
                        'target': 'new'
                    }
                else:'''
        
