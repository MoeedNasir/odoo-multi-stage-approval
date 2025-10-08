from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install', 'integration')
class TestApprovalIntegration(TransactionCase):
    """Integration tests for the complete approval workflow"""

    def setUp(self):
        super(TestApprovalIntegration, self).setUp()
        self.PurchaseOrder = self.env['purchase.order']
        self.SaleOrder = self.env['sale.order']
        self.ApprovalFlow = self.env['approval.flow']
        self.ApprovalStage = self.env['approval.stage']
        self.ApprovalHistory = self.env['approval.history']
        self.ResPartner = self.env['res.partner']
        self.ResGroups = self.env['res.groups']
        self.Product = self.env['product.product']
        self.MailMessage = self.env['mail.message']

        # Create test data
        self.manager_group = self.ResGroups.create({'name': 'Purchase Managers'})
        self.director_group = self.ResGroups.create({'name': 'Purchase Directors'})
        self.sales_group = self.ResGroups.create({'name': 'Sales Managers'})

        self.vendor = self.ResPartner.create({'name': 'Test Vendor', 'supplier_rank': 1})
        self.customer = self.ResPartner.create({'name': 'Test Customer'})
        self.product = self.Product.create({'name': 'Test Product', 'type': 'consu'})

        # Create test users
        self.manager_user = self.env['res.users'].create({
            'name': 'Manager User',
            'login': 'manager@example.com',
            'email': 'manager@example.com',
            'groups_id': [(4, self.manager_group.id)]
        })

        self.director_user = self.env['res.users'].create({
            'name': 'Director User',
            'login': 'director@example.com',
            'email': 'director@example.com',
            'groups_id': [(4, self.director_group.id)]
        })

        self.sales_user = self.env['res.users'].create({
            'name': 'Sales User',
            'login': 'sales@example.com',
            'email': 'sales@example.com',
            'groups_id': [(4, self.sales_group.id)]
        })

    def test_complete_purchase_approval_workflow(self):
        """Test complete multi-stage purchase approval workflow"""
        # Create approval flow with multiple stages
        flow = self.ApprovalFlow.create({
            'name': 'Multi-Stage Purchase Flow',
            'model': 'purchase.order',
            'company_id': self.env.company.id
        })

        # Create approval stages
        manager_stage = self.ApprovalStage.create({
            'name': 'Manager Approval',
            'sequence': 10,
            'approval_flow_id': flow.id,
            'role_id': self.manager_group.id,
            'minimum_amount': 0,
            'maximum_amount': 5000,
        })

        director_stage = self.ApprovalStage.create({
            'name': 'Director Approval',
            'sequence': 20,
            'approval_flow_id': flow.id,
            'role_id': self.director_group.id,
            'minimum_amount': 5000.01,
            'maximum_amount': 0,  # Unlimited
            'is_final_approval': True,
        })

        # Create purchase order
        po = self.PurchaseOrder.create({
            'partner_id': self.vendor.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_qty': 100,  # High quantity for high amount
                'price_unit': 100,  # Total: 10,000 - should go to director
            })]
        })

        # Test initial state
        self.assertEqual(po.approval_status, 'draft')
        self.assertFalse(po.requires_approval)

        # Request approval
        po.action_request_approval()
        self.assertEqual(po.approval_status, 'waiting')
        self.assertEqual(po.approval_stage_id, director_stage)  # Should skip manager due to amount

        # Test approval history
        history = self.ApprovalHistory.search([('purchase_order_id', '=', po.id)])
        self.assertEqual(len(history), 1)
        self.assertEqual(history.action, 'requested')

        # Test chatter messages
        messages = self.MailMessage.search([
            ('model', '=', 'purchase.order'),
            ('res_id', '=', po.id)
        ])
        self.assertGreater(len(messages), 0)

        # Test director approval (as director user)
        po_with_director = po.with_user(self.director_user)
        po_with_director.action_approve()

        # Check final approval
        self.assertEqual(po.approval_status, 'approved')

        # Verify approval history
        history = self.ApprovalHistory.search([('purchase_order_id', '=', po.id)])
        self.assertEqual(len(history), 2)  # Requested + Approved
        actions = history.mapped('action')
        self.assertIn('requested', actions)
        self.assertIn('approved', actions)

    def test_sales_order_approval_workflow(self):
        """Test complete sales order approval workflow"""
        # Create sales approval flow
        flow = self.ApprovalFlow.create({
            'name': 'Sales Approval Flow',
            'model': 'sale.order',
            'company_id': self.env.company.id
        })

        sales_stage = self.ApprovalStage.create({
            'name': 'Sales Manager Approval',
            'sequence': 10,
            'approval_flow_id': flow.id,
            'role_id': self.sales_group.id,
            'is_final_approval': True,
        })

        # Create sales order
        so = self.SaleOrder.create({
            'partner_id': self.customer.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 10,
                'price_unit': 500,  # Total: 5,000
            })]
        })

        # Request approval
        so.action_request_approval()
        self.assertEqual(so.approval_status, 'waiting')
        self.assertEqual(so.approval_stage_id, sales_stage)

        # Test approval as sales user
        so_with_sales = so.with_user(self.sales_user)
        so_with_sales.action_approve()

        self.assertEqual(so.approval_status, 'approved')

    def test_rejection_workflow(self):
        """Test order rejection workflow"""
        flow = self.ApprovalFlow.create({
            'name': 'Test Rejection Flow',
            'model': 'purchase.order'
        })

        stage = self.ApprovalStage.create({
            'name': 'Test Stage',
            'sequence': 10,
            'approval_flow_id': flow.id,
            'role_id': self.manager_group.id,
        })

        po = self.PurchaseOrder.create({
            'partner_id': self.vendor.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_qty': 5,
                'price_unit': 100,
            })]
        })

        # Request approval
        po.action_request_approval()

        # Reject as manager
        po_with_manager = po.with_user(self.manager_user)
        po_with_manager.action_reject()

        self.assertEqual(po.approval_status, 'rejected')

        # Verify rejection history
        history = self.ApprovalHistory.search([
            ('purchase_order_id', '=', po.id),
            ('action', '=', 'rejected')
        ])
        self.assertEqual(len(history), 1)

    def test_amount_based_routing(self):
        """Test amount-based stage routing"""
        flow = self.ApprovalFlow.create({
            'name': 'Amount Based Flow',
            'model': 'purchase.order'
        })

        # Create stages with amount ranges
        low_stage = self.ApprovalStage.create({
            'name': 'Low Amount Approval',
            'sequence': 10,
            'approval_flow_id': flow.id,
            'role_id': self.manager_group.id,
            'minimum_amount': 0,
            'maximum_amount': 1000,
            'is_final_approval': True,
        })

        high_stage = self.ApprovalStage.create({
            'name': 'High Amount Approval',
            'sequence': 20,
            'approval_flow_id': flow.id,
            'role_id': self.director_group.id,
            'minimum_amount': 1000.01,
            'maximum_amount': 0,
            'is_final_approval': True,
        })

        # Test low amount order
        po_low = self.PurchaseOrder.create({
            'partner_id': self.vendor.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_qty': 5,
                'price_unit': 100,  # Total: 500
            })]
        })

        po_low.action_request_approval()
        self.assertEqual(po_low.approval_stage_id, low_stage)

        # Test high amount order
        po_high = self.PurchaseOrder.create({
            'partner_id': self.vendor.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_qty': 15,
                'price_unit': 100,  # Total: 1,500
            })]
        })

        po_high.action_request_approval()
        self.assertEqual(po_high.approval_stage_id, high_stage)

    def test_permission_validation(self):
        """Test that users can only approve stages they have permission for"""
        flow = self.ApprovalFlow.create({
            'name': 'Permission Test Flow',
            'model': 'purchase.order'
        })

        stage = self.ApprovalStage.create({
            'name': 'Manager Only Stage',
            'sequence': 10,
            'approval_flow_id': flow.id,
            'role_id': self.manager_group.id,  # Only managers can approve
        })

        po = self.PurchaseOrder.create({
            'partner_id': self.vendor.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_qty': 2,
                'price_unit': 50,
            })]
        })

        po.action_request_approval()

        # Try to approve as sales user (should fail)
        po_with_sales = po.with_user(self.sales_user)
        with self.assertRaises(UserError):
            po_with_sales.action_approve()

        # Approve as manager (should succeed)
        po_with_manager = po.with_user(self.manager_user)
        po_with_manager.action_approve()
        self.assertEqual(po.approval_status, 'approved')

    def test_auto_confirm_configuration(self):
        """Test auto-confirm after approval configuration"""
        # Set auto-confirm parameter
        self.env['ir.config_parameter'].sudo().set_param(
            'multi_stage_approval.auto_confirm', True
        )

        flow = self.ApprovalFlow.create({
            'name': 'Auto Confirm Flow',
            'model': 'purchase.order'
        })

        stage = self.ApprovalStage.create({
            'name': 'Final Stage',
            'sequence': 10,
            'approval_flow_id': flow.id,
            'role_id': self.manager_group.id,
            'is_final_approval': True,
        })

        po = self.PurchaseOrder.create({
            'partner_id': self.vendor.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_qty': 3,
                'price_unit': 100,
            })]
        })

        # Request and approve
        po.action_request_approval()
        po_with_manager = po.with_user(self.manager_user)
        po_with_manager.action_approve()

        # Order should be automatically confirmed
        self.assertEqual(po.state, 'purchase')

    def test_concurrent_approval_attempts(self):
        """Test handling of concurrent approval attempts"""
        flow = self.ApprovalFlow.create({
            'name': 'Concurrency Test Flow',
            'model': 'purchase.order'
        })

        stage = self.ApprovalStage.create({
            'name': 'Test Stage',
            'sequence': 10,
            'approval_flow_id': flow.id,
            'role_id': self.manager_group.id,
            'is_final_approval': True,
        })

        po = self.PurchaseOrder.create({
            'partner_id': self.vendor.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_qty': 2,
                'price_unit': 75,
            })]
        })

        po.action_request_approval()

        # Create two instances for concurrent testing
        po1 = po.with_user(self.manager_user)
        po2 = po.with_user(self.manager_user)

        # First approval should succeed
        po1.action_approve()
        self.assertEqual(po.approval_status, 'approved')

        # Second approval should fail (already approved)
        with self.assertRaises(UserError):
            po2.action_approve()