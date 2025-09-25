from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError


class TestApprovalStage(TransactionCase):

    def setUp(self):
        super(TestApprovalStage, self).setUp()
        self.ApprovalFlow = self.env['approval.flow']
        self.ApprovalStage = self.env['approval.stage']
        self.ResGroups = self.env['res.groups']

    def test_stage_creation(self):
        """Test approval stage creation with valid data"""
        group = self.ResGroups.create({'name': 'Test Approvers'})
        flow = self.ApprovalFlow.create({
            'name': 'Test Flow',
            'model': 'purchase.order'
        })
        stage = self.ApprovalStage.create({
            'name': 'First Approval',
            'sequence': 10,
            'approval_flow_id': flow.id,
            'role_id': group.id,
        })
        self.assertEqual(stage.name, 'First Approval')
        self.assertEqual(stage.approval_flow_id.id, flow.id)
        self.assertEqual(stage.sequence, 10)

    def test_stage_required_fields(self):
        """Test that required fields are enforced"""
        group = self.ResGroups.create({'name': 'Test Approvers'})
        flow = self.ApprovalFlow.create({
            'name': 'Test Flow',
            'model': 'purchase.order'
        })

        # Test missing required fields
        with self.assertRaises(Exception):
            self.ApprovalStage.create({
                'name': 'Invalid Stage',
                # Missing approval_flow_id and role_id
            })

    def test_stage_sequence_ordering(self):
        """Test stage ordering by sequence"""
        group = self.ResGroups.create({'name': 'Test Approvers'})
        flow = self.ApprovalFlow.create({
            'name': 'Test Flow',
            'model': 'purchase.order'
        })

        stage1 = self.ApprovalStage.create({
            'name': 'Stage 1',
            'sequence': 10,
            'approval_flow_id': flow.id,
            'role_id': group.id,
        })

        stage2 = self.ApprovalStage.create({
            'name': 'Stage 2',
            'sequence': 20,
            'approval_flow_id': flow.id,
            'role_id': group.id,
        })

        stages = self.ApprovalStage.search([], order='sequence')
        self.assertEqual(stages[0], stage1)
        self.assertEqual(stages[1], stage2)

    def test_amount_range_validation(self):
        """Test minimum/maximum amount validation"""
        group = self.ResGroups.create({'name': 'Test Approvers'})
        flow = self.ApprovalFlow.create({
            'name': 'Test Flow',
            'model': 'purchase.order'
        })

        # This should raise ValidationError
        with self.assertRaises(ValidationError):
            self.ApprovalStage.create({
                'name': 'Invalid Amount Range',
                'sequence': 10,
                'approval_flow_id': flow.id,
                'role_id': group.id,
                'minimum_amount': 1000,
                'maximum_amount': 500,  # Less than minimum
            })