from odoo import models, fields


class ApprovalHistory(models.Model):
    _name = 'approval.history'
    _description = 'Approval History'
    _order = 'create_date desc'

    purchase_order_id = fields.Many2one('purchase.order', string='Purchase Order', ondelete='cascade')
    stage_id = fields.Many2one('approval.stage', string='Approval Stage')
    action = fields.Selection([
        ('requested', 'Requested'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Action')
    user_id = fields.Many2one('res.users', string='User')
    note = fields.Text(string='Notes')
    date = fields.Datetime(string='Date', default=fields.Datetime.now)
