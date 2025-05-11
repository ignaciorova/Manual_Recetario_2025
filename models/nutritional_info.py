from odoo import models, fields

class NutritionalInfo(models.Model):
    _name = 'industrial.nutritional.info'
    _description = 'Nutritional Information'

    name = fields.Char(string='Name', required=True)
    energy_kcal = fields.Float(string='Energy (kcal)')
    protein_g = fields.Float(string='Protein (g)')
    fat_g = fields.Float(string='Fat (g)')
    carbs_g = fields.Float(string='Carbohydrates (g)')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company, required=True)