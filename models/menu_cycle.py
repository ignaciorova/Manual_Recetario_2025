from odoo import models, fields, api
from datetime import timedelta

class MenuCycle(models.Model):
    _name = 'industrial.menu.cycle'
    _description = 'Menu Cycle'

    name = fields.Char(string='Cycle Name', required=True)
    meal_type = fields.Selection([
        ('breakfast', 'Breakfast'),
        ('lunch', 'Lunch'),
        ('snack', 'Snack'),
    ], string='Meal Type', required=True)
    duration_weeks = fields.Integer(string='Duration (Weeks)', required=True)
    menu_items = fields.One2many('industrial.menu.item', 'cycle_id', string='Menu Items')
    start_date = fields.Date(string='Start Date')
    end_date = fields.Date(string='End Date', compute='_compute_end_date')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company, required=True)

    @api.depends('start_date', 'duration_weeks')
    def _compute_end_date(self):
        for record in self:
            if record.start_date and record.duration_weeks:
                record.end_date = record.start_date + timedelta(weeks=record.duration_weeks)
            else:
                record.end_date = False

    @api.constrains('company_id', 'menu_items')
    def _check_company_id(self):
        for record in self:
            if record.menu_items:
                invalid_items = record.menu_items.filtered(lambda item: item.company_id != record.company_id)
                if invalid_items:
                    raise ValidationError("All menu items must belong to the same company as the menu cycle.")