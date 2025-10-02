from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError
from unittest.mock import patch


class TestNotificationSystem(TransactionCase):
    """Test cases for notification system"""

    def setUp(self):
        super(TestNotificationSystem, self).setUp()
        self.PurchaseOrder = self.env['purchase.order']
        self.SaleOrder = self.env['sale.order']
        self.ApprovalFlow = self.env['approval.flow']
        self.ApprovalStage = self.env['approval.stage']
        self.ResPartner = self.env['res.partner']
        self.ResGroups = self.env['res.groups']
        self.Product = self.env['product.product']
        self.MailTemplate = self.env['mail.template']

        # Create test data
        self.approver_group = self.ResGroups.create({'name': 'Test Approvers'})
        self.vendor = self.ResPartner.create({'name': 'Test Vendor', 'supplier_rank': 1})
        self.customer = self.ResPartner.create({'name': 'Test Customer'})
        self.product = self.Product.create({'name': 'Test Product', 'type': 'consu'})

    def test_email_notification_sent(self):
        """Test that email notifications are sent on approval request"""
        flow = self.ApprovalFlow.create({
            'name': 'Test Flow',
            'model': 'purchase.order'
        })

        stage = self.ApprovalStage.create({
            'name': 'Test Stage',
            'sequence': 10,
            'approval_flow_id': flow.id,
            'role_id': self.approver_group.id,
        })

        # Create approver user with email
        approver_user = self.env['res.users'].create({
            'name': 'Test Approver',
            'login': 'test_approver@example.com',
            'email': 'test_approver@example.com',
            'groups_id': [(4, self.approver_group.id)]
        })

        po = self.PurchaseOrder.create({
            'partner_id': self.vendor.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_qty': 5,
                'price_unit': 100,
            })]
        })

        # Mock the email sending to test notification logic
        with patch(
                'odoo.addons.multi_stage_approval.models.purchase_sale_inherit.PurchaseOrder._send_email_notification') as mock_email:
            po.action_request_approval()

            # Check that email notification was attempted
            mock_email.assert_called_once()
            self.assertTrue(mock_email.called)

    def test_notification_method_configuration(self):
        """Test notification method configuration"""
        # Test different notification methods
        config_params = self.env['ir.config_parameter'].sudo()

        # Test email only
        config_params.set_param('multi_stage_approval.notification_method', 'email')
        po = self.PurchaseOrder.create({
            'partner_id': self.vendor.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_qty': 1,
                'price_unit': 50,
            })]
        })

        method = po._get_notification_method()
        self.assertEqual(method, ['email'])

        # Test chat only
        config_params.set_param('multi_stage_approval.notification_method', 'chat')
        method = po._get_notification_method()
        self.assertEqual(method, ['chat'])

        # Test both
        config_params.set_param('multi_stage_approval.notification_method', 'both')
        method = po._get_notification_method()
        self.assertEqual(set(method), {'email', 'chat'})

    def test_escalation_system(self):
        """Test escalation notification system"""
        notification_system = self.env['approval.notification.system']

        # Test escalation check doesn't crash
        try:
            notification_system.check_escalations()
            # If we get here, the method executed without errors
            success = True
        except Exception as e:
            success = False
            _logger.error("Escalation check failed: %s", str(e))

        self.assertTrue(success, "Escalation check should complete without errors")

    def test_template_availability(self):
        """Test that all required email templates exist"""
        templates = [
            'multi_stage_approval.email_template_approval_request',
            'multi_stage_approval.email_template_sales_approval_request',
            'multi_stage_approval.email_template_approval_approved',
            'multi_stage_approval.email_template_approval_rejected',
            'multi_stage_approval.email_template_sales_approval_approved',
            'multi_stage_approval.email_template_approval_escalation',
        ]

        for template_xmlid in templates:
            template = self.env.ref(template_xmlid, raise_if_not_found=False)
            self.assertIsNotNone(template, f"Template {template_xmlid} should exist")

    def test_sales_order_notifications(self):
        """Test notification system for sales orders"""
        flow = self.ApprovalFlow.create({
            'name': 'Test Sales Flow',
            'model': 'sale.order'
        })

        stage = self.ApprovalStage.create({
            'name': 'Test Stage',
            'sequence': 10,
            'approval_flow_id': flow.id,
            'role_id': self.approver_group.id,
        })

        so = self.SaleOrder.create({
            'partner_id': self.customer.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 3,
                'price_unit': 75,
            })]
        })

        # Mock email sending for sales orders
        with patch(
                'odoo.addons.multi_stage_approval.models.purchase_sale_inherit.SaleOrder._send_email_notification') as mock_email:
            so.action_request_approval()

            # Check that email notification was attempted for sales order
            mock_email.assert_called_once()
            self.assertTrue(mock_email.called)