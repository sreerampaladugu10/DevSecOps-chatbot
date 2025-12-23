SECURITY_POLICIES = [
    {
        "id": "pol-001",
        "title": "Security Patch Management",
        "content": "All production servers must have automatic security patches enabled. Critical patches must be applied within 24 hours of release. High severity patches within 72 hours.",
        "metadata": {"category": "patching", "severity": "critical"}
    },
    {
        "id": "pol-002",
        "title": "Multi-Factor Authentication",
        "content": "Multi-factor authentication (MFA) is required for all user accounts accessing production systems. SMS-based MFA is not acceptable; use TOTP or hardware keys.",
        "metadata": {"category": "authentication", "severity": "critical"}
    },
    {
        "id": "pol-003",
        "title": "API Rate Limiting",
        "content": "All API endpoints must implement rate limiting. Default limits: 100 requests per minute for authenticated users, 20 requests per minute for unauthenticated.",
        "metadata": {"category": "api-security", "severity": "high"}
    },
    {
        "id": "pol-004",
        "title": "Secrets Management",
        "content": "Secrets and credentials must never be committed to version control. Use environment variables or secret management services like HashiCorp Vault.",
        "metadata": {"category": "secrets-management", "severity": "critical"}
    },
    {
        "id": "pol-005",
        "title": "Container Image Scanning",
        "content": "All container images must be scanned for vulnerabilities before deployment. Images with critical CVEs are blocked from production.",
        "metadata": {"category": "container-security", "severity": "critical"}
    },
    {
        "id": "pol-006",
        "title": "Database Encryption",
        "content": "Database connections must use TLS encryption. Plain text database connections are prohibited in all environments.",
        "metadata": {"category": "data-security", "severity": "high"}
    },
    {
        "id": "pol-007",
        "title": "Logging and Retention",
        "content": "All logs must be centralized and retained for minimum 90 days. Sensitive data like passwords and PII must be masked in logs.",
        "metadata": {"category": "logging", "severity": "medium"}
    },
    {
        "id": "pol-008",
        "title": "Network Segmentation",
        "content": "Network segmentation is required between development, staging, and production environments. No direct access between environments allowed.",
        "metadata": {"category": "network-security", "severity": "high"}
    },
    {
        "id": "pol-009",
        "title": "SQL Injection Prevention",
        "content": "SQL injection prevention: Use parameterized queries or ORM. Raw SQL string concatenation is strictly prohibited.",
        "metadata": {"category": "application-security", "severity": "critical"}
    },
    {
        "id": "pol-010",
        "title": "Incident Response",
        "content": "Incident response: Security incidents must be reported within 1 hour of detection. P1 incidents require immediate escalation to security team.",
        "metadata": {"category": "incident-response", "severity": "critical"}
    }
]
