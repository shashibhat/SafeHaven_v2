# Security Policy

## Reporting a Vulnerability

Please report suspected vulnerabilities privately to project maintainers. Include:
- affected component(s)
- reproduction steps
- potential impact
- suggested mitigation (if available)

Avoid public disclosure until a fix or mitigation is available.

## Secure Deployment Baseline

- Keep all services on local/private network by default
- Restrict external ingress to only required endpoints
- Protect camera credentials using secret management
- Rotate credentials regularly
- Isolate cameras and IoT devices in dedicated VLAN/network segments
- Limit relay/actuator automations with safety guards

## Data Handling

- Video and inference remain local by design
- Cloud upload is not required for core operation
- Keep backups encrypted if exporting recordings externally
