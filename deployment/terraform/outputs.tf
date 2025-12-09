output "vpc_id" {
  description = "VPC ID"
  value       = aws_vpc.main.id
}

output "public_subnet_ids" {
  description = "Public subnet IDs"
  value       = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  description = "Private subnet IDs"
  value       = aws_subnet.private[*].id
}

output "rds_endpoint" {
  description = "RDS endpoint"
  value       = aws_db_instance.postgres.endpoint
}

output "rds_port" {
  description = "RDS port"
  value       = aws_db_instance.postgres.port
}

output "database_name" {
  description = "Database name"
  value       = aws_db_instance.postgres.db_name
}

output "s3_bucket_name" {
  description = "S3 bucket name for PDF storage"
  value       = aws_s3_bucket.pdfs.id
}

output "s3_bucket_arn" {
  description = "S3 bucket ARN"
  value       = aws_s3_bucket.pdfs.arn
}

output "kms_key_id" {
  description = "KMS key ID"
  value       = aws_kms_key.resume_roast_key.key_id
}

output "kms_key_arn" {
  description = "KMS key ARN"
  value       = aws_kms_key.resume_roast_key.arn
}

output "db_secret_arn" {
  description = "Database credentials secret ARN"
  value       = aws_secretsmanager_secret.db_credentials.arn
}

output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = aws_ecs_cluster.main.name
}

output "load_balancer_dns" {
  description = "Application Load Balancer DNS name"
  value       = aws_lb.main.dns_name
}

output "ecr_backend_repository_url" {
  description = "ECR backend repository URL"
  value       = aws_ecr_repository.backend.repository_url
}

output "ecr_frontend_repository_url" {
  description = "ECR frontend repository URL"
  value       = aws_ecr_repository.frontend.repository_url
}

output "application_urls" {
  description = "Application URLs"
  value = {
    backend_api = "http://${aws_lb.main.dns_name}:8000"
    frontend_ui = "http://${aws_lb.main.dns_name}"
    api_docs    = "http://${aws_lb.main.dns_name}:8000/docs"
  }
}

output "database_connection_string" {
  description = "Database connection string (sensitive)"
  value       = "postgresql+asyncpg://${aws_db_instance.postgres.username}:${random_password.db_password.result}@${aws_db_instance.postgres.endpoint}:${aws_db_instance.postgres.port}/${aws_db_instance.postgres.db_name}"
  sensitive   = true
}

output "deployment_instructions" {
  description = "Next steps for deployment"
  value = <<-EOT
    
    🚀 Resume Roast Infrastructure Deployed Successfully!
    
    Next Steps:
    1. Build and push Docker images:
       # Backend
       docker build -f server/Dockerfile -t backend .
       docker tag backend:latest ${aws_ecr_repository.backend.repository_url}:latest
       aws ecr get-login-password --region ${var.aws_region} | docker login --username AWS --password-stdin ${aws_ecr_repository.backend.repository_url}
       docker push ${aws_ecr_repository.backend.repository_url}:latest
       
       # Frontend  
       docker build -f frontend/Dockerfile -t frontend .
       docker tag frontend:latest ${aws_ecr_repository.frontend.repository_url}:latest
       docker push ${aws_ecr_repository.frontend.repository_url}:latest
    
    2. Update ECS services to use new images:
       aws ecs update-service --cluster ${aws_ecs_cluster.main.name} --service resume-roast-backend --force-new-deployment
       aws ecs update-service --cluster ${aws_ecs_cluster.main.name} --service resume-roast-frontend --force-new-deployment
    
    URLs:
    - Backend API: http://${aws_lb.main.dns_name}:8000
    - Frontend UI: http://${aws_lb.main.dns_name}
    - API Docs: http://${aws_lb.main.dns_name}:8000/docs
    
    Security:
    - Database credentials stored in AWS Secrets Manager
    - OpenAI API key stored in AWS Secrets Manager  
    - S3 bucket encrypted with KMS
    - All data encrypted at rest
    - ECS tasks run in Fargate with minimal permissions
    
  EOT
}

# Export environment variables for easy setup
output "env_vars_for_application" {
  description = "Environment variables to set in your application"
  value = {
    DATABASE_URL    = "postgresql+asyncpg://${aws_db_instance.postgres.username}:${random_password.db_password.result}@${aws_db_instance.postgres.endpoint}:${aws_db_instance.postgres.port}/${aws_db_instance.postgres.db_name}"
    AWS_REGION      = var.aws_region
    S3_BUCKET_NAME  = aws_s3_bucket.pdfs.id
    KMS_KEY_ID      = aws_kms_key.resume_roast_key.key_id
  }
  sensitive = true
}