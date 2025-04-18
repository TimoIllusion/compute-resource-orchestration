# Compute Resource Orchestration System Specifications

## Overview
This system provides a web application for managing and orchestrating compute resources, specifically focusing on GPU resource allocation, reservations, and job queuing in a cluster environment. The application allows users to view cluster status, reserve GPUs, and manage their reservations.

## Architecture

### Components
1. **Backend API (FastAPI)**
   - Provides REST endpoints for cluster management
   - Handles business logic for resource allocation and reservation
   - Connects to SQLite database for persistence
   - Monitors and reports real GPU utilization metrics

2. **Frontend (Vue.js)**
   - Single-page application for user interaction
   - Communicates with backend API
   - Provides intuitive UI for cluster management
   - Real-time visualization of GPU metrics and utilization

3. **Database (SQLite)**
   - Stores reservation information
   - Tracks user allocation history
   - Maintains cluster state

4. **Container Environment (Docker)**
   - Simulates a cluster environment with actual GPU access
   - Provides isolated, reproducible deployment
   - Orchestrates services via Docker Compose
   - Passes through host GPU devices to containers

5. **GPU Worker Processes**
   - Simulates realistic GPU workloads using PyTorch
   - Demonstrates variable memory usage and computation patterns
   - Provides metrics for monitoring and visualization
   - Can be started/stopped to test scheduling and allocation

## Functional Requirements

### Cluster Status
- View current status of all GPUs in the cluster
- See which GPUs are reserved and available
- Monitor resource utilization metrics
- Real-time tracking of:
  - GPU memory usage
  - Compute utilization percentage
  - Running processes on each GPU
  - Temperature and power consumption (if available)

### Reservation Management
- Find best available GPU based on resource requirements
- Reserve GPUs for specific durations
- Cancel existing reservations
- View active reservations

### GPU Process Management
- Start sample PyTorch workloads on specific GPUs
- Monitor the resource impact of running workloads
- Terminate specific processes when needed
- View process details (PID, memory usage, runtime)

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
Returns the current status of all GPUs in the cluster with detailed metrics.

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

### POST /start_process
Start a PyTorch worker process on a specified GPU.
- Parameters: `gpu_id` (string), `memory_usage` (float), `duration_minutes` (integer)

### POST /stop_process/{process_id}
Stop a running GPU process.
- Parameters: `process_id` (integer)

### GET /processes
Get information about all running GPU processes.

## Docker Environment

- Backend service: FastAPI running on port 8000 with GPU access
- Frontend service: Vue.js running on port 8080
- GPU worker containers: Running PyTorch workloads on allocated GPUs
- Development mode with hot-reloading for both services
- GPU passthrough from host to containers

## Technology Stack

- Backend: Python 3.10+, FastAPI, Uvicorn, SQLite, PyTorch, NVIDIA CUDA
- Frontend: Vue.js 3, Vue Router, Axios, Chart.js for visualization
- GPU Monitoring: NVIDIA Management Library (NVML), pynvml
- Containerization: Docker, Docker Compose with GPU support
- Development: Node.js, npm

## Roadmap

1. Basic functionality: GPU reservations and monitoring
2. Advanced job queueing with priorities
3. User authentication and authorization
4. Resource usage analytics and reporting
5. Enhanced scheduling algorithms
6. Integration with job schedulers like Slurm or Kubernetes
7. Multi-node cluster support