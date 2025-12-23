from datetime import datetime, timedelta
from langchain_core.tools import tool


def _get_scan_data() -> dict:
    """Raw scan data from Azure Defender."""
    scan_timestamp = datetime.utcnow() - timedelta(hours=2)

    return {
        "scan_id": f"scan_{scan_timestamp.strftime('%Y%m%d_%H%M%S')}",
        "scan_type": "Microsoft Defender Vulnerability Management",
        "timestamp": scan_timestamp.isoformat() + "Z",
        "source": "Azure Defender for Cloud",
        "subscription_id": "00000000-1111-2222-3333-444444444444",
        "resource_group": "rg-production",
        "scan_scope": {
            "virtual_machines": 12,
            "containers": 8,
            "sql_databases": 5
        },
        "summary": {
            "total_findings": 15,
            "critical": 2,
            "high": 5,
            "medium": 6,
            "low": 2,
            "unhealthy_resources": 8
        },
        "findings": [
            {
                "id": "CVE-2024-1234",
                "type": "vulnerability",
                "severity": "Critical",
                "category": "Compute",
                "display_name": "Critical OpenSSL vulnerability in production VM",
                "description": "Vulnerable OpenSSL version 1.1.1k detected with remote code execution potential",
                "resource_name": "prod-web-vm-01",
                "resource_type": "Microsoft.Compute/virtualMachines",
                "cvss_score": 9.8,
                "remediation": "Update OpenSSL to version 3.0.2 or later",
                "impact": "Remote attackers could execute arbitrary code"
            },
            {
                "id": "CVE-2024-5678",
                "type": "vulnerability",
                "severity": "Critical",
                "category": "Container",
                "display_name": "Container image contains critical vulnerability",
                "description": "Base image ubuntu:20.04 contains critical kernel vulnerability",
                "resource_name": "api-service@sha256:abc123",
                "resource_type": "Microsoft.ContainerRegistry/repositories",
                "cvss_score": 9.1,
                "remediation": "Rebuild container using ubuntu:22.04 base image",
                "impact": "Container escape possible leading to host compromise"
            },
            {
                "id": "SQL-VA-2063",
                "type": "sql_vulnerability",
                "severity": "High",
                "category": "Data",
                "display_name": "SQL Server authentication mode set to mixed",
                "description": "SQL Server allows both Windows and SQL authentication",
                "resource_name": "customer-db",
                "resource_type": "Microsoft.Sql/servers/databases",
                "remediation": "Switch to Windows Authentication only mode",
                "impact": "Increased risk of brute force attacks"
            },
            {
                "id": "CVE-2024-9876",
                "type": "vulnerability",
                "severity": "High",
                "category": "Compute",
                "display_name": "Outdated Python packages with known vulnerabilities",
                "description": "requests 2.25.0 has SSRF vulnerability",
                "resource_name": "data-processor-vm",
                "resource_type": "Microsoft.Compute/virtualMachines",
                "cvss_score": 7.5,
                "package_name": "requests",
                "installed_version": "2.25.0",
                "fixed_version": "2.31.0",
                "remediation": "pip install --upgrade requests>=2.31.0",
                "impact": "Server-side request forgery attacks possible"
            },
            {
                "id": "AZCONFIG-001",
                "type": "misconfiguration",
                "severity": "Medium",
                "category": "Storage",
                "display_name": "Storage account allows public blob access",
                "description": "Storage account has public access enabled",
                "resource_name": "prodstorageacct",
                "resource_type": "Microsoft.Storage/storageAccounts",
                "remediation": "Disable public blob access",
                "impact": "Sensitive data could be exposed"
            },
            {
                "id": "AZCONFIG-002",
                "type": "misconfiguration",
                "severity": "Medium",
                "category": "Network",
                "display_name": "NSG allows broad RDP access",
                "description": "NSG rule allows RDP (3389) from 0.0.0.0/0",
                "resource_name": "prod-nsg",
                "resource_type": "Microsoft.Network/networkSecurityGroups",
                "remediation": "Restrict RDP to specific IPs or use Azure Bastion",
                "impact": "Increased risk of brute force RDP attacks"
            },
            {
                "id": "SQL-VA-1105",
                "type": "sql_vulnerability",
                "severity": "Low",
                "category": "Data",
                "display_name": "Database backup retention period is short",
                "description": "Backups retained for only 7 days",
                "resource_name": "analytics-db",
                "resource_type": "Microsoft.Sql/servers/databases",
                "remediation": "Increase backup retention to 35 days",
                "impact": "Limited recovery options"
            }
        ]
    }


@tool
def get_latest_scan() -> dict:
    """Get the latest security scan results from Azure Defender. Returns scan summary and all findings."""
    return _get_scan_data()


@tool
def get_findings_by_severity(severity: str) -> list:
    """Filter scan findings by severity level. Valid severities: Critical, High, Medium, Low."""
    scan = _get_scan_data()
    return [f for f in scan["findings"] if f["severity"].lower() == severity.lower()]


@tool
def get_scan_summary() -> dict:
    """Get a brief summary of the latest scan without detailed findings."""
    scan = _get_scan_data()
    return {
        "scan_id": scan["scan_id"],
        "timestamp": scan["timestamp"],
        "source": scan["source"],
        "summary": scan["summary"],
        "scan_scope": scan["scan_scope"]
    }
