# ECR Repositories
resource "aws_ecr_repository" "backend" {
  name                 = "resume-roast-backend"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "KMS"
    kms_key         = aws_kms_key.resume_roast_key.arn
  }

  tags = {
    Name = "resume-roast-backend"
  }
}

resource "aws_ecr_repository" "frontend" {
  name                 = "resume-roast-frontend"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "KMS"
    kms_key         = aws_kms_key.resume_roast_key.arn
  }

  tags = {
    Name = "resume-roast-frontend"
  }
}

# CloudWatch Log Groups
resource "aws_cloudwatch_log_group" "backend" {
  name              = "/ecs/resume-roast-backend"
  retention_in_days = 7
  kms_key_id        = aws_kms_key.resume_roast_key.arn

  tags = {
    Name = "resume-roast-backend-logs"
  }
}

resource "aws_cloudwatch_log_group" "frontend" {
  name              = "/ecs/resume-roast-frontend"
  retention_in_days = 7
  kms_key_id        = aws_kms_key.resume_roast_key.arn

  tags = {
    Name = "resume-roast-frontend-logs"
  }
}

# Secrets for OpenAI API Key
resource "aws_secretsmanager_secret" "azure_openai_api_key" {
  name                    = "resume-roast/azure-openai-key"
  description             = "Azure OpenAI API key for Resume Roast"
  kms_key_id             = aws_kms_key.resume_roast_key.arn
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "azure_openai_api_key" {
  secret_id     = aws_secretsmanager_secret.azure_openai_api_key.id
  secret_string = var.azure_openai_api_key
}

# ECS Task Definition - Backend
resource "aws_ecs_task_definition" "backend" {
  family                   = "resume-roast-backend"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.backend_cpu
  memory                   = var.backend_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn           = aws_iam_role.ecs_task_role.arn

  container_definitions = jsonencode([
    {
      name      = "backend"
      image     = "${aws_ecr_repository.backend.repository_url}:latest"
      essential = true

      portMappings = [
        {
          containerPort = 8000
          protocol      = "tcp"
        }
      ]

      environment = [
        {
          name  = "ENVIRONMENT"
          value = var.environment
        },
        {
          name  = "DEBUG"
          value = var.environment == "production" ? "false" : "true"
        },
        {
          name  = "AWS_REGION"
          value = var.aws_region
        },
        {
          name  = "S3_BUCKET_NAME"
          value = aws_s3_bucket.pdfs.id
        },
        {
          name  = "KMS_KEY_ID"
          value = aws_kms_key.resume_roast_key.key_id
        },
        {
          name  = "AZURE_OPENAI_ENDPOINT"
          value = var.azure_openai_endpoint
        },
        {
          name  = "AZURE_OPENAI_API_VERSION"
          value = var.azure_openai_api_version
        },
        {
          name  = "AZURE_OPENAI_DEPLOYMENT"
          value = var.azure_openai_deployment
        },
        {
          name  = "OPENAI_MAX_TOKENS"
          value = "4000"
        },
        {
          name  = "RESUME_TOKEN_LIMIT"
          value = "15000"
        },
        {
          name  = "JOB_DESCRIPTION_TOKEN_LIMIT"
          value = "5000"
        },
        {
          name  = "DATABASE_POOL_SIZE"
          value = "10"
        },
        {
          name  = "DATABASE_ECHO"
          value = "false"
        },
        {
          name  = "CORS_ORIGINS"
          value = jsonencode(["*"])
        },
        {
          name  = "MEMORY_REFRESH_INTERVAL_HOURS"
          value = "1"
        },
        {
          name  = "AGENT_MEMORY_MAX_ENTRIES"
          value = "100"
        }
      ]

      secrets = [
        {
          name      = "DATABASE_URL"
          valueFrom = aws_secretsmanager_secret.db_credentials.arn
        },
        {
          name      = "azure_openai_api_key"
          valueFrom = aws_secretsmanager_secret.azure_openai_api_key.arn
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.backend.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }

      healthCheck = {
        command = [
          "CMD-SHELL",
          "curl -f http://localhost:8000/api/v1/health || exit 1"
        ]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 60
      }
    }
  ])

  tags = {
    Name = "resume-roast-backend-task"
  }
}

# ECS Task Definition - Frontend
resource "aws_ecs_task_definition" "frontend" {
  family                   = "resume-roast-frontend"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.frontend_cpu
  memory                   = var.frontend_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn           = aws_iam_role.ecs_task_role.arn

  container_definitions = jsonencode([
    {
      name      = "frontend"
      image     = "${aws_ecr_repository.frontend.repository_url}:latest"
      essential = true

      portMappings = [
        {
          containerPort = 8080
          protocol      = "tcp"
        }
      ]

      environment = [
        {
          name  = "API_BASE_URL"
          value = "http://${aws_lb.main.dns_name}:8000/api/v1"
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.frontend.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }
    }
  ])

  tags = {
    Name = "resume-roast-frontend-task"
  }
}

# ECS Service - Backend
resource "aws_ecs_service" "backend" {
  name            = "resume-roast-backend"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.backend.arn
  desired_count   = var.backend_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    security_groups  = [aws_security_group.ecs_tasks.id]
    subnets          = aws_subnet.public[*].id
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.backend.arn
    container_name   = "backend"
    container_port   = 8000
  }

  depends_on = [aws_lb_listener.backend]

  tags = {
    Name = "resume-roast-backend-service"
  }
}

# ECS Service - Frontend
resource "aws_ecs_service" "frontend" {
  name            = "resume-roast-frontend"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.frontend.arn
  desired_count   = var.frontend_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    security_groups  = [aws_security_group.ecs_tasks.id]
    subnets          = aws_subnet.public[*].id
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.frontend.arn
    container_name   = "frontend"
    container_port   = 8080
  }

  depends_on = [aws_lb_listener.frontend]

  tags = {
    Name = "resume-roast-frontend-service"
  }
}

# Auto Scaling for Backend
resource "aws_appautoscaling_target" "backend" {
  max_capacity       = 4
  min_capacity       = 1
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.backend.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "backend_cpu" {
  name               = "backend-cpu-autoscaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.backend.resource_id
  scalable_dimension = aws_appautoscaling_target.backend.scalable_dimension
  service_namespace  = aws_appautoscaling_target.backend.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value       = 70.0
    scale_in_cooldown  = 300
    scale_out_cooldown = 60
  }
}

# Auto Scaling for Frontend
resource "aws_appautoscaling_target" "frontend" {
  max_capacity       = 4
  min_capacity       = 1
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.frontend.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "frontend_cpu" {
  name               = "frontend-cpu-autoscaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.frontend.resource_id
  scalable_dimension = aws_appautoscaling_target.frontend.scalable_dimension
  service_namespace  = aws_appautoscaling_target.frontend.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value       = 70.0
    scale_in_cooldown  = 300
    scale_out_cooldown = 60
  }
}