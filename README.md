# Compute Resource Orchestration

A web application for managing and orchestrating compute resources, specifically GPU allocations, in a cluster environment.

## Features

- View cluster status and GPU information
- Reserve GPUs for specific durations
- Cancel existing reservations
- View all active reservations
- Reset the cluster state (admin function)

## Architecture

- **Backend**: FastAPI REST API (Python)
- **Frontend**: Vue.js single-page application
- **Database**: SQLite for persistence
- **Deployment**: Docker containers orchestrated with Docker Compose

## Getting Started

### Prerequisites

- Docker and Docker Compose installed
- Git (optional, for cloning the repository)

### Development Setup

1. Clone or download this repository
2. Start the development environment:

```bash
docker-compose -f docker-compose.dev.yml up
```

This will:
- Start the FastAPI backend with hot-reloading on port 8000
- Start the Vue.js development server with hot-reloading on port 8080

### Production Setup

```bash
docker-compose up -d
```

This will:
- Start the FastAPI backend on port 8000
- Start the Vue.js frontend (served via Nginx) on port 8080

## API Documentation

When the application is running, you can access the API documentation at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Project Structure

```
├── app.py                 # FastAPI backend entry point
├── cluster.py             # Cluster management logic
├── db.py                  # Database operations
├── Dockerfile             # Backend Dockerfile
├── requirements.txt       # Python dependencies
├── specifications.md      # Detailed specifications
├── docker-compose.yml     # Production Docker Compose
├── docker-compose.dev.yml # Development Docker Compose
└── frontend/              # Vue.js frontend
    ├── Dockerfile         # Frontend production Dockerfile
    ├── Dockerfile.dev     # Frontend development Dockerfile
    └── src/               # Vue source code
```

## Future Plans

- User authentication and authorization
- Advanced job queuing with priorities
- Resource usage analytics and reporting

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Author

- **Timo Leitritz**, 2024

## AI Assistance

Development of this project was supported by OpenAI's ChatGPT models (o1, December 2024 Version), which provided code suggestions and troubleshooting help.