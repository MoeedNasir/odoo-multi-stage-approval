from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, ValidationError


class TestSalesApproval(TransactionCase):
    """Test cases for sales approval functionality"""

    def setUp(self):
        super(TestSalesApproval, self).setUp()
        self.SaleOrder = self.env['sale.order']
        self.ApprovalFlow = self.env['approval.flow']
        self.ApprovalStage = self.env['approval.stage']
        self.ResPartner = self.env['res.partner']
        self.ResGroups = self.env['res.groups']
        self.Product = self.env['product.product']

        # Create test data
        self.approver_group = self.ResGroups.create({'name': 'Sales Approvers'})
        self.customer = self.ResPartner.create({'name': 'Test Customer'})
        self.product = self.Product.create({'name': 'Test Product', 'type': 'consu'})

    def test_sales_approval_workflow(self):
        """Test complete sales approval workflow"""
        # Create approval flow
        flow = self.ApprovalFlow.create({
            'name': 'Sales Approval Flow',
            'model': 'sale.order',
            'company_id': self.env.company.id
        })

        # Create approval stages
        stage1 = self.ApprovalStage.create({
            'name': 'Sales Manager Approval',
            'sequence': 10,
            'approval_flow_id': flow.id,
            'role_id': self.approver_group.id,
        })

        stage2 = self.ApprovalStage.create({
            'name': 'Sales Director Approval',
            'sequence': 20,
            'approval_flow_id': flow.id,
            'role_id': self.approver_group.id,
            'is_final_approval': True
        })

        # Create sales order
        so = self.SaleOrder.create({
            'partner_id': self.customer.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 10,
                'price_unit': 100,
            })]
        })

        # Test approval request
        so.action_request_approval()
        self.assertEqual(so.approval_status, 'waiting')
        self.assertEqual(so.approval_stage_id, stage1)

        # Test cannot confirm without approval
        with self.assertRaises(UserError):
            so.action_confirm()

    def test_sales_approval_amount_based(self):
        """Test amount-based approval routing"""
        flow = self.ApprovalFlow.create({
            'name': 'Amount Based Sales Flow',
            'model': 'sale.order'
        })

        # Create stages with amount ranges
        stage_low = self.ApprovalStage.create({
            'name': 'Low Amount Approval',
            'sequence': 10,
            'approval_flow_id': flow.id,
            'role_id': self.approver_group.id,
            'minimum_amount': 0,
            'maximum_amount': 1000,
            'is_final_approval': True
        })

        stage_high = self.ApprovalStage.create({
            'name': 'High Amount Approval',
            'sequence': 20,
            'approval_flow_id': flow.id,
            'role_id': self.approver_group.id,
            'minimum_amount': 1000.01,
            'maximum_amount': 0,
            'is_final_approval': True
        })

        # Test low amount order
        so_low = self.SaleOrder.create({
            'partner_id': self.customer.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 5,
                'price_unit': 100,  # Total: 500
            })]
        })

        so_low.action_request_approval()
        self.assertEqual(so_low.approval_stage_id, stage_low)

        # Test high amount order
        so_high = self.SaleOrder.create({
            'partner_id': self.customer.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 15,
                'price_unit': 100,  # Total: 1500
            })]
        })

        so_high.action_request_approval()
        self.assertEqual(so_high.approval_stage_id, stage_high)

    def test_advanced_approval_features(self):
        """Test advanced approval features"""
        # Test configuration settings
        config = self.env['res.config.settings'].create({})

        # Test auto-confirm setting
        config.approval_auto_confirm = True
        config.set_values()

        auto_confirm = self.env['ir.config_parameter'].sudo().get_param(
            'multi_stage_approval.auto_confirm'
        )
        self.assertEqual(auto_confirm, 'True')

    def test_approval_history_tracking(self):
        """Test approval history tracking for sales orders"""
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
                'product_uom_qty': 2,
                'price_unit': 50,
            })]
        })

        # Add current user to approver group
        self.env.user.groups_id |= self.approver_group

        so.action_request_approval()
        so.action_approve()

        # Check history records
        history = self.env['approval.history'].search([
            ('sale_order_id', '=', so.id)
        ])
        self.assertEqual(len(history), 2)  # Requested + Approved

        actions = history.mapped('action')
        self.assertIn('requested', actions)
        self.assertIn('approved', actions)