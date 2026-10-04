# CDRO Security Architecture

## 1. Authentication & Role-Based Access Control (RBAC)

CDRO enforces JWT-based authentication with cryptographically signed tokens.

### Roles:
- **Admin**:
  - View dashboard, backups, recoveries, and audit logs.
  - Trigger on-demand backups.
  - Execute controlled simulation actions (failure injection, backup corruption).
  - Update system configuration.
- **Operator**:
  - View dashboard, backups, recoveries, and audit logs.
  - Read-only access to operational metrics.
  - Restricted from simulation and administrative mutations.

Passwords are salted and hashed using Werkzeug's secure PBKDF2:SHA-256 implementation.

---

## 2. Internal Microservice Protection

To protect DemoApp's internal endpoints (`/internal/failure/*`, `/internal/backup/export`, `/internal/restore`):
- All requests must include the header `X-Internal-Token` matching `INTERNAL_SECRET`.
- External unauthenticated callers receive HTTP 401 Unauthorized.
- Endpoints are isolated within Docker's internal bridge network.

---

## 3. Backup Cryptographic Integrity

Backup tampering or storage bit-rot is guarded by SHA-256 hashes:
1. When a backup is generated, its SHA-256 hash is computed and stored in the database.
2. Prior to any recovery extraction, the archive is downloaded/read and re-hashed.
3. If hashes match: archive is verified as authentic.
4. If hashes mismatch: archive is rejected as `CORRUPTED` and fallback logic engages.

---

## 4. AWS IAM Least Privilege

When running on AWS, CDRO utilizes an EC2 IAM Instance Profile with minimal required permissions:
- `s3:PutObject`, `s3:GetObject`, `s3:ListBucket`, `s3:DeleteObject` restricted to the dedicated backup bucket ARN.
- `sns:Publish` restricted to the dedicated alert topic ARN.
- `cloudwatch:PutMetricData` restricted to the `CDRO/Orchestrator` namespace.
- No static AWS keys stored in source code or production Docker images.
