from datetime import datetime, timezone
from app.config import Config

class MetricsService:
    def __init__(self):
        self.cw_client = None
        if Config.AWS_REGION:
            try:
                import boto3
                session_kwargs = {"region_name": Config.AWS_REGION}
                if Config.AWS_ACCESS_KEY_ID and Config.AWS_SECRET_ACCESS_KEY:
                    session_kwargs["aws_access_key_id"] = Config.AWS_ACCESS_KEY_ID
                    session_kwargs["aws_secret_access_key"] = Config.AWS_SECRET_ACCESS_KEY
                self.cw_client = boto3.client("cloudwatch", **session_kwargs)
            except Exception:
                self.cw_client = None

    def publish_metric(self, metric_name: str, value: float, unit: str = "Count", dimensions: list = None):
        dims = dimensions or [{"Name": "Environment", "Value": Config.APP_ENV}]
        timestamp = datetime.now(timezone.utc)
        print(f"[METRIC] {metric_name} = {value} ({unit}) at {timestamp.isoformat()}")

        if self.cw_client:
            try:
                self.cw_client.put_metric_data(
                    Namespace="CDRO/Orchestrator",
                    MetricData=[
                        {
                            "MetricName": metric_name,
                            "Dimensions": dims,
                            "Timestamp": timestamp,
                            "Value": float(value),
                            "Unit": unit
                        }
                    ]
                )
            except Exception as e:
                # Do not disrupt application if CloudWatch put fails
                print(f"[WARN] Failed to publish CloudWatch metric {metric_name}: {e}")
