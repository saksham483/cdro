"""
AWS Lambda Function: Scheduled Backup Orchestration for CDRO
Triggered periodically by Amazon EventBridge (e.g. cron schedule rate(1 hour)).
Invokes CDRO Backend API to create an application backup, verifies the backup,
and reports status to CloudWatch.
"""
import json
import urllib.request
import urllib.error
import os

CDRO_API_URL = os.environ.get("CDRO_API_URL", "http://cdro-backend.internal:5000")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
APPLICATION_ID = int(os.environ.get("APPLICATION_ID", 1))

def lambda_handler(event, context):
    print(f"Starting scheduled backup trigger for Application ID {APPLICATION_ID}...")

    # 1. Authenticate to CDRO API
    login_url = f"{CDRO_API_URL}/api/auth/login"
    login_payload = json.dumps({"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}).encode("utf-8")

    req = urllib.request.Request(
        login_url,
        data=login_payload,
        headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            login_data = json.loads(response.read().decode("utf-8"))
            token = login_data.get("access_token")
            if not token:
                raise RuntimeError("Authentication failed: No token received")
    except Exception as e:
        print(f"Failed to authenticate with CDRO Backend: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "AUTH_FAILED", "detail": str(e)})
        }

    # 2. Trigger Backup
    backup_url = f"{CDRO_API_URL}/api/backups/trigger"
    backup_payload = json.dumps({"application_id": APPLICATION_ID}).encode("utf-8")

    req_backup = urllib.request.Request(
        backup_url,
        data=backup_payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }
    )

    try:
        with urllib.request.urlopen(req_backup, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
            backup = result.get("backup", {})
            print(f"Backup successfully created: {backup.get('filename')} (SHA-256: {backup.get('checksum')})")
            return {
                "statusCode": 200,
                "body": json.dumps({
                    "status": "success",
                    "backup_id": backup.get("id"),
                    "filename": backup.get("filename"),
                    "checksum": backup.get("checksum"),
                    "storage_path": backup.get("storage_path")
                })
            }
    except Exception as e:
        print(f"Backup invocation failed: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "BACKUP_TRIGGER_FAILED", "detail": str(e)})
        }
