# Compute Resource Orchestration System Specifications

## Overview
This system provides a web application for managing and orchestrating compute resources, specifically focusing on GPU resource allocation, reservations, and job queuing in a cluster environment. The application allows users to view cluster status, reserve GPUs, and manage their reservations.

## Architecture

### Components
1. **Backend API (FastAPI)**
   - Provides REST endpoints for cluster management
   - Handles business logic for resource allocation and reservation
   - Connects to SQLite database for persistence

2. **Frontend (Vue.js)**
   - Single-page application for user interaction
   - Communicates with backend API
   - Provides intuitive UI for cluster management

3. **Database (SQLite)**
   - Stores reservation information
   - Tracks user allocation history
   - Maintains cluster state

4. **Container Environment (Docker)**
   - Simulates a cluster environment
   - Provides isolated, reproducible deployment
   - Orchestrates services via Docker Compose

## Functional Requirements

### Cluster Status
- View current status of all GPUs in the cluster
- See which GPUs are reserved and available
- Monitor resource utilization metrics

### Reservation Management
- Find best available GPU based on resource requirements
- Reserve GPUs for specific durations
- Cancel existing reservations
- View active reservations

### Job Queue
- Submit jobs to be executed when resources are available
- Monitor job status in queue
- Set job priorities and resource requirements

### Future Authentication Features
- User registration and authentication
- Role-based access control
- Resource quotas per user/group

## API Endpoints

### GET /status
Returns the current status of all GPUs in the cluster.

### POST /reserve
Reserve a GPU for a specified duration.
- Parameters: `user` (string), `duration_hours` (integer)
- Returns reservation ID and GPU ID

### POST /cancel/{reservation_id}
Cancel an existing reservation.
- Parameters: `reservation_id` (integer)

### GET /reservations
Get all active reservations, optionally filtered by user.
- Optional parameters: `user` (string)

### POST /reset
Reset the cluster state and clear all reservations.

### GET /find_best
Find the best available GPU without reserving it.

## Docker Environment

- Backend service: FastAPI running on port 8000
- Frontend service: Vue.js running on port 8080
- Development mode with hot-reloading for both services

## Technology Stack

- Backend: Python 3.10+, FastAPI, Uvicorn, SQLite
- Frontend: Vue.js 3, Vue Router, Axios
- Containerization: Docker, Docker Compose
- Development: Node.js, npm

## Roadmap

1. Basic functionality: GPU reservations and monitoring
2. Advanced job queueing with priorities
3. User authentication and authorization
4. Resource usage analytics and reporting
5. Enhanced scheduling algorithms