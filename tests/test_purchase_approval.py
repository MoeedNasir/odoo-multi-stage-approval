from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, ValidationError


class TestPurchaseApproval(TransactionCase):
    """Test cases for purchase approval functionality"""

    def setUp(self):
        super(TestPurchaseApproval, self).setUp()
        self.PurchaseOrder = self.env['purchase.order']
        self.ApprovalFlow = self.env['approval.flow']
        self.ApprovalStage = self.env['approval.stage']
        self.ApprovalHistory = self.env['approval.history']
        self.ResPartner = self.env['res.partner']
        self.ResGroups = self.env['res.groups']
        self.Product = self.env['product.product']

        # Create test data
        self.approver_group = self.ResGroups.create({'name': 'Test Approvers'})
        self.vendor = self.ResPartner.create({'name': 'Test Vendor', 'supplier_rank': 1})
        self.product = self.Product.create({'name': 'Test Product', 'type': 'consu'})

    def test_approval_flow_creation(self):
        """Test complete approval workflow"""
        # Create approval flow
        flow = self.ApprovalFlow.create({
            'name': 'Purchase Approval Flow',
            'model': 'purchase.order',
            'company_id': self.env.company.id
        })

        # Create approval stages
        stage1 = self.ApprovalStage.create({
            'name': 'Manager Approval',
            'sequence': 10,
            'approval_flow_id': flow.id,
            'role_id': self.approver_group.id,
        })

        stage2 = self.ApprovalStage.create({
            'name': 'Director Approval',
            'sequence': 20,
            'approval_flow_id': flow.id,
            'role_id': self.approver_group.id,
            'is_final_approval': True
        })

        # Create purchase order
        po = self.PurchaseOrder.create({
            'partner_id': self.vendor.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_qty': 10,
                'price_unit': 100,
            })]
        })

        # Test approval request
        po.action_request_approval()
        self.assertEqual(po.approval_status, 'waiting')
        self.assertEqual(po.approval_stage_id, stage1)

        # Test approval history created
        history = self.ApprovalHistory.search([('purchase_order_id', '=', po.id)])
        self.assertEqual(len(history), 1)
        self.assertEqual(history.action, 'requested')

    def test_approval_permissions(self):
        """Test approval permission checks"""
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
                'product_qty': 1,
                'price_unit': 50,
            })]
        })

        po.action_request_approval()

        # Test user without permission cannot approve
        with self.assertRaises(UserError):
            po.action_approve()

    def test_auto_approval_flow(self):
        """Test multi-stage approval flow"""
        # Create flow with auto-approve stage
        flow = self.ApprovalFlow.create({
            'name': 'Auto Approval Flow',
            'model': 'purchase.order'
        })

        stage1 = self.ApprovalStage.create({
            'name': 'Stage 1',
            'sequence': 10,
            'approval_flow_id': flow.id,
            'role_id': self.approver_group.id,
            'auto_approve': True
        })

        stage2 = self.ApprovalStage.create({
            'name': 'Stage 2',
            'sequence': 20,
            'approval_flow_id': flow.id,
            'role_id': self.approver_group.id,
        })

        po = self.PurchaseOrder.create({
            'partner_id': self.vendor.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_qty': 5,
                'price_unit': 200,
            })]
        })

        # Add current user to approver group
        self.env.user.groups_id |= self.approver_group

        po.action_request_approval()
        po.action_approve()  # This should move to stage 2

        self.assertEqual(po.approval_stage_id, stage2)
        self.assertEqual(po.approval_status, 'waiting')

    def test_order_confirmation_without_approval(self):
        """Test that order cannot be confirmed without approval"""
        flow = self.ApprovalFlow.create({
            'name': 'Test Flow',
            'model': 'purchase.order'
        })

        self.ApprovalStage.create({
            'name': 'Test Stage',
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

        # Should raise error when trying to confirm without approval
        with self.assertRaises(UserError):
            po.button_confirm()

    def test_approval_domain_method(self):
        """Test the _get_approval_domain method"""
        domain = self.PurchaseOrder._get_approval_domain()

        # Admin user should get empty domain
        self.env.user.groups_id -= self.approver_group
        admin_domain = self.PurchaseOrder._get_approval_domain()
        self.assertEqual(admin_domain, [])