# Multi-Stage Approval System - User Guide

## Overview

The Multi-Stage Approval System provides a flexible workflow for approving Purchase and Sales orders with multiple approval levels, amount-based routing, and comprehensive tracking.

## Quick Start

### For Requesters
1. **Create Order**: Create a Purchase or Sales order as usual
2. **Request Approval**: Click "Request Approval" button
3. **Track Progress**: Monitor approval status in the Approval Status section
4. **Receive Notification**: Get notified when fully approved or rejected

### For Approvers
1. **Review Requests**: Check "Approval Dashboards" for pending approvals
2. **Approve/Reject**: Use Approve/Reject buttons on orders
3. **Add Notes**: Provide comments for approval decisions
4. **Multi-Stage**: Approve your stage, system moves to next automatically

## Detailed Workflows

### Purchase Order Approval

#### Single Stage Approval:
Create PO → Request Approval → Manager Approves → Order Confirmed


#### Multi-Stage Approval:
Create PO → Request Approval → Manager Approves → Director Approves → Order Confirmed

#### Amount-Based Routing
- **< $5,000**: Manager approval only
- **> $5,000**: Manager → Director approval

### Sales Order Approval:
Create SO → Request Approval → Sales Manager Approves → Order Confirmed


## Key Features

### Approval Status Tracking
- **Draft**: Order created, approval not requested
- **Waiting**: Approval requested, pending action
- **Approved**: Fully approved, ready for confirmation
- **Rejected**: Approval denied, requires revision

### Approval History
- Complete audit trail of all approval actions
- User, date, stage, and notes for each action
- Accessible via "Approval History" tab

### Notifications
- **Email**: Detailed approval requests and status updates
- **Chatter**: Internal messages on order documents
- **Activities**: Task assignments for approvers

### Dashboards
- **Purchase Approvals**: All purchase orders needing approval
- **Sales Approvals**: All sales orders needing approval
- **Kanban View**: Visual workflow management

## Configuration Guide

### Setting Up Approval Flows

1. **Navigate to**: Approvals → Configuration → Approval Flows
2. **Create Flow**:
   - Name: "High Value Purchase Approval"
   - Model: Purchase Order
   - Company: Select appropriate company

3. **Add Stages**:
   - Stage 1: Manager Review (Sequence: 10)
   - Stage 2: Director Approval (Sequence: 20, Final Approval: Yes)

### Configuring Approval Stages

For each stage:
- **Name**: Descriptive stage name
- **Approver Group**: User group that can approve this stage
- **Amount Range**: Minimum/maximum amounts for this stage
- **Approval Type**: Mandatory/Optional/Parallel
- **Final Approval**: Mark if this is the final approval stage

### System Settings

Access via: Settings → General Settings → Approval Configuration
- **Auto Confirm**: Automatically confirm orders after final approval
- **Notification Method**: Email, Chat, or Both
- **Escalation Days**: Days before escalating pending approvals

## Best Practices

### For Requesters
- Provide clear descriptions in order notes
- Attach supporting documents when needed
- Follow up on pending approvals appropriately
- Review rejection reasons before resubmitting

### For Approvers
- Review orders promptly to avoid delays
- Provide constructive feedback when rejecting
- Use notes to explain approval decisions
- Escalate issues that require higher authority

### For Administrators
- Regularly review approval process effectiveness
- Monitor for bottlenecks in approval workflow
- Train new users on approval procedures
- Update approval flows as business needs change

## Troubleshooting

### Common Questions

**Q: Why can't I see the approval buttons?**
A: Check that:
- You are in the correct user group
- An approval flow is configured for this order type
- The order is in draft status

**Q: Why was my order rejected?**
A: Check the approval history for rejection reasons and notes from approvers.

**Q: How long does approval take?**
A: Approval times vary. Use the escalation feature if approvals are delayed beyond configured thresholds.

**Q: Can I recall an approval request?**
A: Once submitted, approval requests cannot be recalled. Contact approvers directly if needed.

### Getting Help

- **System Issues**: Contact IT Support
- **Process Questions**: Contact your manager
- **Configuration Changes**: Contact System Administrator

## Advanced Features

### Parallel Approvals
Configure stages for multiple simultaneous approvers where any approval progresses the workflow.

### Conditional Routing
Set up complex approval paths based on order amount, product categories, or other criteria.

### Custom Notifications
Create specialized email templates for different approval scenarios.

### API Integration
Extend approval workflows through Odoo's API for custom integrations.