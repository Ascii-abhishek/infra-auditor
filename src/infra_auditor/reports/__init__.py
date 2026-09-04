"""Report builders for audit snapshots."""

from infra_auditor.reports.builder import (
    build_fleet_report,
    build_instance_report,
    build_snapshot_report,
)
from infra_auditor.reports.markdown import render_fleet_markdown, render_snapshot_markdown
from infra_auditor.reports.models import FleetReport, InstanceReport, SnapshotReport

__all__ = [
    "FleetReport",
    "InstanceReport",
    "SnapshotReport",
    "build_fleet_report",
    "build_instance_report",
    "build_snapshot_report",
    "render_fleet_markdown",
    "render_snapshot_markdown",
]
