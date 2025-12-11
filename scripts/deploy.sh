#!/bin/bash

# ResumeRoast Deployment Script
# Automates the build and deployment process for AWS ECS Fargate

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Starting ResumeRoast Deployment${NC}"

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

if ! command -v aws &> /dev/null; then
    echo -e "${RED}❌ AWS CLI not found. Please install AWS CLI and configure credentials.${NC}"
    exit 1
fi

if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker not found. Please install Docker.${NC}"
    exit 1
fi

if ! command -v terraform &> /dev/null; then
    echo -e "${RED}❌ Terraform not found. Please install Terraform.${NC}"
    exit 1
fi

# Check if we're in the right directory
if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}❌ Please run this script from the project root directory.${NC}"
    exit 1
fi

# Get Azure OpenAI API key if not provided
if [ -z "$AZURE_OPENAI_API_KEY" ]; then
    echo -e "${YELLOW}Please enter your Azure OpenAI API key:${NC}"
    read -s AZURE_OPENAI_API_KEY
    export AZURE_OPENAI_API_KEY
fi

echo -e "${GREEN}✅ Prerequisites check passed${NC}"

# Deploy infrastructure
echo -e "${YELLOW}Deploying infrastructure with Terraform...${NC}"
cd deployment/terraform

terraform init
terraform plan -var="azure_openai_api_key=$AZURE_OPENAI_API_KEY"

echo -e "${YELLOW}Apply infrastructure changes? (y/N)${NC}"
read -r CONFIRM
if [[ $CONFIRM =~ ^[Yy]$ ]]; then
    terraform apply -var="azure_openai_api_key=$AZURE_OPENAI_API_KEY" -auto-approve
else
    echo -e "${RED}❌ Deployment cancelled${NC}"
    exit 1
fi

# Get Terraform outputs
BACKEND_ECR=$(terraform output -raw backend_ecr_repository_url)
FRONTEND_ECR=$(terraform output -raw frontend_ecr_repository_url)
AWS_REGION=$(terraform output -raw aws_region)
CLUSTER_NAME=$(terraform output -raw cluster_name)

echo -e "${GREEN}✅ Infrastructure deployed successfully${NC}"
echo -e "${BLUE}Backend ECR: $BACKEND_ECR${NC}"
echo -e "${BLUE}Frontend ECR: $FRONTEND_ECR${NC}"

cd ../..

# Login to ECR
echo -e "${YELLOW}Logging in to ECR...${NC}"
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $BACKEND_ECR

# Build and push backend
echo -e "${YELLOW}Building and pushing backend image...${NC}"
docker build -f server/Dockerfile -t backend .
docker tag backend:latest $BACKEND_ECR:latest
docker push $BACKEND_ECR:latest

echo -e "${GREEN}✅ Backend image pushed successfully${NC}"

# Build and push frontend
echo -e "${YELLOW}Building and pushing frontend image...${NC}"
docker build -f frontend/Dockerfile -t frontend .
docker tag frontend:latest $FRONTEND_ECR:latest
docker push $FRONTEND_ECR:latest

echo -e "${GREEN}✅ Frontend image pushed successfully${NC}"

# Deploy to ECS
echo -e "${YELLOW}Updating ECS services...${NC}"
aws ecs update-service --cluster $CLUSTER_NAME --service resume-roast-backend --force-new-deployment > /dev/null
aws ecs update-service --cluster $CLUSTER_NAME --service resume-roast-frontend --force-new-deployment > /dev/null

echo -e "${GREEN}✅ ECS services updated${NC}"

# Wait for services to stabilize
echo -e "${YELLOW}Waiting for services to stabilize (this may take a few minutes)...${NC}"
aws ecs wait services-stable --cluster $CLUSTER_NAME --services resume-roast-backend
aws ecs wait services-stable --cluster $CLUSTER_NAME --services resume-roast-frontend

# Get load balancer DNS
cd deployment/terraform
LB_DNS=$(terraform output -raw load_balancer_dns_name)
cd ../..

echo -e "${GREEN}🎉 Deployment completed successfully!${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}Your application is now available at:${NC}"
echo -e "${BLUE}Frontend: http://$LB_DNS${NC}"
echo -e "${BLUE}Backend API: http://$LB_DNS:8000${NC}"
echo -e "${BLUE}API Docs: http://$LB_DNS:8000/docs${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Health check
echo -e "${YELLOW}Performing health check...${NC}"
sleep 30  # Wait a bit for services to start

if curl -f -s "http://$LB_DNS:8000/health" > /dev/null; then
    echo -e "${GREEN}✅ Backend health check passed${NC}"
else
    echo -e "${YELLOW}⚠️ Backend health check failed - services may still be starting${NC}"
fi

echo -e "${GREEN}🚀 ResumeRoast deployment complete!${NC}"