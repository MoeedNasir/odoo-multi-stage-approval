from odoo import models, fields, api


class ApprovalHistory(models.Model):
    _name = 'approval.history'
    _description = 'Approval History'
    _order = 'date desc'

    purchase_order_id = fields.Many2one('purchase.order', string='Purchase Order', ondelete='cascade')
    sale_order_id = fields.Many2one('sale.order', string='Sale Order', ondelete='cascade')
    stage_id = fields.Many2one('approval.stage', string='Approval Stage', required=True)
    action = fields.Selection([
        ('requested', 'Requested'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Action', required=True)
    user_id = fields.Many2one('res.users', string='User', required=True)
    note = fields.Text(string='Notes')
    date = fields.Datetime(string='Date', default=fields.Datetime.now)

    def name_get(self):
        result = []
        for record in self:
            name = f"{record.stage_id.name} - {record.action} by {record.user_id.name}"
            result.append((record.id, name))
        return result

    @api.model
    def create(self, vals):
        """Override create to ensure proper record linking"""
        record = super(ApprovalHistory, self).create(vals)

        # Post message to linked document
        if record.purchase_order_id:
            record.purchase_order_id.message_post(
                body=f"Approval {record.action}: {record.stage_id.name}"
            )
        elif record.sale_order_id:
            record.sale_order_id.message_post(
                body=f"Approval {record.action}: {record.stage_id.name}"
            )

        return record