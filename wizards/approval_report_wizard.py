from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta


class ApprovalReportWizard(models.TransientModel):
    _name = 'approval.report.wizard'
    _description = 'Approval Report Wizard'

    date_from = fields.Date(string='From Date', required=True,
                            default=lambda self: (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
    date_to = fields.Date(string='To Date', required=True,
                          default=lambda self: datetime.now().strftime('%Y-%m-%d'))
    report_type = fields.Selection([
        ('summary', 'Summary Report'),
        ('purchase', 'Purchase Orders Only'),
        ('sales', 'Sales Orders Only'),
        ('detailed', 'Detailed Report')
    ], string='Report Type', default='summary', required=True)
    include_draft = fields.Boolean(string='Include Draft Orders', default=False)
    include_rejected = fields.Boolean(string='Include Rejected Orders', default=True)

    @api.model
    def default_get(self, fields):
        """Set default values"""
        res = super(ApprovalReportWizard, self).default_get(fields)
        # Set default date range to last 30 days
        today = datetime.now().date()
        res['date_from'] = (today - timedelta(days=30)).strftime('%Y-%m-%d')
        res['date_to'] = today.strftime('%Y-%m-%d')
        return res

    def generate_report(self):
        """Generate the approval report"""
        self.ensure_one()

        # Validate date range
        if self.date_from > self.date_to:
            raise UserError(_("From Date cannot be after To Date."))

        # Prepare report action based on type
        if self.report_type == 'summary':
            return self._generate_summary_report()
        elif self.report_type == 'purchase':
            return self._generate_purchase_report()
        elif self.report_type == 'sales':
            return self._generate_sales_report()
        else:
            return self._generate_detailed_report()

    def _generate_summary_report(self):
        """Generate summary report"""
        return {
            'type': 'ir.actions.report',
            'report_name': 'multi_stage_approval.report_approval_summary',
            'model': 'approval.flow',
            'report_type': 'qweb-pdf',
            'context': {
                'date_from': self.date_from,
                'date_to': self.date_to,
                'include_draft': self.include_draft,
                'include_rejected': self.include_rejected,
            }
        }

    def _generate_purchase_report(self):
        """Generate purchase orders report"""
        # Build domain based on filters
        domain = [
            ('approval_history_ids.date', '>=', self.date_from),
            ('approval_history_ids.date', '<=', self.date_to)
        ]

        if not self.include_draft:
            domain.append(('approval_status', '!=', 'draft'))
        if not self.include_rejected:
            domain.append(('approval_status', '!=', 'rejected'))

        purchase_orders = self.env['purchase.order'].search(domain)

        if not purchase_orders:
            raise UserError(_("No purchase orders found matching the criteria."))

        return {
            'type': 'ir.actions.report',
            'report_name': 'purchase.report_purchaseorder',
            'docs': purchase_orders,
            'data': None,
        }

    def _generate_sales_report(self):
        """Generate sales orders report"""
        # Build domain based on filters
        domain = [
            ('approval_history_ids.date', '>=', self.date_from),
            ('approval_history_ids.date', '<=', self.date_to)
        ]

        if not self.include_draft:
            domain.append(('approval_status', '!=', 'draft'))
        if not self.include_rejected:
            domain.append(('approval_status', '!=', 'rejected'))

        sales_orders = self.env['sale.order'].search(domain)

        if not sales_orders:
            raise UserError(_("No sales orders found matching the criteria."))

        return {
            'type': 'ir.actions.report',
            'report_name': 'sale.report_saleorder',
            'docs': sales_orders,
            'data': None,
        }

    def _generate_detailed_report(self):
        """Generate detailed report"""
        raise UserError(_("Detailed report feature is under development."))