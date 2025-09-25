from odoo import _,models, fields, api
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    approval_flow_id = fields.Many2one('approval.flow', string='Approval Flow')
    approval_stage_id = fields.Many2one('approval.stage', string='Current Stage')
    approval_status = fields.Selection([
        ('draft', 'Draft'),
        ('waiting', 'Waiting Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Approval Status', default='draft', tracking=True)
    approval_history_ids = fields.One2many('approval.history', 'purchase_order_id', string='Approval History')
    requires_approval = fields.Boolean(compute='_compute_requires_approval')
    next_approver_id = fields.Many2one('res.users', compute='_compute_next_approver')

    @api.model
    def _get_approval_domain(self):
        """Domain for records user can approve"""
        if self.env.user.has_group('base.group_system'):
            return []
        return [('approval_stage_id.role_id', 'in', self.env.user.groups_id.ids)]

    @api.depends('amount_total', 'company_id')
    def _compute_requires_approval(self):
        for order in self:
            flow = self.env['approval.flow'].search([
                ('model', '=', 'purchase.order'),
                ('company_id', '=', order.company_id.id)
            ], limit=1)
            order.requires_approval = bool(flow and flow.stage_ids)

    @api.depends('approval_stage_id', 'approval_status')
    def _compute_next_approver(self):
        for order in self:
            if order.approval_status == 'waiting' and order.approval_stage_id:
                # Logic to determine next approver
                order.next_approver_id = False
            else:
                order.next_approver_id = False

    def action_request_approval(self):
        """Initiate approval process"""
        for order in self:
            if order.approval_status != 'draft':
                raise UserError(_("Approval can only be requested from draft status."))

            flow = order.approval_flow_id or self.env['approval.flow'].search([
                ('model', '=', 'purchase.order'),
                ('company_id', '=', order.company_id.id)
            ], limit=1)

            if not flow:
                raise UserError(_("No approval flow configured for purchase orders."))

            first_stage = flow.stage_ids.sorted('sequence')[:1]
            if not first_stage:
                raise UserError(_("No approval stages configured in the flow."))

            order.write({
                'approval_flow_id': flow.id,
                'approval_stage_id': first_stage.id,
                'approval_status': 'waiting'
            })

            # Create approval history record
            self.env['approval.history'].create({
                'purchase_order_id': order.id,
                'stage_id': first_stage.id,
                'action': 'requested',
                'user_id': self.env.user.id
            })

            order.message_post(body=_("Approval requested by %s") % self.env.user.name)