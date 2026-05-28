from odoo import api, fields, models, _
import logging

_logger = logging.getLogger(__name__)

COMPANIES_WITH_DISABLED_AUTO_MATCHING = [
    'diamond',
    'charlotte',
]


class AccountReconcileModel(models.Model):
    _inherit = "account.reconcile.model"

    def _is_applicable_for(self, st_line, partner):
        """Disable automatic invoice matching for Diamond and Charlotte companies."""
        res = super()._is_applicable_for(st_line, partner)
        if not res:
            return False

        if self.rule_type == 'invoice_matching' and st_line.move_id.company_id:
            company_name = (st_line.move_id.company_id.name or '').lower()
            for blocked in COMPANIES_WITH_DISABLED_AUTO_MATCHING:
                if blocked in company_name:
                    _logger.info(
                        "Auto-matching disabled for company '%s' (rule: %s)",
                        st_line.move_id.company_id.name, self.name
                    )
                    return False
        return res
