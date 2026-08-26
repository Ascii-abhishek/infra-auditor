"""Project-specific exception categories."""


class InfraAuditorError(Exception):
    """Base class for expected infra-auditor errors."""


class ConfigurationError(InfraAuditorError):
    """Raised when local settings or resource configuration are invalid."""


class AWSDiscoveryError(InfraAuditorError):
    """Raised when AWS resource discovery cannot complete."""


class SecretResolutionError(InfraAuditorError):
    """Raised when a required secret cannot be read or validated."""


class DatabaseConnectionError(InfraAuditorError):
    """Raised when a PostgreSQL connection cannot be established safely."""


class CollectorQueryError(InfraAuditorError):
    """Raised when a deterministic collector query fails."""


class SnapshotValidationError(InfraAuditorError):
    """Raised when a snapshot cannot be validated or persisted."""
