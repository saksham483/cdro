from datetime import datetime, timezone
from app.config import Config
from app.extensions import db
from app.models.notification import Notification
from app.models.audit_log import AuditLog

class NotificationService:
    @staticmethod
    def send_notification(subject: str, message: str, severity: str = "INFO", app_id: int = None) -> Notification:
        timestamp = datetime.now(timezone.utc)
        channel = "CONSOLE/DATABASE"
        status = "SENT"

        # Check for AWS SNS
        if Config.NOTIFICATION_BACKEND.lower() == "sns" and Config.SNS_TOPIC_ARN:
            try:
                import boto3
                session_kwargs = {}
                if Config.AWS_ACCESS_KEY_ID and Config.AWS_SECRET_ACCESS_KEY:
                    session_kwargs["aws_access_key_id"] = Config.AWS_ACCESS_KEY_ID
                    session_kwargs["aws_secret_access_key"] = Config.AWS_SECRET_ACCESS_KEY
                if Config.AWS_REGION:
                    session_kwargs["region_name"] = Config.AWS_REGION
                sns_client = boto3.client("sns", **session_kwargs)
                sns_client.publish(
                    TopicArn=Config.SNS_TOPIC_ARN,
                    Subject=f"[CDRO {severity}] {subject}",
                    Message=message
                )
                channel = "AWS_SNS"
            except Exception as e:
                print(f"[WARN] AWS SNS notification delivery failed: {e}. Logged locally.")
                channel = "CONSOLE/DATABASE (SNS_FAILED)"

        # Console log with high visibility
        border = "=" * 65
        print(f"\n{border}\n[CDRO NOTIFICATION - {severity}]\nSubject: {subject}\nTimestamp: {timestamp.isoformat()}\nChannel: {channel}\nMessage: {message}\n{border}\n")

        # Database record
        notification = Notification(
            timestamp=timestamp,
            channel=channel,
            recipient=Config.ADMIN_NOTIFICATION_EMAIL,
            subject=subject,
            message=message,
            status=status,
            sent_at=timestamp
        )
        db.session.add(notification)

        # Audit log entry
        audit = AuditLog(
            timestamp=timestamp,
            application_id=app_id,
            event_type="NOTIFICATION_SENT",
            severity=severity,
            message=f"Notification dispatched via {channel}: {subject}",
            metadata_json=None
        )
        db.session.add(audit)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

        return notification
