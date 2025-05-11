from odoo import models, fields

class HandleUnforeseenChanges(models.TransientModel):
    _name = 'industrial.unforeseen.changes.wizard'
    _description = 'Handle Unforeseen Changes'

    menu_item_id = fields.Many2one('industrial.menu.item', string='Menu Item', domain="[('company_id', '=', company_id)]")
    issue_type = fields.Selection([
        ('stock_shortage', 'Stock Shortage'),
        ('refrigeration_issue', 'Refrigeration Issue'),
    ], string='Issue Type')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company, required=True)

    def action_suggest_alternative(self):
        # Logic to suggest alternative recipes or ingredients
        return {'type': 'ir.actions.act_window_close'}