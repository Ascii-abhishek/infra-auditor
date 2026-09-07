# Changelog

## Unreleased

- Replaced transitional full-snapshot plus split-artifact S3 writes with
  canonical schema-2 service/subservice artifacts and completion manifests.
- Reworked UI reports, sync completeness, and MCP reads around canonical
  artifacts; removed schema-1 compatibility paths and composite `rds-postgres`
  report parameters before alpha.
- Added AWS security group ingress, CloudWatch RDS metric summary, RDS operations,
  and PostgreSQL activity-summary collectors.
- Added deterministic findings for public RDS exposure, pending maintenance,
  open RDS recommendations, parameter apply status, resource pressure, and
  connection hygiene.
- Added snapshot/fleet report models, service-aware S3 snapshot reads, a local
  FastAPI report console, JSON/Markdown exports, and a root `run.sh`.
- Reworked the report console into service-section navigation with right-pane
  controls and an inert Chat placeholder for the future MCP/LLM layer.
- Added sidebar collapse, persistent light/dark mode, Bootstrap 5.3.8/Icons
  1.13.1, and async `/view` loading behind a central loader.

## 0.1.0 - 2026-08-26

- Bootstrapped the deterministic V1 repository foundation.
- Added validated runtime/resource configuration, structured logging, read-only AWS RDS discovery, Secrets Manager credential boundary, safe PostgreSQL database inventory, PostgreSQL role-security findings, and S3 JSON snapshot writing.
- Added the initial project memory documents, decision log, runbooks, and safety boundaries.
