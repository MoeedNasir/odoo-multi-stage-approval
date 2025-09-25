from odoo import models,fields, api
from odoo.tools import unique

class ApprovalFlow(models.Model):
    _name = 'approval.flow'
    _description = 'Approval Flow'
    _order = 'sequence, id'

    name = fields.Char(string="Flow name", required = True)
    sequence = fields.Integer(string="Sequence", default= 10)
    model = fields.Selection([
        ('purchase.order', 'Purchase Order'),
        ('sale.order', 'Sales Order')
    ], string="Apllied Model", required = True)
    active = fields.Boolean(default = True)
    stage_ids= fields.One2many('approval.stage', 'approval_flow_id', string= "Stages")
    company_id = fields.Many2one('res.company', default =lambda self: self.env.company)

    _sql_constraints = [
        ('unique_flow_model', 'unique(model, company_id)','Only one flow per model per company is allowed!')
    ]
