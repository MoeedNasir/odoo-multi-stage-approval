from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta


class ApprovalReports(models.AbstractModel):
    _name = 'report.multi_stage_approval.report_approval_summary'
    _description = 'Approval Summary Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Generate report values for approval summary"""
        # Get date range from context or use default
        date_from = self._context.get('date_from')
        date_to = self._context.get('date_to')

        if not date_from:
            date_from = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        if not date_to:
            date_to = datetime.now().strftime('%Y-%m-%d')

        # Build domain for date filtering
        domain = [
            ('approval_history_ids.date', '>=', date_from),
            ('approval_history_ids.date', '<=', date_to)
        ]

        # Get purchase orders
        purchase_orders = self.env['purchase.order'].search(domain)

        # Get sales orders
        sales_orders = self.env['sale.order'].search(domain)

        # Categorize orders by status
        all_orders = list(purchase_orders) + list(sales_orders)

        draft_orders = [o for o in all_orders if o.approval_status == 'draft']
        waiting_orders = [o for o in all_orders if o.approval_status == 'waiting']
        approved_orders = [o for o in all_orders if o.approval_status == 'approved']
        rejected_orders = [o for o in all_orders if o.approval_status == 'rejected']

        return {
            'doc_ids': docids,
            'doc_model': 'approval.flow',
            'docs': self.env['approval.flow'].browse(docids),
            'purchase_orders': purchase_orders,
            'sales_orders': sales_orders,
            'draft_orders': draft_orders,
            'waiting_orders': waiting_orders,
            'approved_orders': approved_orders,
            'rejected_orders': rejected_orders,
            'company': self.env.company,
            'date_from': date_from,
            'date_to': date_to,
        }


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def get_approval_report_data(self):
        """Get approval data for reports"""
        return {
            'approval_history': self.approval_history_ids.sorted('date'),
            'current_stage': self.approval_stage_id,
            'approval_status': self.approval_status,
            'requires_approval': self.requires_approval,
            'next_approver': self.next_approver_id,
        }


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def get_approval_report_data(self):
        """Get approval data for reports"""
        return {
            'approval_history': self.approval_history_ids.sorted('date'),
            'current_stage': self.approval_stage_id,
            'approval_status': self.approval_status,
            'requires_approval': self.requires_approval,
            'next_approver': self.next_approver_id,
        }