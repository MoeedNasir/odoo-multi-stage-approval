from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError


class TestApprovalReports(TransactionCase):
    """Test cases for approval reports"""

    def setUp(self):
        super(TestApprovalReports, self).setUp()
        self.PurchaseOrder = self.env['purchase.order']
        self.SaleOrder = self.env['sale.order']
        self.ApprovalFlow = self.env['approval.flow']
        self.ApprovalReportWizard = self.env['approval.report.wizard']
        self.ResPartner = self.env['res.partner']
        self.Product = self.env['product.product']

        # Create test data
        self.vendor = self.ResPartner.create({'name': 'Test Vendor', 'supplier_rank': 1})
        self.customer = self.ResPartner.create({'name': 'Test Customer'})
        self.product = self.Product.create({'name': 'Test Product', 'type': 'consu'})

    def test_report_wizard_creation(self):
        """Test report wizard creation and validation"""
        wizard = self.ApprovalReportWizard.create({
            'date_from': '2024-01-01',
            'date_to': '2024-12-31',
            'report_type': 'summary',
            'include_draft': True,
            'include_rejected': True,
        })

        self.assertEqual(wizard.report_type, 'summary')
        self.assertTrue(wizard.include_draft)
        self.assertTrue(wizard.include_rejected)

    def test_report_wizard_date_validation(self):
        """Test date validation in report wizard"""
        wizard = self.ApprovalReportWizard.create({
            'date_from': '2024-12-31',
            'date_to': '2024-01-01',  # Invalid: from after to
            'report_type': 'summary',
        })

        with self.assertRaises(UserError):
            wizard.generate_report()

    def test_report_data_generation(self):
        """Test report data generation"""
        # Create a purchase order with approval data
        po = self.PurchaseOrder.create({
            'partner_id': self.vendor.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_qty': 5,
                'price_unit': 100,
            })]
        })

        # Test approval report data method
        report_data = po.get_approval_report_data()

        self.assertIn('approval_history', report_data)
        self.assertIn('current_stage', report_data)
        self.assertIn('approval_status', report_data)
        self.assertIn('requires_approval', report_data)
        self.assertIn('next_approver', report_data)

    def test_summary_report_values(self):
        """Test summary report values generation"""
        # Get the report model
        report_model = self.env['report.multi_stage_approval.report_approval_summary']

        # Test report values generation
        report_values = report_model._get_report_values(docids=None, data=None)

        self.assertIn('purchase_orders', report_values)
        self.assertIn('sales_orders', report_values)
        self.assertIn('draft_orders', report_values)
        self.assertIn('waiting_orders', report_values)
        self.assertIn('approved_orders', report_values)
        self.assertIn('rejected_orders', report_values)
        self.assertIn('company', report_values)

    def test_report_actions_exist(self):
        """Test that all report actions are properly defined"""
        report_actions = [
            'multi_stage_approval.action_report_approval_summary',
            'multi_stage_approval.action_report_purchase_order_approval',
            'multi_stage_approval.action_report_sale_order_approval',
        ]

        for action_xmlid in report_actions:
            action = self.env.ref(action_xmlid, raise_if_not_found=False)
            self.assertIsNotNone(action, f"Report action {action_xmlid} should exist")

    def test_report_templates_exist(self):
        """Test that all report templates are properly defined"""
        report_templates = [
            'multi_stage_approval.report_purchase_order_approval',
            'multi_stage_approval.report_sale_order_approval',
            'multi_stage_approval.report_approval_summary',
        ]

        for template_xmlid in report_templates:
            template = self.env.ref(template_xmlid, raise_if_not_found=False)
            self.assertIsNotNone(template, f"Report template {template_xmlid} should exist")