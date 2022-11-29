# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class pos_order(models.Model):
    _inherit = "pos.order"

    disabled=fields.Boolean(string='Disabled')


class pos_order_report(models.Model):
    _inherit = "report.pos.order"

    disabled=fields.Boolean(related = 'order_id.disabled')

