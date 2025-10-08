from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install', 'edge_cases')
class TestApprovalEdgeCases(TransactionCase):
    """Edge case tests for approval system"""

    def setUp(self):
        super(TestApprovalEdgeCases, self).setUp()
        self.PurchaseOrder = self.env['purchase.order']
        self.SaleOrder = self.env['sale.order']
        self.ApprovalFlow = self.env['approval.flow']
        self.ApprovalStage = self.env['approval.stage']
        self.ResPartner = self.env['res.partner']
        self.ResGroups = self.env['res.groups']
        self.Product = self.env['product.product']

        # Create test data
        self.approver_group = self.ResGroups.create({'name': 'Edge Case Approvers'})
        self.vendor = self.ResPartner.create({'name': 'Edge Case Vendor', 'supplier_rank': 1})
        self.product = self.Product.create({'name': 'Edge Case Product', 'type': 'consu'})

        # Create approver user
        self.approver_user = self.env['res.users'].create({
            'name': 'Edge Case Approver',
            'login': 'edge_approver@example.com',
            'groups_id': [(4, self.approver_group.id)]
        })

    def test_empty_approval_flow(self):
        """Test behavior when approval flow has no stages"""
        flow = self.ApprovalFlow.create({
            'name': 'Empty Flow',
            'model': 'purchase.order'
        })
        # No stages created

        po = self.PurchaseOrder.create({
            'partner_id': self.vendor.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_qty': 1,
                'price_unit': 100,
            })]
        })

        # Should raise error when no stages configured
        with self.assertRaises(UserError):
            po.action_request_approval()

    def test_zero_amount_order(self):
        """Test approval for orders with zero amount"""
        flow = self.ApprovalFlow.create({
            'name': 'Zero Amount Flow',
            'model': 'purchase.order'
        })

        stage = self.ApprovalStage.create({
            'name': 'Zero Amount Stage',
            'sequence': 10,
            'approval_flow_id': flow.id,
            'role_id': self.approver_group.id,
            'minimum_amount': 0,
            'maximum_amount': 0,  # Should match any amount
            'is_final_approval': True,
        })

        po = self.PurchaseOrder.create({
            'partner_id': self.vendor.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_qty': 0,  # Zero quantity
                'price_unit': 100,
            })]
        })

        # Should work with zero amount
        po.action_request_approval()
        self.assertEqual(po.approval_stage_id, stage)

        po.with_user(self.approver_user).action_approve()
        self.assertEqual(po.approval_status, 'approved')

    def test_very_large_amount(self):
        """Test approval for orders with very large amounts"""
        flow = self.ApprovalFlow.create({
            'name': 'Large Amount Flow',
            'model': 'purchase.order'
        })

        stage = self.ApprovalStage.create({
            'name': 'Large Amount Stage',
            'sequence': 10,
            'approval_flow_id': flow.id,
            'role_id': self.approver_group.id,
            'minimum_amount': 1000000,  # 1 million
            'maximum_amount': 0,
            'is_final_approval': True,
        })

        po = self.PurchaseOrder.create({
            'partner_id': self.vendor.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_qty': 10000,  # Large quantity
                'price_unit': 1000,  # High price
            })]
        })

        # Should handle large amounts correctly
        po.action_request_approval()
        self.assertEqual(po.approval_stage_id, stage)

    def test_duplicate_approval_requests(self):
        """Test behavior when approval is requested multiple times"""
        flow = self.ApprovalFlow.create({
            'name': 'Duplicate Request Flow',
            'model': 'purchase.order'
        })

        stage = self.ApprovalStage.create({
            'name': 'Duplicate Stage',
            'sequence': 10,
            'approval_flow_id': flow.id,
            'role_id': self.approver_group.id,
        })

        po = self.PurchaseOrder.create({
            'partner_id': self.vendor.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_qty': 1,
                'price_unit': 100,
            })]
        })

        # First request should succeed
        po.action_request_approval()
        self.assertEqual(po.approval_status, 'waiting')

        # Second request should fail
        with self.assertRaises(UserError):
            po.action_request_approval()

    def test_invalid_state_transitions(self):
        """Test invalid state transitions"""
        flow = self.ApprovalFlow.create({
            'name': 'State Transition Flow',
            'model': 'purchase.order'
        })

        stage = self.ApprovalStage.create({
            'name': 'Transition Stage',
            'sequence': 10,
            'approval_flow_id': flow.id,
            'role_id': self.approver_group.id,
        })

        po = self.PurchaseOrder.create({
            'partner_id': self.vendor.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_qty': 1,
                'price_unit': 100,
            })]
        })

        # Try to approve from draft (should fail)
        with self.assertRaises(UserError):
            po.action_approve()

        # Try to reject from draft (should fail)
        with self.assertRaises(UserError):
            po.action_reject()

        # Request approval
        po.action_request_approval()

        # Try to request approval again (should fail)
        with self.assertRaises(UserError):
            po.action_request_approval()

    def test_stage_with_no_approvers(self):
        """Test stage with no users in approver group"""
        empty_group = self.ResGroups.create({'name': 'Empty Approvers'})

        flow = self.ApprovalFlow.create({
            'name': 'Empty Approvers Flow',
            'model': 'purchase.order'
        })

        stage = self.ApprovalStage.create({
            'name': 'Empty Approvers Stage',
            'sequence': 10,
            'approval_flow_id': flow.id,
            'role_id': empty_group.id,  # No users in this group
            'is_final_approval': True,
        })

        po = self.PurchaseOrder.create({
            'partner_id': self.vendor.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_qty': 1,
                'price_unit': 100,
            })]
        })

        # Request approval should work
        po.action_request_approval()
        self.assertEqual(po.approval_status, 'waiting')

        # But no one can approve (no users in group)
        # This is a valid scenario - approval will wait indefinitely

    def test_multiple_companies(self):
        """Test approval system with multiple companies"""
        # Create second company
        company2 = self.env['res.company'].create({
            'name': 'Test Company 2'
        })

        # Create flow for second company
        flow_company2 = self.ApprovalFlow.create({
            'name': 'Company 2 Flow',
            'model': 'purchase.order',
            'company_id': company2.id
        })

        stage_company2 = self.ApprovalStage.create({
            'name': 'Company 2 Stage',
            'sequence': 10,
            'approval_flow_id': flow_company2.id,
            'role_id': self.approver_group.id,
        })

        # Create order in second company
        po_company2 = self.PurchaseOrder.create({
            'partner_id': self.vendor.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_qty': 1,
                'price_unit': 100,
            })]
        })

        # Should not find flow from different company
        with self.assertRaises(UserError):
            po_company2.action_request_approval()

    def test_currency_handling(self):
        """Test approval with different currencies"""
        # Create another currency
        other_currency = self.env['res.currency'].create({
            'name': 'Test Currency',
            'symbol': 'TC',
            'rounding': 0.01,
            'currency_unit_label': 'Test Unit',
            'currency_subunit_label': 'Test Subunit',
        })

        flow = self.ApprovalFlow.create({
            'name': 'Currency Test Flow',
            'model': 'purchase.order'
        })

        stage = self.ApprovalStage.create({
            'name': 'Currency Stage',
            'sequence': 10,
            'approval_flow_id': flow.id,
            'role_id': self.approver_group.id,
            'minimum_amount': 0,
            'maximum_amount': 1000,
        })

        po = self.PurchaseOrder.create({
            'partner_id': self.vendor.id,
            'currency_id': other_currency.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_qty': 1,
                'price_unit': 500,
            })]
        })

        # Should handle different currencies correctly
        po.action_request_approval()
        self.assertEqual(po.approval_stage_id, stage)

    def test_deleted_approval_flow(self):
        """Test behavior when approval flow is deleted"""
        flow = self.ApprovalFlow.create({
            'name': 'To Be Deleted Flow',
            'model': 'purchase.order'
        })

        stage = self.ApprovalStage.create({
            'name': 'To Be Deleted Stage',
            'sequence': 10,
            'approval_flow_id': flow.id,
            'role_id': self.approver_group.id,
        })

        po = self.PurchaseOrder.create({
            'partner_id': self.vendor.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_qty': 1,
                'price_unit': 100,
            })]
        })

        # Request approval
        po.action_request_approval()

        # Delete the flow
        flow.unlink()

        # Order should still maintain its state
        self.assertEqual(po.approval_status, 'waiting')
        self.assertEqual(po.approval_flow_id, flow)  # Reference remains

        # But new approval requests should fail
        po2 = self.PurchaseOrder.create({
            'partner_id': self.vendor.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_qty': 1,
                'price_unit': 100,
            })]
        })

        with self.assertRaises(UserError):
            po2.action_request_approval()