import os
import shutil
from datetime import datetime, timezone
from app.config import Config

class StorageService:
    def __init__(self):
        self.backend = Config.STORAGE_BACKEND.lower()
        self.local_root = os.path.abspath(Config.LOCAL_BACKUP_PATH)
        os.makedirs(self.local_root, exist_ok=True)
        self.s3_client = None
        if self.backend == "s3" and Config.S3_BUCKET:
            try:
                import boto3
                session_kwargs = {}
                if Config.AWS_ACCESS_KEY_ID and Config.AWS_SECRET_ACCESS_KEY:
                    session_kwargs["aws_access_key_id"] = Config.AWS_ACCESS_KEY_ID
                    session_kwargs["aws_secret_access_key"] = Config.AWS_SECRET_ACCESS_KEY
                if Config.AWS_REGION:
                    session_kwargs["region_name"] = Config.AWS_REGION
                self.s3_client = boto3.client("s3", **session_kwargs)
            except Exception as e:
                print(f"[WARN] Failed to initialize S3 client: {e}. Falling back to local storage.")
                self.backend = "local"

    def get_hierarchical_path(self, app_name: str, filename: str, dt: datetime = None) -> str:
        if not dt:
            dt = datetime.now(timezone.utc)
        safe_app = app_name.lower().replace(" ", "_")
        return f"applications/{safe_app}/{dt.strftime('%Y')}/{dt.strftime('%m')}/{dt.strftime('%d')}/{filename}"

    def save_file(self, source_path: str, relative_key: str) -> tuple[str, str]:
        """
        Saves a local file into the designated storage backend.
        Returns: (storage_type, storage_path)
        """
        if self.backend == "s3" and self.s3_client and Config.S3_BUCKET:
            try:
                s3_key = relative_key
                self.s3_client.upload_file(source_path, Config.S3_BUCKET, s3_key)
                return "s3", f"s3://{Config.S3_BUCKET}/{s3_key}"
            except Exception as e:
                print(f"[ERROR] S3 upload failed ({e}). Falling back to local storage.")

        # Local storage fallback
        dest_path = os.path.join(self.local_root, relative_key)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        shutil.copy2(source_path, dest_path)
        return "local", dest_path

    def retrieve_file(self, storage_type: str, storage_path: str, target_dest_path: str) -> bool:
        """
        Retrieves a file from storage and saves it to target_dest_path.
        """
        os.makedirs(os.path.dirname(target_dest_path), exist_ok=True)
        if storage_type == "s3" and self.s3_client and Config.S3_BUCKET:
            try:
                s3_key = storage_path.replace(f"s3://{Config.S3_BUCKET}/", "")
                self.s3_client.download_file(Config.S3_BUCKET, s3_key, target_dest_path)
                return True
            except Exception as e:
                print(f"[ERROR] S3 download failed: {e}")
                return False

        # Local file
        if os.path.exists(storage_path):
            shutil.copy2(storage_path, target_dest_path)
            return True
        return False

    def delete_file(self, storage_type: str, storage_path: str) -> bool:
        if storage_type == "s3" and self.s3_client and Config.S3_BUCKET:
            try:
                s3_key = storage_path.replace(f"s3://{Config.S3_BUCKET}/", "")
                self.s3_client.delete_object(Bucket=Config.S3_BUCKET, Key=s3_key)
                return True
            except Exception as e:
                print(f"[ERROR] S3 delete failed: {e}")
                return False

        if os.path.exists(storage_path):
            try:
                os.remove(storage_path)
                return True
            except OSError:
                return False
        return False

    def file_exists(self, storage_type: str, storage_path: str) -> bool:
        if storage_type == "s3" and self.s3_client and Config.S3_BUCKET:
            try:
                s3_key = storage_path.replace(f"s3://{Config.S3_BUCKET}/", "")
                self.s3_client.head_object(Bucket=Config.S3_BUCKET, Key=s3_key)
                return True
            except Exception:
                return False
        return os.path.exists(storage_path)
