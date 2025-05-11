from odoo import models, fields

class MenuItem(models.Model):
    _name = 'industrial.menu.item'
    _description = 'Menu Item'

    name = fields.Char(string='Menu Item Name', required=True)
    cycle_id = fields.Many2one('industrial.menu.cycle', string='Menu Cycle')
    day_of_week = fields.Selection([
        ('monday', 'Monday'), ('tuesday', 'Tuesday'), ('wednesday', 'Wednesday'),
        ('thursday', 'Thursday'), ('friday', 'Friday'),
    ], string='Day of Week')
    recipe_ids = fields.Many2many('industrial.recipe', string='Recipes')
    nutritional_info_id = fields.Many2one('industrial.nutritional.info', string='Nutritional Info')
    company_id = fields.Many2one('res.company', string='Company', related='cycle_id.company_id', store=True)