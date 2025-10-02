from odoo import _, models, fields, api
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    approval_flow_id = fields.Many2one('approval.flow', string='Approval Flow', tracking=True)
    approval_stage_id = fields.Many2one('approval.stage', string='Current Stage', tracking=True)
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
                # Get users from the approver group of current stage
                approver_group = order.approval_stage_id.role_id
                approvers = self.env['res.users'].search([('groups_id', 'in', approver_group.ids)])
                order.next_approver_id = approvers[0] if approvers else False
            else:
                order.next_approver_id = False

    def action_request_approval(self):
        """Initiate approval process with enhanced messaging and notifications"""
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

            # Enhanced chatter messaging
            order.message_post(
                body=_("Approval requested by %s. Current Stage: %s") % (self.env.user.name, first_stage.name),
                subtype_xmlid='mail.mt_comment'
            )

            # Send email notifications
            order._send_approval_notifications(first_stage)

            # Create activity for approvers
            self._create_approval_activity(order, first_stage)

    def action_approve(self):
        """Approve current stage and move to next with enhanced notifications"""
        for order in self:
            if order.approval_status != 'waiting':
                raise UserError(_("Only orders waiting approval can be approved."))

            if not self._check_approval_rights(order):
                raise UserError(_("You don't have permission to approve this stage."))

            # Create approval history
            self.env['approval.history'].create({
                'purchase_order_id': order.id,
                'stage_id': order.approval_stage_id.id,
                'action': 'approved',
                'user_id': self.env.user.id,
                'note': 'Approved via button'
            })

            # Move to next stage or complete approval
            next_stage = self._get_next_stage(order)
            if next_stage:
                order.approval_stage_id = next_stage
                order.message_post(
                    body=_("Approved by %s. Moved to next stage: %s") % (self.env.user.name, next_stage.name),
                    subtype_xmlid='mail.mt_comment'
                )

                # Send notifications for next stage
                order._send_approval_notifications(next_stage)

                # Create activity for next stage approvers
                self._create_approval_activity(order, next_stage)
            else:
                order.approval_status = 'approved'
                order.message_post(
                    body=_("Fully approved by %s") % self.env.user.name,
                    subtype_xmlid='mail.mt_comment'
                )

                # Send approval completion notification
                order._send_approval_complete_notification()

                # Auto confirm purchase order if configured
                if self._should_auto_confirm():
                    order.button_confirm()

    def _send_approval_notifications(self, stage):
        """Send email and/or chat notifications for approval requests"""
        notification_method = self._get_notification_method()

        if 'email' in notification_method:
            self._send_email_notification(stage)

        if 'chat' in notification_method:
            self._send_chat_notification(stage)

    def _send_email_notification(self, stage):
        """Send email notification to approvers"""
        try:
            # Get appropriate email template based on model
            if self._name == 'purchase.order':
                template = self.env.ref('multi_stage_approval.email_template_approval_request')
            else:
                template = self.env.ref('multi_stage_approval.email_template_sales_approval_request')

            # Send email to all approvers in the stage group
            approver_group = stage.role_id
            approvers = self.env['res.users'].search([
                ('groups_id', 'in', approver_group.ids),
                ('id', '!=', self.env.user.id)  # Exclude current user
            ])

            for approver in approvers:
                if approver.email:
                    template.with_context(
                        lang=approver.lang,
                        email_to=approver.email
                    ).send_mail(self.id, force_send=True)

        except Exception as e:
            # Log error but don't break the approval process
            self.message_post(
                body=_("Failed to send email notification: %s") % str(e),
                subtype_xmlid='mail.mt_comment'
            )

    def _send_chat_notification(self, stage):
        """Send chat notification to approvers"""
        try:
            approver_group = stage.role_id
            approvers = self.env['res.users'].search([
                ('groups_id', 'in', approver_group.ids),
                ('id', '!=', self.env.user.id)
            ])

            for approver in approvers:
                # Create a direct notification
                self.env['mail.message'].create({
                    'model': self._name,
                    'res_id': self.id,
                    'body': _('Approval required for %s. Current stage: %s') % (self.name, stage.name),
                    'partner_ids': [(6, 0, [approver.partner_id.id])],
                    'subject': _('Approval Required'),
                    'message_type': 'notification',
                })

        except Exception as e:
            # Log error but don't break the approval process
            self.message_post(
                body=_("Failed to send chat notification: %s") % str(e),
                subtype_xmlid='mail.mt_comment'
            )

    def _send_approval_complete_notification(self):
        """Send notification when approval is complete"""
        try:
            # Notify the requester
            template = self.env.ref('multi_stage_approval.email_template_approval_approved')
            if template and self.create_uid.email:
                template.with_context(
                    lang=self.create_uid.lang,
                    email_to=self.create_uid.email
                ).send_mail(self.id, force_send=True)

        except Exception as e:
            self.message_post(
                body=_("Failed to send approval completion notification: %s") % str(e),
                subtype_xmlid='mail.mt_comment'
            )

    def _get_notification_method(self):
        """Get notification method from configuration"""
        method = self.env['ir.config_parameter'].sudo().get_param(
            'multi_stage_approval.notification_method', 'both'
        )

        if method == 'email':
            return ['email']
        elif method == 'chat':
            return ['chat']
        else:  # both or default
            return ['email', 'chat']

    def action_reject(self):
        """Reject the purchase order with enhanced messaging"""
        for order in self:
            if order.approval_status != 'waiting':
                raise UserError(_("Only orders waiting approval can be rejected."))

            # Create rejection history
            self.env['approval.history'].create({
                'purchase_order_id': order.id,
                'stage_id': order.approval_stage_id.id,
                'action': 'rejected',
                'user_id': self.env.user.id,
                'note': 'Rejected via button'
            })

            order.approval_status = 'rejected'
            order.message_post(
                body=_("Rejected by %s") % self.env.user.name,
                subtype_xmlid='mail.mt_comment'
            )

    def _create_approval_activity(self, order, stage):
        """Create approval activity for approvers"""
        approver_group = stage.role_id
        approvers = self.env['res.users'].search([
            ('groups_id', 'in', approver_group.ids),
            ('id', '!=', self.env.user.id)  # Exclude current user
        ])

        for approver in approvers:
            order.activity_schedule(
                'multi_stage_approval.mail_activity_approval',
                user_id=approver.id,
                note=_('Approval required for %s. Current stage: %s. Amount: %s %s') % (
                    order.name,
                    stage.name,
                    order.amount_total,
                    order.currency_id.name
                ),
                summary=_('Approval Required - %s') % stage.name
            )

    def _check_approval_rights(self, order):
        """Check if current user can approve this stage"""
        return order.approval_stage_id.role_id in self.env.user.groups_id

    def _get_next_stage(self, order):
        """Get next stage in sequence"""
        stages = order.approval_flow_id.stage_ids.sorted('sequence')
        current_index = stages.ids.index(order.approval_stage_id.id)
        return stages[current_index + 1] if current_index + 1 < len(stages) else False

    def _should_auto_confirm(self):
        """Check if purchase order should be auto-confirmed after approval"""
        return self.env['ir.config_parameter'].sudo().get_param(
            'multi_stage_approval.auto_confirm', False
        )

    # Override purchase order confirmation to require approval
    def button_confirm(self):
        """Override confirm button to check approval"""
        for order in self:
            if order.requires_approval and order.approval_status != 'approved':
                raise UserError(_(
                    "This purchase order requires approval before confirmation. "
                    "Please request approval first."
                ))
        return super(PurchaseOrder, self).button_confirm()

    def get_approval_url(self):
        """Generate approval URL for email templates"""
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        return f"{base_url}/web#id={self.id}&model={self._name}&view_type=form"

    def _send_escalation_notification(self):
        """Send escalation notification for purchase orders"""
        try:
            template = self.env.ref('multi_stage_approval.email_template_approval_escalation')
            if template:
                template.send_mail(self.id, force_send=True)

            # Post chatter message
            self.message_post(
                body=_("🚨 Escalation notification sent - approval pending beyond threshold"),
                subtype_xmlid='mail.mt_comment'
            )

        except Exception as e:
            _logger.error("Failed to send escalation email for purchase order %s: %s", self.id, str(e))


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    approval_flow_id = fields.Many2one('approval.flow', string='Approval Flow', tracking=True)
    approval_stage_id = fields.Many2one('approval.stage', string='Current Stage', tracking=True)
    approval_status = fields.Selection([
        ('draft', 'Draft'),
        ('waiting', 'Waiting Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Approval Status', default='draft', tracking=True)
    approval_history_ids = fields.One2many('approval.history', 'sale_order_id', string='Approval History')
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
                ('model', '=', 'sale.order'),
                ('company_id', '=', order.company_id.id)
            ], limit=1)
            order.requires_approval = bool(flow and flow.stage_ids)

    @api.depends('approval_stage_id', 'approval_status')
    def _compute_next_approver(self):
        for order in self:
            if order.approval_status == 'waiting' and order.approval_stage_id:
                # Get users from the approver group of current stage
                approver_group = order.approval_stage_id.role_id
                approvers = self.env['res.users'].search([('groups_id', 'in', approver_group.ids)])
                order.next_approver_id = approvers[0] if approvers else False
            else:
                order.next_approver_id = False

    def action_request_approval(self):
        """Sales order specific approval request with notifications"""
        for order in self:
            if order.state != 'draft':
                raise UserError(_("Approval can only be requested from draft quotation."))

            if order.approval_status != 'draft':
                raise UserError(_("Approval can only be requested from draft status."))

            flow = order.approval_flow_id or self.env['approval.flow'].search([
                ('model', '=', 'sale.order'),
                ('company_id', '=', order.company_id.id)
            ], limit=1)

            if not flow:
                raise UserError(_("No approval flow configured for sales orders."))

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
                'sale_order_id': order.id,
                'stage_id': first_stage.id,
                'action': 'requested',
                'user_id': self.env.user.id
            })

            # Enhanced chatter messaging
            order.message_post(
                body=_("Approval requested by %s. Current Stage: %s") % (self.env.user.name, first_stage.name),
                subtype_xmlid='mail.mt_comment'
            )

            # Send email notifications
            order._send_approval_notifications(first_stage)

            # Create activity for approvers
            self._create_approval_activity(order, first_stage)

    def _send_approval_notifications(self, stage):
        """Send email and/or chat notifications for approval requests"""
        notification_method = self._get_notification_method()

        if 'email' in notification_method:
            self._send_email_notification(stage)

        if 'chat' in notification_method:
            self._send_chat_notification(stage)

    def _send_email_notification(self, stage):
        """Send email notification to approvers"""
        try:
            template = self.env.ref('multi_stage_approval.email_template_sales_approval_request')

            # Send email to all approvers in the stage group
            approver_group = stage.role_id
            approvers = self.env['res.users'].search([
                ('groups_id', 'in', approver_group.ids),
                ('id', '!=', self.env.user.id)
            ])

            for approver in approvers:
                if approver.email:
                    template.with_context(
                        lang=approver.lang,
                        email_to=approver.email
                    ).send_mail(self.id, force_send=True)

        except Exception as e:
            self.message_post(
                body=_("Failed to send email notification: %s") % str(e),
                subtype_xmlid='mail.mt_comment'
            )

    def _send_chat_notification(self, stage):
        """Send chat notification to approvers"""
        try:
            approver_group = stage.role_id
            approvers = self.env['res.users'].search([
                ('groups_id', 'in', approver_group.ids),
                ('id', '!=', self.env.user.id)
            ])

            for approver in approvers:
                self.env['mail.message'].create({
                    'model': self._name,
                    'res_id': self.id,
                    'body': _('Approval required for %s. Current stage: %s') % (self.name, stage.name),
                    'partner_ids': [(6, 0, [approver.partner_id.id])],
                    'subject': _('Approval Required'),
                    'message_type': 'notification',
                })

        except Exception as e:
            self.message_post(
                body=_("Failed to send chat notification: %s") % str(e),
                subtype_xmlid='mail.mt_comment'
            )

    def _get_notification_method(self):
        """Get notification method from configuration"""
        method = self.env['ir.config_parameter'].sudo().get_param(
            'multi_stage_approval.notification_method', 'both'
        )

        if method == 'email':
            return ['email']
        elif method == 'chat':
            return ['chat']
        else:
            return ['email', 'chat']

    def action_approve(self):
        """Approve current stage and move to next"""
        for order in self:
            if order.approval_status != 'waiting':
                raise UserError(_("Only orders waiting approval can be approved."))

            if not self._check_approval_rights(order):
                raise UserError(_("You don't have permission to approve this stage."))

            # Create approval history
            self.env['approval.history'].create({
                'sale_order_id': order.id,
                'stage_id': order.approval_stage_id.id,
                'action': 'approved',
                'user_id': self.env.user.id,
                'note': 'Approved via button'
            })

            # Move to next stage or complete approval
            next_stage = self._get_next_stage(order)
            if next_stage:
                order.approval_stage_id = next_stage
                order.message_post(body=_("Approved by %s. Moved to next stage: %s") %
                                        (self.env.user.name, next_stage.name))
            else:
                order.approval_status = 'approved'
                order.message_post(body=_("✅ Fully approved by %s") % self.env.user.name)

                # Auto confirm sales order if configured
                if self._should_auto_confirm():
                    order.action_confirm()

    def action_reject(self):
        """Reject the sales order"""
        for order in self:
            if order.approval_status != 'waiting':
                raise UserError(_("Only orders waiting approval can be rejected."))

            # Create rejection history
            self.env['approval.history'].create({
                'sale_order_id': order.id,
                'stage_id': order.approval_stage_id.id,
                'action': 'rejected',
                'user_id': self.env.user.id,
                'note': 'Rejected via button'
            })

            order.approval_status = 'rejected'
            order.message_post(body=_("❌ Rejected by %s") % self.env.user.name)

    def _create_approval_activity(self, order, stage):
        """Create approval activity for sales approvers"""
        approver_group = stage.role_id
        approvers = self.env['res.users'].search([
            ('groups_id', 'in', approver_group.ids),
            ('id', '!=', self.env.user.id)  # Exclude current user
        ])

        for approver in approvers:
            order.activity_schedule(
                'multi_stage_approval.mail_activity_approval',
                user_id=approver.id,
                note=_('Approval required for %s. Current stage: %s. Amount: %s %s') % (
                    order.name,
                    stage.name,
                    order.amount_total,
                    order.currency_id.name
                ),
                summary=_('Approval Required - %s') % stage.name
            )

    def _check_approval_rights(self, order):
        """Check if current user can approve this stage"""
        return order.approval_stage_id.role_id in self.env.user.groups_id

    def _get_next_stage(self, order):
        """Get next stage in sequence"""
        stages = order.approval_flow_id.stage_ids.sorted('sequence')
        current_index = stages.ids.index(order.approval_stage_id.id)
        return stages[current_index + 1] if current_index + 1 < len(stages) else False

    def _should_auto_confirm(self):
        """Check if sales order should be auto-confirmed after approval"""
        return self.env['ir.config_parameter'].sudo().get_param(
            'multi_stage_approval.auto_confirm', False
        )

    # Override sales order confirmation to require approval
    def action_confirm(self):
        """Override confirm action to check approval"""
        for order in self:
            if order.requires_approval and order.approval_status != 'approved':
                raise UserError(_(
                    "This sales order requires approval before confirmation. "
                    "Please request approval first."
                ))
        return super(SaleOrder, self).action_confirm()

    def get_approval_url(self):
        """Generate approval URL for email templates"""
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        return f"{base_url}/web#id={self.id}&model={self._name}&view_type=form"

    def _send_escalation_notification(self):
        """Send escalation notification for sales orders"""
        try:
            template = self.env.ref('multi_stage_approval.email_template_approval_escalation')
            if template:
                template.send_mail(self.id, force_send=True)

            # Post chatter message
            self.message_post(
                body=_("🚨 Escalation notification sent - approval pending beyond threshold"),
                subtype_xmlid='mail.mt_comment'
            )

        except Exception as e:
            _logger.error("Failed to send escalation email for sales order %s: %s", self.id, str(e))