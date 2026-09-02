$ErrorActionPreference = "Stop"

# Configuration
$Region = "ap-south-1"
$BucketName = "aiops-project-tf-state"
$DynamoDbTable = "aiops-project-tf-locks"

Write-Host "Creating S3 bucket $BucketName in region $Region..."
# Note: ap-south-1 requires a LocationConstraint
aws s3api create-bucket `
    --bucket $BucketName `
    --region $Region `
    --create-bucket-configuration LocationConstraint=$Region

Write-Host "Enabling versioning on S3 bucket..."
aws s3api put-bucket-versioning `
    --bucket $BucketName `
    --versioning-configuration Status=Enabled

Write-Host "Blocking public access to S3 bucket..."
aws s3api put-public-access-block `
    --bucket $BucketName `
    --public-access-block-configuration "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

Write-Host "Enabling default encryption on S3 bucket..."
aws s3api put-bucket-encryption `
    --bucket $BucketName `
    --server-side-encryption-configuration '{\"Rules\": [{\"ApplyServerSideEncryptionByDefault\": {\"SSEAlgorithm\": \"AES256\"}}]}'

Write-Host "Creating DynamoDB table $DynamoDbTable in region $Region..."
aws dynamodb create-table `
    --table-name $DynamoDbTable `
    --region $Region `
    --attribute-definitions AttributeName=LockID,AttributeType=S `
    --key-schema AttributeName=LockID,KeyType=HASH `
    --billing-mode PAY_PER_REQUEST

Write-Host "Backend resources created successfully!"
