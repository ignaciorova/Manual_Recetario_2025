from odoo import models, fields

class RecipeIngredient(models.Model):
    _name = 'industrial.recipe.ingredient'
    _description = 'Recipe Ingredient'

    recipe_id = fields.Many2one('industrial.recipe', string='Recipe', index=True)
    ingredient_id = fields.Many2one('industrial.ingredient', string='Ingredient', index=True)
    quantity = fields.Float(string='Quantity')
    unit_of_measure = fields.Many2one('uom.uom', string='Unit of Measure')
    company_id = fields.Many2one('res.company', string='Company', related='recipe_id.company_id', store=True)