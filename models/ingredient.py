from odoo import models, fields

class Ingredient(models.Model):
    _name = 'industrial.ingredient'
    _description = 'Ingredient'

    name = fields.Char(string='Ingredient Name', required=True)
    product_id = fields.Many2one('product.product', string='Inventory Product', domain="[('company_id', '=', company_id)]")
    unit_of_measure = fields.Many2one('uom.uom', string='Unit of Measure')
    seasonality = fields.Selection([
        ('jan', 'January'), ('feb', 'February'), ('mar', 'March'), ('apr', 'April'),
        ('may', 'May'), ('jun', 'June'), ('jul', 'July'), ('aug', 'August'),
        ('sep', 'September'), ('oct', 'October'), ('nov', 'November'), ('dec', 'December'),
        ('all_year', 'All Year'),
    ], string='Seasonality')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company, required=True)