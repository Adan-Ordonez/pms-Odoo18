from odoo import api, fields, models

import logging
_logger = logging.getLogger(__name__)

class StockMove(models.Model):
    _inherit = 'stock.move'
    
    material_order_id = fields.Many2one('pms.materials', string='Material Order', index=True, ondelete='cascade')
    property_id = fields.Many2one('pms.property', string='Project/Property', index=True, help="Property where these materials were used")
    property_name = fields.Char(related='property_id.name', string='Property Address', store=True, readonly=True)
    
class StockPicking(models.Model):
    _inherit = 'stock.picking'
    
    material_order_ids = fields.One2many('pms.materials', 'picking_id', string='Material Orders')



