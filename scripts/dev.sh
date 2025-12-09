#!/bin/bash

# ResumeRoast Local Development Helper
# Simplifies common development tasks

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

show_usage() {
    echo -e "${BLUE}ResumeRoast Development Helper${NC}"
    echo -e "${YELLOW}Usage: $0 [command]${NC}"
    echo ""
    echo "Commands:"
    echo "  start     Start all services (default)"
    echo "  stop      Stop all services"
    echo "  restart   Restart all services" 
    echo "  logs      Follow service logs"
    echo "  test      Run backend tests"
    echo "  migrate   Run database migrations"
    echo "  revision  Create new migration (usage: ./dev.sh revision 'message')"
    echo "  clean     Clean up containers and volumes"
    echo "  status    Show service status"
    echo "  shell     Open shell in backend container"
    echo "  build     Rebuild all images"
    echo ""
}

check_docker() {
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}❌ Docker not found. Please install Docker.${NC}"
        exit 1
    fi
    
    if ! docker compose version &> /dev/null; then
        echo -e "${RED}❌ Docker Compose not found. Please install Docker Compose.${NC}"
        exit 1
    fi
}

check_env() {
    if [ ! -f ".env" ]; then
        echo -e "${YELLOW}⚠️ .env file not found. Creating from .env.example...${NC}"
        if [ -f ".env.example" ]; then
            cp .env.example .env
            echo -e "${YELLOW}📝 Please edit .env file with your OpenAI API key before starting services.${NC}"
        else
            echo -e "${RED}❌ .env.example not found. Please create .env manually.${NC}"
            exit 1
        fi
    fi
    
    # Check if OpenAI API key is set
    if grep -q "your_openai_api_key_here" .env; then
        echo -e "${YELLOW}⚠️ Please set your OpenAI API key in .env file before starting services.${NC}"
        echo -e "${YELLOW}Edit .env and replace 'your_openai_api_key_here' with your actual API key.${NC}"
        exit 1
    fi
}

start_services() {
    echo -e "${YELLOW}🚀 Starting ResumeRoast services...${NC}"
    docker compose up --build -d
    echo -e "${GREEN}✅ Services started successfully${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}Your application is now available at:${NC}"
    echo -e "${BLUE}Frontend: http://localhost:8080${NC}"
    echo -e "${BLUE}Backend API: http://localhost:8000${NC}"
    echo -e "${BLUE}API Docs: http://localhost:8000/docs${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    echo -e "${YELLOW}Waiting for services to be ready...${NC}"
    sleep 10
    
    # Health check
    if curl -f -s "http://localhost:8000/health" > /dev/null; then
        echo -e "${GREEN}✅ Backend is healthy${NC}"
    else
        echo -e "${YELLOW}⚠️ Backend health check failed - services may still be starting${NC}"
        echo -e "${YELLOW}Run 'docker compose logs backend' to check startup logs${NC}"
    fi
}

stop_services() {
    echo -e "${YELLOW}🛑 Stopping ResumeRoast services...${NC}"
    docker compose down
    echo -e "${GREEN}✅ Services stopped${NC}"
}

restart_services() {
    echo -e "${YELLOW}🔄 Restarting ResumeRoast services...${NC}"
    docker compose restart
    echo -e "${GREEN}✅ Services restarted${NC}"
}

show_logs() {
    echo -e "${YELLOW}📋 Following service logs (Ctrl+C to exit)...${NC}"
    docker compose logs -f
}

run_tests() {
    echo -e "${YELLOW}🧪 Running backend tests...${NC}"
    docker compose exec backend pytest -v
}

clean_up() {
    echo -e "${YELLOW}🧹 Cleaning up containers and volumes...${NC}"
    docker compose down -v --remove-orphans
    docker system prune -f
    echo -e "${GREEN}✅ Cleanup complete${NC}"
}

show_status() {
    echo -e "${YELLOW}📊 Service Status:${NC}"
    docker compose ps
}

open_shell() {
    echo -e "${YELLOW}🐚 Opening shell in backend container...${NC}"
    docker compose exec backend bash
}

build_images() {
    echo -e "${YELLOW}🔨 Rebuilding all images...${NC}"
    docker compose build --no-cache
    echo -e "${GREEN}✅ Images rebuilt${NC}"
}

run_migrations() {
    echo -e "${YELLOW}🗃️ Running database migrations...${NC}"
    docker compose exec backend uv run alembic upgrade head
    echo -e "${GREEN}✅ Migrations completed${NC}"
}

create_migration() {
    local message=${1:-"New migration"}
    echo -e "${YELLOW}📝 Creating new migration: $message${NC}"
    docker compose exec backend uv run alembic revision --autogenerate -m "$message"
    echo -e "${GREEN}✅ Migration created${NC}"
}

main() {
    check_docker
    
    # Check if we're in the right directory
    if [ ! -f "docker-compose.yml" ]; then
        echo -e "${RED}❌ Please run this script from the project root directory.${NC}"
        exit 1
    fi
    
    COMMAND=${1:-start}
    
    case $COMMAND in
        start)
            check_env
            start_services
            ;;
        stop)
            stop_services
            ;;
        restart)
            restart_services
            ;;
        logs)
            show_logs
            ;;
        test)
            run_tests
            ;;
        clean)
            clean_up
            ;;
        status)
            show_status
            ;;
        shell)
            open_shell
            ;;
        build)
            build_images
            ;;
        migrate)
            run_migrations
            ;;
        revision)
            create_migration "$2"
            ;;
        help|--help|-h)
            show_usage
            ;;
        *)
            echo -e "${RED}❌ Unknown command: $COMMAND${NC}"
            show_usage
            exit 1
            ;;
    esac
}

main "$@"