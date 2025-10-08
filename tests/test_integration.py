from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install')
class TestMultiStageApprovalIntegration(TransactionCase):
    """Comprehensive integration tests for the complete approval system"""

    def setUp(self):
        super(TestMultiStageApprovalIntegration, self).setUp()
        # All models
        self.PurchaseOrder = self.env['purchase.order']
        self.SaleOrder = self.env['sale.order']
        self.ApprovalFlow = self.env['approval.flow']
        self.ApprovalStage = self.env['approval.stage']
        self.ApprovalHistory = self.env['approval.history']
        self.ResPartner = self.env['res.partner']
        self.ResGroups = self.env['res.groups']
        self.Product = self.env['product.product']
        self.MailMessage = self.env['mail.message']
        self.MailActivity = self.env['mail.activity']

        # Create comprehensive test data
        self.company = self.env.company

        # Create user groups
        self.manager_group = self.ResGroups.create({'name': 'Purchase Managers'})
        self.director_group = self.ResGroups.create({'name': 'Purchase Directors'})
        self.sales_manager_group = self.ResGroups.create({'name': 'Sales Managers'})

        # Create users
        self.manager_user = self.env['res.users'].create({
            'name': 'Purchase Manager',
            'login': 'purchase_manager',
            'email': 'manager@example.com',
            'groups_id': [(4, self.manager_group.id)]
        })

        self.director_user = self.env['res.users'].create({
            'name': 'Purchase Director',
            'login': 'purchase_director',
            'email': 'director@example.com',
            'groups_id': [(4, self.director_group.id)]
        })

        self.sales_manager_user = self.env['res.users'].create({
            'name': 'Sales Manager',
            'login': 'sales_manager',
            'email': 'sales_manager@example.com',
            'groups_id': [(4, self.sales_manager_group.id)]
        })

        # Create partners and products
        self.vendor = self.ResPartner.create({
            'name': 'Test Vendor Inc.',
            'supplier_rank': 1,
            'email': 'vendor@example.com'
        })

        self.customer = self.ResPartner.create({
            'name': 'Test Customer LLC',
            'email': 'customer@example.com'
        })

        self.product = self.Product.create({
            'name': 'Test Product - Premium',
            'type': 'consu',
            'list_price': 150.0,
            'standard_price': 100.0
        })

        # Create comprehensive approval flows
        self.purchase_flow = self.ApprovalFlow.create({
            'name': 'Multi-Level Purchase Approval',
            'model': 'purchase.order',
            'active': True,
        })

        self.sales_flow = self.ApprovalFlow.create({
            'name': 'Sales Approval Workflow',
            'model': 'sale.order',
            'active': True,
        })

        # Create multi-stage approval process
        self.manager_stage = self.ApprovalStage.create({
            'name': 'Manager Review',
            'sequence': 10,
            'approval_flow_id': self.purchase_flow.id,
            'role_id': self.manager_group.id,
            'minimum_amount': 0,
            'maximum_amount': 5000,
            'approval_type': 'mandatory',
        })

        self.director_stage = self.ApprovalStage.create({
            'name': 'Director Approval',
            'sequence': 20,
            'approval_flow_id': self.purchase_flow.id,
            'role_id': self.director_group.id,
            'minimum_amount': 5000.01,
            'maximum_amount': 0,  # Unlimited
            'is_final_approval': True,
            'approval_type': 'mandatory',
        })

        self.sales_stage = self.ApprovalStage.create({
            'name': 'Sales Manager Approval',
            'sequence': 10,
            'approval_flow_id': self.sales_flow.id,
            'role_id': self.sales_manager_group.id,
            'is_final_approval': True,
            'approval_type': 'mandatory',
        })

    def test_complete_purchase_approval_workflow(self):
        """Test complete purchase order approval workflow from start to finish"""
        # Create purchase order
        po = self.PurchaseOrder.create({
            'partner_id': self.vendor.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_qty': 50,  # Total: 50 * 100 = 5000
                'price_unit': 100,
            })]
        })

        # Verify initial state
        self.assertEqual(po.approval_status, 'draft')
        self.assertEqual(po.amount_total, 5000)
        self.assertTrue(po.requires_approval)

        # Test approval request
        po.action_request_approval()
        self.assertEqual(po.approval_status, 'waiting')
        self.assertEqual(po.approval_stage_id, self.manager_stage)

        # Verify history record created
        history = self.ApprovalHistory.search([('purchase_order_id', '=', po.id)])
        self.assertEqual(len(history), 1)
        self.assertEqual(history.action, 'requested')

        # Verify chatter message
        messages = self.MailMessage.search([('model', '=', 'purchase.order'), ('res_id', '=', po.id)])
        self.assertTrue(any('Approval requested' in message.body for message in messages))

        # Verify activity created
        activities = self.MailActivity.search([
            ('res_model', '=', 'purchase.order'),
            ('res_id', '=', po.id)
        ])
        self.assertEqual(len(activities), 1)

        # Test manager approval (as manager user)
        po_with_manager = po.with_user(self.manager_user)
        po_with_manager.action_approve()

        # Should move to director stage for amounts > 5000
        self.assertEqual(po.approval_status, 'waiting')
        self.assertEqual(po.approval_stage_id, self.director_stage)

        # Test director approval (as director user)
        po_with_director = po.with_user(self.director_user)
        po_with_director.action_approve()

        # Should be fully approved
        self.assertEqual(po.approval_status, 'approved')

        # Verify final history records
        history = self.ApprovalHistory.search([('purchase_order_id', '=', po.id)])
        self.assertEqual(len(history), 3)  # requested + manager approved + director approved

        # Test order confirmation
        po.button_confirm()
        self.assertEqual(po.state, 'purchase')

    def test_sales_order_approval_workflow(self):
        """Test complete sales order approval workflow"""
        # Create sales order
        so = self.SaleOrder.create({
            'partner_id': self.customer.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 10,
                'price_unit': 150,
            })]
        })

        # Request approval
        so.action_request_approval()
        self.assertEqual(so.approval_status, 'waiting')

        # Approve as sales manager
        so_with_manager = so.with_user(self.sales_manager_user)
        so_with_manager.action_approve()

        self.assertEqual(so.approval_status, 'approved')

        # Confirm order
        so.action_confirm()
        self.assertEqual(so.state, 'sale')

    def test_amount_based_routing(self):
        """Test that orders are routed correctly based on amount"""
        # Low amount order (should go to manager only)
        po_low = self.PurchaseOrder.create({
            'partner_id': self.vendor.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_qty': 10,  # Total: 1000
                'price_unit': 100,
            })]
        })

        po_low.action_request_approval()
        self.assertEqual(po_low.approval_stage_id, self.manager_stage)

        # High amount order (should go to director)
        po_high = self.PurchaseOrder.create({
            'partner_id': self.vendor.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_qty': 100,  # Total: 10000
                'price_unit': 100,
            })]
        })

        po_high.action_request_approval()
        self.assertEqual(po_high.approval_stage_id, self.director_stage)

    def test_rejection_workflow(self):
        """Test order rejection workflow"""
        po = self.PurchaseOrder.create({
            'partner_id': self.vendor.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_qty': 10,
                'price_unit': 100,
            })]
        })

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

    def test_permission_validation(self):
        """Test that users can only approve stages they have permission for"""
        po = self.PurchaseOrder.create({
            'partner_id': self.vendor.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_qty': 10,
                'price_unit': 100,
            })]
        })

        po.action_request_approval()

        # Try to approve with user without permissions
        with self.assertRaises(UserError):
            po.action_approve()  # Current user doesn't have manager role

    def test_auto_confirm_configuration(self):
        """Test auto-confirm after approval configuration"""
        # Enable auto-confirm
        self.env['ir.config_parameter'].sudo().set_param(
            'multi_stage_approval.auto_confirm', True
        )

        po = self.PurchaseOrder.create({
            'partner_id': self.vendor.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_qty': 10,
                'price_unit': 100,
            })]
        })

        # Request and approve
        po.action_request_approval()
        po_with_manager = po.with_user(self.manager_user)
        po_with_manager.action_approve()

        # Should be automatically confirmed
        self.assertEqual(po.state, 'purchase')

    def test_multi_company_support(self):
        """Test multi-company functionality"""
        # Create second company
        company2 = self.env['res.company'].create({
            'name': 'Test Company 2'
        })

        # Create flow for second company
        flow_company2 = self.ApprovalFlow.create({
            'name': 'Company 2 Purchase Flow',
            'model': 'purchase.order',
            'company_id': company2.id,
        })

        self.ApprovalStage.create({
            'name': 'Company 2 Stage',
            'sequence': 10,
            'approval_flow_id': flow_company2.id,
            'role_id': self.manager_group.id,
        })

        # Test that each company has its own flow
        flow1 = self.ApprovalFlow.search([
            ('model', '=', 'purchase.order'),
            ('company_id', '=', self.company.id)
        ])
        flow2 = self.ApprovalFlow.search([
            ('model', '=', 'purchase.order'),
            ('company_id', '=', company2.id)
        ])

        self.assertTrue(flow1)
        self.assertTrue(flow2)
        self.assertNotEqual(flow1, flow2)

    def test_performance_large_dataset(self):
        """Test performance with larger datasets"""
        # Create multiple orders
        for i in range(10):
            po = self.PurchaseOrder.create({
                'partner_id': self.vendor.id,
                'order_line': [(0, 0, {
                    'product_id': self.product.id,
                    'product_qty': 5,
                    'price_unit': 100,
                })]
            })
            po.action_request_approval()

        # Test bulk operations
        pending_orders = self.PurchaseOrder.search([('approval_status', '=', 'waiting')])
        self.assertEqual(len(pending_orders), 10)

        # Test search performance
        import time
        start_time = time.time()

        # Complex search with multiple domains
        domain = [
            ('approval_status', 'in', ['waiting', 'approved']),
            ('amount_total', '>=', 100),
            ('partner_id', '=', self.vendor.id)
        ]
        results = self.PurchaseOrder.search(domain)

        end_time = time.time()
        execution_time = end_time - start_time

        # Should complete in reasonable time
        self.assertLess(execution_time, 5.0, "Search should complete within 5 seconds")
        self.assertTrue(len(results) > 0)

    def test_error_handling_and_edge_cases(self):
        """Test error handling and edge cases"""
        # Test approval request on already approved order
        po = self.PurchaseOrder.create({
            'partner_id': self.vendor.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_qty': 10,
                'price_unit': 100,
            })]
        })

        po.action_request_approval()
        po_with_manager = po.with_user(self.manager_user)
        po_with_manager.action_approve()

        # Try to request approval again
        with self.assertRaises(UserError):
            po.action_request_approval()

        # Test approval without flow configuration
        po_no_flow = self.PurchaseOrder.create({
            'partner_id': self.vendor.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_qty': 1,
                'price_unit': 10,
            })]
        })

        # Temporarily remove flows
        self.purchase_flow.active = False

        with self.assertRaises(UserError):
            po_no_flow.action_request_approval()

        # Restore flows
        self.purchase_flow.active = True

    def test_data_integrity_and_constraints(self):
        """Test data integrity and model constraints"""
        # Test duplicate flow constraint
        with self.assertRaises(ValidationError):
            self.ApprovalFlow.create({
                'name': 'Duplicate Flow',
                'model': 'purchase.order',
                'company_id': self.company.id,
            })

        # Test stage amount validation
        with self.assertRaises(ValidationError):
            self.ApprovalStage.create({
                'name': 'Invalid Amount Stage',
                'sequence': 30,
                'approval_flow_id': self.purchase_flow.id,
                'role_id': self.manager_group.id,
                'minimum_amount': 1000,
                'maximum_amount': 500,  # Invalid: min > max
            })

    def test_backward_compatibility(self):
        """Test that existing data remains compatible"""
        # Create order without approval data (simulating pre-module data)
        po = self.PurchaseOrder.create({
            'partner_id': self.vendor.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_qty': 5,
                'price_unit': 50,
            })]
        })

        # Should handle gracefully
        self.assertEqual(po.approval_status, 'draft')
        self.assertFalse(po.requires_approval)

        # Should be able to confirm without approval
        po.button_confirm()
        self.assertEqual(po.state, 'purchase')