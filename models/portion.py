from odoo import models, fields

class Portion(models.Model):
    _name = 'industrial.portion'
    _description = 'Portion'

    recipe_id = fields.Many2one('industrial.recipe', string='Recipe')
    portion_size = fields.Integer(string='Number of Portions', required=True)
    ingredient_quantities = fields.Text(string='Ingredient Quantities')
    company_id = fields.Many2one('res.company', string='Company', related='recipe_id.company_id', store=True)