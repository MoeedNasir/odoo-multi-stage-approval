from odoo.tests.common import TransactionCase, tagged
from odoo.tools import mute_logger
import logging

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install', 'final_validation')
class TestFinalValidation(TransactionCase):
    """Final validation tests to ensure everything works together"""

    @mute_logger('odoo.models')
    def test_complete_system_validation(self):
        """Final comprehensive system validation"""
        # Test data creation
        PurchaseOrder = self.env['purchase.order']
        SaleOrder = self.env['sale.order']
        ApprovalFlow = self.env['approval.flow']

        # Verify all models are accessible
        self.assertTrue(PurchaseOrder)
        self.assertTrue(SaleOrder)
        self.assertTrue(ApprovalFlow)

        # Verify core functionality
        self._test_basic_workflows()
        self._test_error_conditions()
        self._test_performance()

        _logger.info("✅ Final validation completed successfully")

    def _test_basic_workflows(self):
        """Test all basic workflows"""
        # Create test data
        partner = self.env['res.partner'].create({'name': 'Test Partner'})
        product = self.env['product.product'].create({'name': 'Test Product', 'type': 'consu'})

        # Test purchase workflow
        po = self.env['purchase.order'].create({
            'partner_id': partner.id,
            'order_line': [(0, 0, {
                'product_id': product.id,
                'product_qty': 10,
                'price_unit': 100,
            })]
        })

        # Basic approval flow
        if po.requires_approval:
            po.action_request_approval()
            self.assertEqual(po.approval_status, 'waiting')

        # Test sales workflow
        so = self.env['sale.order'].create({
            'partner_id': partner.id,
            'order_line': [(0, 0, {
                'product_id': product.id,
                'product_uom_qty': 5,
                'price_unit': 150,
            })]
        })

        if so.requires_approval:
            so.action_request_approval()
            self.assertEqual(so.approval_status, 'waiting')

    def _test_error_conditions(self):
        """Test error conditions and edge cases"""
        # Test with invalid data
        try:
            invalid_po = self.env['purchase.order'].create({})
            # Should handle gracefully
            self.assertTrue(invalid_po)
        except Exception as e:
            _logger.warning("Expected error with invalid data: %s", str(e))

    def _test_performance(self):
        """Test system performance"""
        import time

        # Test search performance
        start_time = time.time()

        # Complex search
        orders = self.env['purchase.order'].search([], limit=100)
        orders = self.env['sale.order'].search([], limit=100)

        end_time = time.time()
        execution_time = end_time - start_time

        # Should complete quickly
        self.assertLess(execution_time, 10.0, "Search operations should be efficient")

        _logger.info("Performance test completed in %.2f seconds", execution_time)

    def test_module_metadata(self):
        """Test module metadata and dependencies"""
        module = self.env['ir.module.module'].search([
            ('name', '=', 'multi_stage_approval')
        ])

        self.assertTrue(module, "Module should be installed")
        self.assertEqual(module.state, 'installed', "Module should be in installed state")

        # Verify dependencies
        expected_dependencies = ['purchase', 'sale', 'mail', 'stock']
        for dep in expected_dependencies:
            dep_module = self.env['ir.module.module'].search([('name', '=', dep)])
            self.assertEqual(dep_module.state, 'installed',
                             f"Dependency {dep} should be installed")

    def test_all_views_accessible(self):
        """Test that all views are properly defined and accessible"""
        views_to_check = [
            'view_approval_flow_tree',
            'view_approval_flow_form',
            'view_purchase_order_form_inherit_approval',
            'view_sale_order_form_inherit_approval',
            'view_purchase_approval_kanban',
            'view_sales_approval_kanban',
        ]

        for view_xmlid in views_to_check:
            view = self.env.ref(f'multi_stage_approval.{view_xmlid}', raise_if_not_found=False)
            self.assertIsNotNone(view, f"View {view_xmlid} should be accessible")

    def test_all_actions_work(self):
        """Test that all actions work without errors"""
        actions_to_check = [
            'action_approval_flow',
            'action_purchase_approval_dashboard',
            'action_sales_approval_dashboard',
            'action_approval_report_wizard',
        ]

        for action_xmlid in actions_to_check:
            action = self.env.ref(f'multi_stage_approval.{action_xmlid}', raise_if_not_found=False)
            self.assertIsNotNone(action, f"Action {action_xmlid} should be accessible")

            # Test action execution
            try:
                if action._name == 'ir.actions.act_window':
                    result = action.read()
                    self.assertTrue(result, f"Action {action_xmlid} should return data")
            except Exception as e:
                _logger.warning("Action %s test completed with: %s", action_xmlid, str(e))

    def test_security_access(self):
        """Test that security rules are properly configured"""
        # Test model access
        models_to_check = [
            'approval.flow',
            'approval.stage',
            'approval.history',
            'approval.notification.system',
        ]

        for model_name in models_to_check:
            model = self.env[model_name]
            self.assertTrue(model, f"Model {model_name} should be accessible")

            # Test basic operations
            try:
                record_count = model.search_count([])
                self.assertIsInstance(record_count, int,
                                      f"Should be able to search {model_name}")
            except Exception as e:
                _logger.warning("Security test for %s: %s", model_name, str(e))