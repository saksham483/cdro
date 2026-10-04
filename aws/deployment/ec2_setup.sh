#!/usr/bin/env bash
# ==============================================================================
# CDRO - Production EC2 Deployment Script (Ubuntu 22.04 LTS / 24.04 LTS)
# ==============================================================================
set -euo pipefail

echo "=========================================================="
echo " Starting Cloud Disaster Recovery Orchestrator Deployment "
echo "=========================================================="

# 1. Update OS packages
echo "[1/7] Updating system packages..."
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y git curl apt-transport-https ca-certificates gnupg lsb-release

# 2. Install Docker and Docker Compose
echo "[2/7] Installing Docker and Docker Compose plugin..."
if ! command -v docker &> /dev/null; then
    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    sudo chmod a+r /etc/apt/keyrings/docker.gpg
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
      $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    sudo apt-get update
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    sudo usermod -aG docker "$USER"
fi

# 3. Create Project Directory
echo "[3/7] Setting up CDRO application directory..."
sudo mkdir -p /opt/cdro
sudo chown "$USER":"$USER" /opt/cdro
cd /opt/cdro

# 4. Create production .env file
echo "[4/7] Generating production environment configuration..."
cat << 'ENV_EOF' > /opt/cdro/.env
APP_ENV=production
DATABASE_URL=postgresql://cdro:cdro_secure_prod_pw@postgres:5432/cdro_db
SECRET_KEY=$(openssl rand -hex 32)
JWT_SECRET_KEY=$(openssl rand -hex 32)
INTERNAL_SECRET=$(openssl rand -hex 24)
DEMOAPP_URL=http://demoapp:5001

HEALTH_CHECK_INTERVAL_SECONDS=5
HEALTH_FAILURE_THRESHOLD=3
BACKUP_INTERVAL_SECONDS=300
BACKUP_RETENTION_COUNT=10
RECOVERY_TIMEOUT_SECONDS=120
RTO_TARGET_SECONDS=60

# S3 Mode (when IAM Role or credentials attached)
STORAGE_BACKEND=local
LOCAL_BACKUP_PATH=/app/storage/backups
S3_BUCKET=
AWS_REGION=us-east-1

# SNS Mode
NOTIFICATION_BACKEND=console
SNS_TOPIC_ARN=
ADMIN_NOTIFICATION_EMAIL=admin@company.com
RUN_BACKGROUND_WORKERS=true
ENV_EOF

# 5. Build and run containers
echo "[5/7] Launching CDRO services with Docker Compose..."
docker compose up -d --build

# 6. Verify service health
echo "[6/7] Verifying running services..."
sleep 5
docker compose ps

# 7. Summary
echo "=========================================================="
echo " CDRO Deployment Completed Successfully!                 "
echo " CDRO Console: http://$(curl -s http://checkip.amazonaws.com):5000 "
echo " DemoApp:      http://$(curl -s http://checkip.amazonaws.com):5001 "
echo " Default Admin:    admin / admin123                       "
echo " Default Operator: operator / operator123                 "
echo "=========================================================="
