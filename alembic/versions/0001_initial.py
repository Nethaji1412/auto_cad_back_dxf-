"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-08

"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

project_status_enum = sa.Enum(
    "DRAFT", "INPUTS_READY", "CALCULATING", "GENERATING", "COMPLETED", "FAILED", name="projectstatus"
)
job_status_enum = sa.Enum("QUEUED", "RUNNING", "COMPLETED", "FAILED", name="jobstatus")
file_type_enum = sa.Enum(
    "BOUNDARY", "CONTROL_ROOM", "INVERTER_ROOM", "PRIVATE_AREA", "DXF", "DWG", name="filetype"
)
audit_action_enum = sa.Enum(
    "PROJECT_CREATED",
    "FILE_UPLOADED",
    "INPUT_UPDATED",
    "CALCULATION_STARTED",
    "CALCULATION_COMPLETED",
    "LAYOUT_GENERATION_STARTED",
    "LAYOUT_GENERATION_COMPLETED",
    "LAYOUT_GENERATION_FAILED",
    "FILE_DOWNLOADED",
    name="auditaction",
)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("is_admin", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "projects",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("uuid", sa.String(36), nullable=False, unique=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("status", project_status_enum, nullable=False, server_default="DRAFT"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_projects_uuid", "projects", ["uuid"], unique=True)

    op.create_table(
        "project_inputs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "project_id", sa.Integer, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, unique=True
        ),
        sa.Column("module_config", sa.JSON, nullable=False),
        sa.Column("table_config", sa.JSON, nullable=False),
        sa.Column("layout_config", sa.JSON, nullable=False),
        sa.Column("electrical_config", sa.JSON, nullable=False),
        sa.Column("service_road_config", sa.JSON, nullable=False),
        sa.Column("dxf_config", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "project_files",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("uuid", sa.String(36), nullable=False, unique=True),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_type", file_type_enum, nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("stored_filename", sa.String(255), nullable=False),
        sa.Column("storage_path", sa.String(1024), nullable=False),
        sa.Column("mime_type", sa.String(127), nullable=False),
        sa.Column("file_size", sa.Integer, nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_project_files_uuid", "project_files", ["uuid"], unique=True)

    op.create_table(
        "calculation_results",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("theoretical_result", sa.JSON, nullable=True),
        sa.Column("actual_result", sa.JSON, nullable=True),
        sa.Column("grouping_result", sa.JSON, nullable=True),
        sa.Column("capacity_result", sa.JSON, nullable=True),
        sa.Column("warnings", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("uuid", sa.String(36), nullable=False, unique=True),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", job_status_enum, nullable=False, server_default="QUEUED"),
        sa.Column("progress", sa.Integer, nullable=False, server_default="0"),
        sa.Column("result", sa.JSON, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_jobs_uuid", "jobs", ["uuid"], unique=True)

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("job_id", sa.Integer, sa.ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", audit_action_enum, nullable=False),
        sa.Column("details", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("jobs")
    op.drop_table("calculation_results")
    op.drop_table("project_files")
    op.drop_table("project_inputs")
    op.drop_table("projects")
    op.drop_table("users")
    job_status_enum.drop(op.get_bind(), checkfirst=True)
    project_status_enum.drop(op.get_bind(), checkfirst=True)
    file_type_enum.drop(op.get_bind(), checkfirst=True)
    audit_action_enum.drop(op.get_bind(), checkfirst=True)
