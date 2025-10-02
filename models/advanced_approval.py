from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError


class AdvancedApproval(models.Model):
    _name = 'advanced.approval'
    _description = 'Advanced Approval Features'

    @api.model
    def _get_appropriate_flow(self, record):
        """Get flow based on order amount and conditions"""
        domain = [
            ('model', '=', record._name),
            ('company_id', '=', record.company_id.id),
            ('active', '=', True)
        ]
        flows = self.env['approval.flow'].search(domain)

        for flow in flows:
            # Check if this flow applies based on amount ranges and conditions
            applicable_stages = flow.stage_ids.filtered(
                lambda s: s.minimum_amount <= record.amount_total <= (s.maximum_amount or float('inf'))
            )
            if applicable_stages:
                return flow
        return flows[:1] if flows else False

    def _handle_parallel_approval(self, record, stage):
        """Handle parallel approval stages with multiple approvers"""
        approver_group = stage.role_id
        approvers = self.env['res.users'].search([('groups_id', 'in', approver_group.ids)])

        if stage.approval_type == 'parallel':
            # Create approval tasks for all approvers
            for approver in approvers:
                record.activity_schedule(
                    'multi_stage_approval.mail_activity_approval',
                    user_id=approver.id,
                    note=f'Parallel approval required for {record.name} at stage {stage.name}'
                )
            return True
        return False

    def _check_parallel_approval_complete(self, record, stage):
        """Check if parallel approval is complete"""
        if stage.approval_type == 'parallel':
            # Check if all required approvers have approved
            required_approvers = self.env['res.users'].search([
                ('groups_id', 'in', stage.role_id.ids)
            ])

            approved_history = self.env['approval.history'].search([
                ('stage_id', '=', stage.id),
                ('action', '=', 'approved'),
                '|',
                ('purchase_order_id', '=', record.id),
                ('sale_order_id', '=', record.id)
            ])

            approver_ids = approved_history.mapped('user_id.id')
            return all(approver.id in approver_ids for approver in required_approvers)
        return True


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    approval_auto_confirm = fields.Boolean(
        string="Auto Confirm After Approval",
        config_parameter='multi_stage_approval.auto_confirm',
        help="Automatically confirm Purchase/Sales orders after final approval"
    )

    approval_notification_method = fields.Selection([
        ('email', 'Email Only'),
        ('chat', 'Chat Only'),
        ('both', 'Both Email and Chat')
    ], string="Notification Method",
        default='both',
        config_parameter='multi_stage_approval.notification_method')

    approval_escallation_days = fields.Integer(
        string="Escalation Days",
        default=2,
        config_parameter='multi_stage_approval.escallation_days',
        help="Number of days before escalating pending approvals"
    )

    approval_allow_override = fields.Boolean(
        string="Allow Manager Override",
        config_parameter='multi_stage_approval.allow_override',
        help="Allow managers to override approval requirements"
    )

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        # Additional configuration logic if needed
        return True

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        # Get current configuration values
        return res