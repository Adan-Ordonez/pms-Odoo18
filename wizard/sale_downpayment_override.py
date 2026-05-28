from odoo import _, models
from odoo.tools.misc import formatLang


class SaleAdvancePaymentInvPMS(models.TransientModel):
    _inherit = 'sale.advance.payment.inv'

    def _get_down_payment_description(self, order):
        self.ensure_one()
        context = {'lang': order.partner_id.lang}
        if self.advance_payment_method == 'percentage':
            percent = formatLang(self.env(context=context), self.amount)
            # Get product names from order lines
            products = order.order_line.filtered(
                lambda l: not l.display_type and not l.is_downpayment
            ).mapped('name')
            product_summary = ', '.join(products[:2])  # max 2 products to keep it short
            if len(products) > 2:
                product_summary += '...'
            name = _(
                "Down Payment (%s%%) – %s",
                percent,
                product_summary or order.name
            )
        else:
            name = _("Down Payment – %s", order.name)
        del context
        return name
