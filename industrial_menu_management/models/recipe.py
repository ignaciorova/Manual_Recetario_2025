from odoo import models, fields

class Recipe(models.Model):
    _name = 'industrial.recipe'
    _description = 'Recipe'

    name = fields.Char(string='Recipe Name', required=True)
    preparation_instructions = fields.Text(string='Preparation Instructions')
    cooking_technique = fields.Selection([
        ('boil', 'Boil'), ('bake', 'Bake'), ('fry', 'Fry'), ('steam', 'Steam'),
    ], string='Cooking Technique')
    ingredient_lines = fields.One2many('industrial.recipe.ingredient', 'recipe_id', string='Ingredients')
    portion_ids = fields.One2many('industrial.portion', 'recipe_id', string='Portions')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company, required=True)

    def consume_ingredients(self):
        for ingredient in self.ingredient_lines:
            move = self.env['stock.move'].create({
                'product_id': ingredient.ingredient_id.product_id.id,
                'product_uom_qty': ingredient.quantity,
                'product_uom': ingredient.unit_of_measure.id,
                'location_id': self.env.ref('stock.stock_location_stock').id,
                'location_dest_id': self.env.ref('stock.stock_location_customers').id,
                'company_id': self.company_id.id,
            })
            move._action_confirm()
            move._action_done()