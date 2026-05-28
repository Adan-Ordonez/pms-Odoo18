from odoo import api, fields, models


class UnifiedWorkOrders(models.Model):
    _name = "unified.work.orders"
    _description = "Unified Work Orders (Activities + Contractor Jobs)"
    _auto = False
    _order = "property_name, sequence, source"

    property_id = fields.Many2one("pms.property", readonly=True, string="Property")
    property_name = fields.Char(readonly=True, string="Property")
    project_id = fields.Many2one("pms.projects", readonly=True, string="Project")
    county = fields.Many2one("pms.county", readonly=True, string="County")
    superintendent = fields.Many2one("hr.employee", readonly=True, string="Superintendent")
    work_order_name = fields.Char(readonly=True, string="Work Order")
    vendor = fields.Many2one("res.partner", readonly=True, string="Contractor")
    status = fields.Char(readonly=True, string="Status")
    completed = fields.Boolean(readonly=True, string="Completed")
    start_date = fields.Datetime(readonly=True, string="Start Date")
    end_date = fields.Datetime(readonly=True, string="End Date")
    deadline = fields.Date(readonly=True, string="Deadline")
    source = fields.Selection([
        ('activity', 'Project Activity'),
        ('contractor_job', 'Contractor Job'),
    ], readonly=True, string="Source")
    linked = fields.Boolean(readonly=True, string="Linked")
    sequence = fields.Integer(readonly=True, string="Sequence")
    activity_id = fields.Many2one("pms.projects.routes", readonly=True, string="Activity")
    contractor_job_id = fields.Many2one("pms.contractor.job", readonly=True, string="Contractor Job")
    bill_created = fields.Boolean(readonly=True, string="Bill Created")
    on_hold = fields.Boolean(readonly=True, string="On Hold")

    @property
    def _table_query(self):
        return """
            SELECT
                pr.id AS id,
                pp.id AS property_id,
                pp.name AS property_name,
                proj.id AS project_id,
                proj.county AS county,
                proj.superintendent AS superintendent,
                COALESCE(tl.name, 'Activity') AS work_order_name,
                pr.vendor AS vendor,
                CASE
                    WHEN pr.completed THEN 'Completed'
                    WHEN pr.to_approve THEN 'To Approve'
                    ELSE 'In Progress'
                END AS status,
                pr.completed AS completed,
                pr.start_date AS start_date,
                pr.end_date AS end_date,
                pr.expected_end_date::date AS deadline,
                'activity' AS source,
                CASE WHEN EXISTS (
                    SELECT 1 FROM pms_contractor_job cj
                    WHERE cj.linked_project_activity = pr.id AND cj.state != 'cancelled'
                ) THEN TRUE ELSE FALSE END AS linked,
                COALESCE(tl.sequence, 0) AS sequence,
                pr.id AS activity_id,
                NULL::integer AS contractor_job_id,
                CASE WHEN EXISTS (
                    SELECT 1 FROM account_move am
                    WHERE am.linked_activities = pr.id AND am.move_type = 'in_invoice'
                ) THEN TRUE ELSE FALSE END AS bill_created,
                COALESCE(pp.on_hold, FALSE) AS on_hold
            FROM pms_projects_routes pr
            INNER JOIN pms_projects proj ON pr.project_property = proj.id
            INNER JOIN pms_property pp ON proj.address = pp.id
            LEFT JOIN pms_projects_routes_templates_lines tl ON pr.name = tl.id
            WHERE pr.active = TRUE

            UNION ALL

            SELECT
                cj.id * -1 AS id,
                cj.property_id AS property_id,
                pp.name AS property_name,
                proj.id AS project_id,
                proj.county AS county,
                proj.superintendent AS superintendent,
                cj.name AS work_order_name,
                cj.contractor_id AS vendor,
                CASE cj.state
                    WHEN 'created' THEN 'Created'
                    WHEN 'pending' THEN 'Pending'
                    WHEN 'ordered' THEN 'Ordered'
                    WHEN 'in_progress' THEN 'In Progress'
                    WHEN 'completed' THEN 'Completed'
                    WHEN 'cancelled' THEN 'Cancelled'
                END AS status,
                CASE WHEN cj.state = 'completed' THEN TRUE ELSE FALSE END AS completed,
                cj.creation_date AS start_date,
                cj.completed_date AS end_date,
                cj.deadline AS deadline,
                'contractor_job' AS source,
                CASE WHEN cj.linked_project_activity IS NOT NULL THEN TRUE ELSE FALSE END AS linked,
                9999 AS sequence,
                cj.linked_project_activity AS activity_id,
                cj.id AS contractor_job_id,
                COALESCE(cj.bill_created, FALSE) AS bill_created,
                COALESCE(pp.on_hold, FALSE) AS on_hold
            FROM pms_contractor_job cj
            INNER JOIN pms_property pp ON cj.property_id = pp.id
            LEFT JOIN pms_projects proj ON proj.address = pp.id
            WHERE cj.active = TRUE
                AND cj.linked_project_activity IS NULL
        """

    def action_open_record(self):
        self.ensure_one()
        if self.source == 'activity' and self.activity_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'pms.projects.routes',
                'res_id': self.activity_id.id,
                'view_mode': 'form',
                'target': 'current',
            }
        elif self.source == 'contractor_job' and self.contractor_job_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'pms.contractor.job',
                'res_id': self.contractor_job_id.id,
                'view_mode': 'form',
                'target': 'current',
            }
