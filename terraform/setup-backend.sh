#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Configuration
REGION="ap-south-1"
BUCKET_NAME="aiops-project-tf-state"
DYNAMODB_TABLE="aiops-project-tf-locks"

echo "Creating S3 bucket $BUCKET_NAME in region $REGION..."
# Note: ap-south-1 requires a LocationConstraint
aws s3api create-bucket \
    --bucket "$BUCKET_NAME" \
    --region "$REGION" \
    --create-bucket-configuration LocationConstraint="$REGION"

echo "Enabling versioning on S3 bucket..."
aws s3api put-bucket-versioning \
    --bucket "$BUCKET_NAME" \
    --versioning-configuration Status=Enabled

echo "Blocking public access to S3 bucket..."
aws s3api put-public-access-block \
    --bucket "$BUCKET_NAME" \
    --public-access-block-configuration "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

echo "Enabling default encryption on S3 bucket..."
aws s3api put-bucket-encryption \
    --bucket "$BUCKET_NAME" \
    --server-side-encryption-configuration '{"Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]}'

echo "Creating DynamoDB table $DYNAMODB_TABLE in region $REGION..."
aws dynamodb create-table \
    --table-name "$DYNAMODB_TABLE" \
    --region "$REGION" \
    --attribute-definitions AttributeName=LockID,AttributeType=S \
    --key-schema AttributeName=LockID,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST

echo "Backend resources created successfully!"
