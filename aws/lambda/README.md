# CDRO AWS Lambda Scheduled Backup Trigger

This serverless function runs on AWS Lambda to trigger periodic backups of CDRO-managed applications without relying solely on local cron daemons.

## Architecture

```
Amazon EventBridge (Cron: rate(1 hour))
         ↓
AWS Lambda Function (backup_trigger.py)
         ↓ HTTP POST /api/backups/trigger
CDRO Backend Orchestrator (EC2 / ECS)
         ↓
S3 Bucket Backup Archive Created
```

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `CDRO_API_URL` | Base URL of CDRO Backend | `http://cdro-backend.internal:5000` |
| `ADMIN_USERNAME` | Admin account for API token | `admin` |
| `ADMIN_PASSWORD` | Admin password | `admin123` |
| `APPLICATION_ID` | Application to back up | `1` |

## Deployment with AWS CLI

```bash
# Package function
zip function.zip backup_trigger.py

# Create Lambda function
aws lambda create-function \
    --function-name CDRO-ScheduledBackupTrigger \
    --runtime python3.12 \
    --handler backup_trigger.lambda_handler \
    --role arn:aws:iam::123456789012:role/CDROLambdaExecutionRole \
    --zip-file fileb://function.zip \
    --environment "Variables={CDRO_API_URL=http://your-ec2-ip:5000,ADMIN_USERNAME=admin,ADMIN_PASSWORD=your_secure_password,APPLICATION_ID=1}"

# Add EventBridge rule for every 1 hour trigger
aws events put-rule \
    --name CDRO-HourlyBackupSchedule \
    --schedule-expression "rate(1 hour)"

# Add target
aws events put-targets \
    --rule CDRO-HourlyBackupSchedule \
    --targets "Id"="1","Arn"="arn:aws:lambda:us-east-1:123456789012:function:CDRO-ScheduledBackupTrigger"
```
