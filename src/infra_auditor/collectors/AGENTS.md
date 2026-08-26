# Collector Instructions

Collectors collect evidence only. They must not assign severity, apply policy thresholds, mutate AWS/RDS/PostgreSQL resources, or retrieve application table rows.

Use fixed SQL resources or fixed query strings with bound parameters. Do not add generic SQL execution APIs. Collector failures should become structured collection gaps so a run can become `PARTIAL_SUCCESS` instead of hiding missing evidence.
