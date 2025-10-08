from odoo.tests.common import TransactionCase, tagged
import time
import logging

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install', 'performance')
class TestApprovalPerformance(TransactionCase):
    """Performance tests for approval system"""

    def setUp(self):
        super(TestApprovalPerformance, self).setUp()
        self.PurchaseOrder = self.env['purchase.order']
        self.SaleOrder = self.env['sale.order']
        self.ApprovalFlow = self.env['approval.flow']
        self.ApprovalStage = self.env['approval.stage']
        self.ResPartner = self.env['res.partner']
        self.ResGroups = self.env['res.groups']
        self.Product = self.env['product.product']

        # Create test data
        self.approver_group = self.ResGroups.create({'name': 'Performance Test Approvers'})
        self.vendor = self.ResPartner.create({'name': 'Performance Vendor', 'supplier_rank': 1})
        self.customer = self.ResPartner.create({'name': 'Performance Customer'})
        self.product = self.Product.create({'name': 'Performance Product', 'type': 'consu'})

        # Create approval user
        self.approver_user = self.env['res.users'].create({
            'name': 'Performance Approver',
            'login': 'performance_approver@example.com',
            'groups_id': [(4, self.approver_group.id)]
        })

    def test_bulk_approval_performance(self):
        """Test performance with bulk approval operations"""
        # Create approval flow
        flow = self.ApprovalFlow.create({
            'name': 'Performance Test Flow',
            'model': 'purchase.order'
        })

        stage = self.ApprovalStage.create({
            'name': 'Performance Stage',
            'sequence': 10,
            'approval_flow_id': flow.id,
            'role_id': self.approver_group.id,
            'is_final_approval': True,
        })

        # Create multiple purchase orders
        start_time = time.time()

        order_count = 50  # Test with 50 orders
        purchase_orders = self.PurchaseOrder

        for i in range(order_count):
            po = self.PurchaseOrder.create({
                'name': f'PERF-PO-{i:04d}',
                'partner_id': self.vendor.id,
                'order_line': [(0, 0, {
                    'product_id': self.product.id,
                    'product_qty': 1,
                    'price_unit': 100 + i,
                })]
            })
            purchase_orders += po

        creation_time = time.time() - start_time
        _logger.info("Created %d purchase orders in %.2f seconds", order_count, creation_time)

        # Bulk approval request
        start_time = time.time()
        for po in purchase_orders:
            po.action_request_approval()
        approval_request_time = time.time() - start_time
        _logger.info("Requested approval for %d orders in %.2f seconds", order_count, approval_request_time)

        # Bulk approval
        start_time = time.time()
        for po in purchase_orders.with_user(self.approver_user):
            po.action_approve()
        approval_time = time.time() - start_time
        _logger.info("Approved %d orders in %.2f seconds", order_count, approval_time)

        # Performance assertions
        self.assertLess(creation_time, 10.0, "Order creation should be fast")
        self.assertLess(approval_request_time, 15.0, "Approval requests should be fast")
        self.assertLess(approval_time, 20.0, "Approvals should be fast")

        # Verify all orders are approved
        approved_count = self.PurchaseOrder.search_count([('approval_status', '=', 'approved')])
        self.assertEqual(approved_count, order_count, "All orders should be approved")

    def test_large_amount_computation_performance(self):
        """Test performance of amount-based computations"""
        flow = self.ApprovalFlow.create({
            'name': 'Amount Based Performance Flow',
            'model': 'purchase.order'
        })

        # Create multiple stages with amount ranges
        for i in range(5):  # Create 5 stages
            self.ApprovalStage.create({
                'name': f'Stage {i + 1}',
                'sequence': (i + 1) * 10,
                'approval_flow_id': flow.id,
                'role_id': self.approver_group.id,
                'minimum_amount': i * 1000,
                'maximum_amount': (i + 1) * 1000 if i < 4 else 0,
                'is_final_approval': i == 4,
            })

        # Test with orders of different amounts
        start_time = time.time()

        for amount in [500, 1500, 2500, 3500, 4500, 5500]:
            po = self.PurchaseOrder.create({
                'partner_id': self.vendor.id,
                'order_line': [(0, 0, {
                    'product_id': self.product.id,
                    'product_qty': 1,
                    'price_unit': amount,
                })]
            })

            # Time the approval request
            request_start = time.time()
            po.action_request_approval()
            request_time = time.time() - request_start

            _logger.info("Amount %d: Approval request took %.4f seconds", amount, request_time)
            self.assertLess(request_time, 1.0, f"Approval request for amount {amount} should be fast")

        total_time = time.time() - start_time
        _logger.info("Total amount-based routing test took %.2f seconds", total_time)

    def test_history_tracking_performance(self):
        """Test performance of approval history tracking"""
        flow = self.ApprovalFlow.create({
            'name': 'History Performance Flow',
            'model': 'purchase.order'
        })

        stage = self.ApprovalStage.create({
            'name': 'Performance Stage',
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

        # Test multiple approval cycles
        start_time = time.time()
        cycles = 10

        for cycle in range(cycles):
            # Reset to draft
            po.write({'approval_status': 'draft'})

            # Request approval
            po.action_request_approval()

            # Approve
            po.with_user(self.approver_user).action_approve()

        total_time = time.time() - start_time
        average_time = total_time / cycles

        _logger.info("Completed %d approval cycles in %.2f seconds (avg: %.2f sec/cycle)",
                     cycles, total_time, average_time)

        # Verify history records
        history_count = self.env['approval.history'].search_count([
            ('purchase_order_id', '=', po.id)
        ])
        expected_count = cycles * 2  # Requested + Approved for each cycle
        self.assertEqual(history_count, expected_count, "Should have correct number of history records")

        self.assertLess(average_time, 2.0, "Average approval cycle should be fast")

    def test_search_and_filter_performance(self):
        """Test performance of search and filter operations"""
        flow = self.ApprovalFlow.create({
            'name': 'Search Performance Flow',
            'model': 'purchase.order'
        })

        stage = self.ApprovalStage.create({
            'name': 'Search Stage',
            'sequence': 10,
            'approval_flow_id': flow.id,
            'role_id': self.approver_group.id,
            'is_final_approval': True,
        })

        # Create test data
        order_count = 100
        for i in range(order_count):
            status = 'draft' if i % 4 == 0 else 'waiting' if i % 4 == 1 else 'approved' if i % 4 == 2 else 'rejected'

            po = self.PurchaseOrder.create({
                'name': f'SEARCH-PO-{i:04d}',
                'partner_id': self.vendor.id,
                'order_line': [(0, 0, {
                    'product_id': self.product.id,
                    'product_qty': 1,
                    'price_unit': 100 + i,
                })],
                'approval_status': status,
            })

            if status == 'waiting':
                po.write({'approval_stage_id': stage.id})

        # Test search performance for different statuses
        statuses = ['draft', 'waiting', 'approved', 'rejected']

        for status in statuses:
            start_time = time.time()
            orders = self.PurchaseOrder.search([('approval_status', '=', status)])
            search_time = time.time() - start_time

            _logger.info("Search for status '%s' found %d orders in %.4f seconds",
                         status, len(orders), search_time)

            self.assertLess(search_time, 1.0, f"Search for {status} should be fast")

        # Test complex domain search
        start_time = time.time()
        complex_domain = [
            '|',
            ('approval_status', 'in', ['waiting', 'approved']),
            ('amount_total', '>', 150)
        ]
        complex_results = self.PurchaseOrder.search(complex_domain)
        complex_time = time.time() - start_time

        _logger.info("Complex domain search found %d orders in %.4f seconds",
                     len(complex_results), complex_time)

        self.assertLess(complex_time, 1.0, "Complex domain search should be fast")