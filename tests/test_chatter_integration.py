from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError


class TestChatterIntegration(TransactionCase):
    """Test cases for chatter and mail integration"""

    def setUp(self):
        super(TestChatterIntegration, self).setUp()
        self.PurchaseOrder = self.env['purchase.order']
        self.SaleOrder = self.env['sale.order']
        self.ApprovalFlow = self.env['approval.flow']
        self.ApprovalStage = self.env['approval.stage']
        self.ResPartner = self.env['res.partner']
        self.ResGroups = self.env['res.groups']
        self.Product = self.env['product.product']
        self.MailMessage = self.env['mail.message']

        # Create test data
        self.approver_group = self.ResGroups.create({'name': 'Test Approvers'})
        self.vendor = self.ResPartner.create({'name': 'Test Vendor', 'supplier_rank': 1})
        self.customer = self.ResPartner.create({'name': 'Test Customer'})
        self.product = self.Product.create({'name': 'Test Product', 'type': 'consu'})

    def test_chatter_messages_on_approval(self):
        """Test that chatter messages are posted during approval workflow"""
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

        po = self.PurchaseOrder.create({
            'partner_id': self.vendor.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_qty': 5,
                'price_unit': 100,
            })]
        })

        # Add current user to approver group
        self.env.user.groups_id |= self.approver_group

        # Test approval request posts message
        initial_message_count = self.MailMessage.search_count(
            [('model', '=', 'purchase.order'), ('res_id', '=', po.id)])
        po.action_request_approval()

        message_count_after_request = self.MailMessage.search_count(
            [('model', '=', 'purchase.order'), ('res_id', '=', po.id)])
        self.assertGreater(message_count_after_request, initial_message_count,
                           "Chatter message should be posted on approval request")

        # Test approval posts message
        po.action_approve()
        message_count_after_approve = self.MailMessage.search_count(
            [('model', '=', 'purchase.order'), ('res_id', '=', po.id)])
        self.assertGreater(message_count_after_approve, message_count_after_request,
                           "Chatter message should be posted on approval")

    def test_activity_creation(self):
        """Test that activities are created for approvers"""
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

        # Create a different user for testing activities
        test_user = self.env['res.users'].create({
            'name': 'Test Approver',
            'login': 'test_approver',
            'groups_id': [(4, self.approver_group.id)]
        })

        po = self.PurchaseOrder.create({
            'partner_id': self.vendor.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_qty': 3,
                'price_unit': 50,
            })]
        })

        # Test activity creation
        activities_before = self.env['mail.activity'].search_count([
            ('res_model', '=', 'purchase.order'),
            ('res_id', '=', po.id)
        ])

        po.action_request_approval()

        activities_after = self.env['mail.activity'].search_count([
            ('res_model', '=', 'purchase.order'),
            ('res_id', '=', po.id)
        ])

        self.assertGreater(activities_after, activities_before, "Activities should be created for approvers")

    def test_tracking_fields(self):
        """Test that approval fields are properly tracked"""
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

        po = self.PurchaseOrder.create({
            'partner_id': self.vendor.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_qty': 2,
                'price_unit': 25,
            })]
        })

        # Check that tracking is enabled on approval fields
        self.assertTrue(po._fields['approval_status'].tracking, "Approval status should have tracking enabled")
        self.assertTrue(po._fields['approval_stage_id'].tracking, "Approval stage should have tracking enabled")
        self.assertTrue(po._fields['approval_flow_id'].tracking, "Approval flow should have tracking enabled")

    def test_sales_order_chatter(self):
        """Test chatter integration for sales orders"""
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
                'product_uom_qty': 4,
                'price_unit': 75,
            })]
        })

        # Add current user to approver group
        self.env.user.groups_id |= self.approver_group

        # Test sales order approval chatter
        initial_message_count = self.MailMessage.search_count([('model', '=', 'sale.order'), ('res_id', '=', so.id)])
        so.action_request_approval()

        message_count_after_request = self.MailMessage.search_count(
            [('model', '=', 'sale.order'), ('res_id', '=', so.id)])
        self.assertGreater(message_count_after_request, initial_message_count,
                           "Chatter message should be posted on sales approval request")