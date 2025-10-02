from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class ApprovalNotificationSystem(models.Model):
    _name = 'approval.notification.system'
    _description = 'Approval Notification System'

    @api.model
    def check_escalations(self):
        """Check for pending approvals that need escalation"""
        escalation_days = int(self.env['ir.config_parameter'].sudo().get_param(
            'multi_stage_approval.escalation_days', 2
        ))

        # Find orders waiting approval for more than escalation days
        domain = [
            ('approval_status', '=', 'waiting'),
            ('write_date', '<=', fields.Datetime.subtract(fields.Datetime.now(), days=escalation_days))
        ]

        purchase_orders = self.env['purchase.order'].search(domain)
        sales_orders = self.env['sale.order'].search(domain)

        all_orders = purchase_orders + sales_orders

        for order in all_orders:
            try:
                order._send_escalation_notification()
                _logger.info("Sent escalation notification for %s %s", order._name, order.id)
            except Exception as e:
                _logger.error("Failed to send escalation notification for %s %s: %s",
                              order._name, order.id, str(e))

    def _send_escalation_notification(self):
        """Send escalation notification - base method"""
        try:
            template = self.env.ref('multi_stage_approval.email_template_approval_escalation')
            if template:
                template.send_mail(self.id, force_send=True)

            # Also post a chatter message
            self.message_post(
                body=_("🚨 Escalation notification sent - approval pending for %s days") %
                     self.env['ir.config_parameter'].sudo().get_param('multi_stage_approval.escalation_days', 2),
                subtype_xmlid='mail.mt_comment'
            )

        except Exception as e:
            _logger.error("Failed to send escalation email for %s %s: %s",
                          self._name, self.id, str(e))
