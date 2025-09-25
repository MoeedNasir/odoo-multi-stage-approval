from odoo import models, fields, api
from odoo.exceptions import ValidationError

class ApprovalStage(models.Model):
    _name= 'approval.stage'
    _description = 'Approval Stage'
    _order = 'sequence, id'

    name = fields.Char(string="String Name", required= True)
    sequence = fields.Integer(string="Sequence", required= True, default = 10)
    approval_flow_id = fields.Many2one('approval.flow', string='Approval Flow', required=True)
    role_id = fields.Many2one('res.groups', string='Approver Group', required=True)
    minimum_amount = fields.Float(string='Minimum Amount', default=0.0)
    maximum_amount = fields.Float(string='Maximum Amount', default=0.0)
    is_final_approval = fields.Boolean(string='Final Approval Stage')
    auto_approve = fields.Boolean(string='Auto Approve')
    approval_type = fields.Selection([
        ('mandatory', 'Mandatory Approval'),
        ('optional', 'Optional Approval'),
        ('parallel', 'Parallel Approval')
    ], default='mandatory')

    # Constraints
    @api.constrains('minimum_amount', 'maximum_amount')
    def _check_amount_range(self):
        for stage in self:
            if stage.maximum_amount > 0 and stage.minimum_amount > stage.maximum_amount:
                raise ValidationError("Minimum amount cannot be greater than maximum amount.")