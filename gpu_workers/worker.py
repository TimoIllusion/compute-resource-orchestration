#!/usr/bin/env python3
"""
Simplified GPU Worker Process

This script runs on GPU worker containers and performs the following functions:
1. Handles communication with the orchestration backend
2. Runs simple PyTorch workloads to simulate GPU usage
3. Supports starting/stopping workloads via API
"""

import os
import time
import logging
import threading
import uuid
import json
from typing import Dict, Any, Optional

import torch
import requests
from torch import nn

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("gpu_worker")

# Get environment variables
NODE_ID = os.environ.get("NODE_ID", "node1")
GPU_ID = os.environ.get("GPU_ID", "0")
BACKEND_URL = os.environ.get("BACKEND_URL", "http://backend:8000")
UPDATE_INTERVAL = int(os.environ.get("UPDATE_INTERVAL", "5"))  # seconds

# Global state
running_processes = {}
worker_id = str(uuid.uuid4())
should_exit = threading.Event()


class GPUProcess:
    """Represents a running GPU workload process."""

    def __init__(
        self,
        process_id: str,
        memory_usage: float = 1.0,
        duration: int = -1,
        custom_code: str = None,
    ):
        self.process_id = process_id
        self.memory_usage = memory_usage  # in GB (approximate)
        self.duration = duration  # in seconds, -1 for indefinite
        self.start_time = time.time()
        self.thread = None
        self.is_running = False
        self.custom_code = custom_code

    def start(self):
        """Start the GPU workload in a separate thread."""
        if self.custom_code:
            self.thread = threading.Thread(target=self._run_custom_workload)
        else:
            self.thread = threading.Thread(target=self._run_workload)

        self.is_running = True
        self.thread.start()
        return self.process_id

    def stop(self):
        """Stop the GPU workload."""
        self.is_running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5.0)
            return True
        return False

    def _run_workload(self):
        """Run a simple PyTorch workload that uses the GPU."""
        try:
            # Check if GPU is available
            if torch.cuda.is_available():
                device = torch.device(f"cuda:{GPU_ID}")
                logger.info(f"Starting process {self.process_id} on GPU {GPU_ID}")

                # Create a matrix size based on the requested memory usage
                # This is approximate - 1GB is roughly 268 million float32 elements
                # A square matrix would be about 16K x 16K for 1GB
                matrix_size = int(4000 * (self.memory_usage**0.5))

                # Create tensors for matrix multiplication
                a = torch.rand(matrix_size, matrix_size, device=device)
                b = torch.rand(matrix_size, matrix_size, device=device)

                end_time = (
                    time.time() + self.duration if self.duration > 0 else float("inf")
                )

                # Run matrix multiplications until stopped
                while self.is_running and time.time() < end_time:
                    # Matrix multiplication
                    c = torch.matmul(a, b)

                    # Do something with the result to avoid optimization
                    a = a * 0.999 + torch.rand(1, device=device) * 0.001

                    # Add a small sleep to avoid maxing out the GPU
                    time.sleep(0.5)

            else:
                logger.warning(
                    f"CUDA not available for process {self.process_id}, running dummy CPU workload"
                )

                # Run a CPU-based loop if GPU is not available
                end_time = (
                    time.time() + self.duration if self.duration > 0 else float("inf")
                )

                while self.is_running and time.time() < end_time:
                    # Just do some CPU work
                    a = torch.rand(1000, 1000)
                    b = torch.rand(1000, 1000)
                    c = torch.matmul(a, b)
                    time.sleep(1.0)

            logger.info(f"Process {self.process_id} completed")

        except Exception as e:
            logger.error(f"Error in process {self.process_id}: {e}")
        finally:
            self.is_running = False

    def _run_custom_workload(self):
        """Run a custom PyTorch workload from provided code string."""
        try:
            if torch.cuda.is_available():
                device = torch.device(f"cuda:{GPU_ID}")
                logger.info(
                    f"Starting custom process {self.process_id} on GPU {GPU_ID}"
                )

                # Set up the execution environment
                local_vars = {
                    "torch": torch,
                    "nn": nn,
                    "device": device,
                    "is_running": lambda: self.is_running,
                    "process_id": self.process_id,
                    "logger": logger,
                }

                # Execute the custom code in the prepared environment
                try:
                    exec(self.custom_code, {}, local_vars)
                except Exception as e:
                    logger.error(f"Error in custom code execution: {e}")
            else:
                logger.warning(
                    f"CUDA not available for custom process {self.process_id}"
                )

        except Exception as e:
            logger.error(f"Error in custom process {self.process_id}: {e}")
        finally:
            self.is_running = False


def report_status():
    """Report worker status to the backend."""
    while not should_exit.is_set():
        try:
            # Gather basic worker and process status
            status = {
                "worker_id": worker_id,
                "node_id": NODE_ID,
                "gpu_id": GPU_ID,
                "timestamp": time.time(),
                "cuda_available": torch.cuda.is_available(),
                "processes": [],
            }

            # Add information about running processes
            for proc_id, process in running_processes.items():
                if process.is_running:
                    status["processes"].append(
                        {
                            "process_id": proc_id,
                            "memory_allocated": process.memory_usage,
                            "runtime": time.time() - process.start_time,
                            "duration": process.duration,
                        }
                    )

            # Send status to backend
            response = requests.post(
                f"{BACKEND_URL}/worker_status",
                json=status,
                headers={"Content-Type": "application/json"},
            )

            if response.status_code == 200:
                logger.debug("Status reported successfully")
            else:
                logger.warning(f"Failed to report status: {response.status_code}")

        except Exception as e:
            logger.error(f"Error reporting status: {e}")

        # Wait for the next update interval
        time.sleep(UPDATE_INTERVAL)


def start_process_handler(
    memory_usage: float = 1.0, duration_minutes: int = -1, custom_code: str = None
) -> str:
    """Start a new GPU process."""
    process_id = f"proc_{str(uuid.uuid4())[:8]}"
    duration_seconds = duration_minutes * 60 if duration_minutes > 0 else -1

    process = GPUProcess(process_id, memory_usage, duration_seconds, custom_code)
    process.start()

    running_processes[process_id] = process
    logger.info(f"Started process {process_id}")
    return process_id


def stop_process_handler(process_id: str) -> bool:
    """Stop a running GPU process."""
    if process_id in running_processes:
        success = running_processes[process_id].stop()
        if success:
            logger.info(f"Stopped process {process_id}")
            del running_processes[process_id]
        return success
    return False


def cleanup():
    """Stop all running processes and perform cleanup."""
    logger.info("Cleaning up resources...")
    for process_id in list(running_processes.keys()):
        stop_process_handler(process_id)


def signal_handler(sig, frame):
    """Handle termination signals."""
    logger.info(f"Received signal {sig}, shutting down...")
    should_exit.set()
    cleanup()


def register_with_backend():
    """Register this worker with the backend."""
    try:
        data = {
            "worker_id": worker_id,
            "node_id": NODE_ID,
            "gpu_id": GPU_ID,
            "cuda_available": torch.cuda.is_available(),
            "capabilities": {
                "torch_version": torch.__version__,
                "cuda_version": (
                    torch.version.cuda if torch.cuda.is_available() else "N/A"
                ),
                "device_name": (
                    torch.cuda.get_device_name(int(GPU_ID))
                    if torch.cuda.is_available()
                    else "CPU only"
                ),
            },
        }

        response = requests.post(
            f"{BACKEND_URL}/register_worker",
            json=data,
            headers={"Content-Type": "application/json"},
        )

        if response.status_code == 200:
            logger.info("Successfully registered with backend")
            return True
        else:
            logger.warning(f"Failed to register with backend: {response.status_code}")
            return False

    except Exception as e:
        logger.error(f"Error registering with backend: {e}")
        return False


def start_api_server():
    """Start a simple HTTP server to handle commands."""
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import json

    class CommandHandler(BaseHTTPRequestHandler):
        def _set_response(self, status_code=200, content_type="application/json"):
            self.send_response(status_code)
            self.send_header("Content-type", content_type)
            self.end_headers()

        def do_POST(self):
            content_length = int(self.headers["Content-Length"])
            post_data = self.rfile.read(content_length)

            try:
                data = json.loads(post_data.decode("utf-8"))

                if self.path == "/start_process":
                    memory_usage = data.get("memory_usage", 1.0)
                    duration_minutes = data.get("duration_minutes", -1)
                    custom_code = data.get("custom_code", None)

                    process_id = start_process_handler(
                        memory_usage, duration_minutes, custom_code
                    )
                    response = {"status": "success", "process_id": process_id}
                    self._set_response()
                    self.wfile.write(json.dumps(response).encode("utf-8"))

                elif self.path == "/stop_process":
                    process_id = data.get("process_id")

                    if process_id:
                        success = stop_process_handler(process_id)
                        response = {"status": "success" if success else "failed"}
                    else:
                        response = {"status": "failed", "error": "Missing process_id"}

                    self._set_response()
                    self.wfile.write(json.dumps(response).encode("utf-8"))

                else:
                    self._set_response(404)
                    self.wfile.write(json.dumps({"error": "Not found"}).encode("utf-8"))

            except Exception as e:
                logger.error(f"Error handling request: {e}")
                self._set_response(500)
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))

        def do_GET(self):
            if self.path == "/status":
                status = {
                    "worker_id": worker_id,
                    "node_id": NODE_ID,
                    "gpu_id": GPU_ID,
                    "cuda_available": torch.cuda.is_available(),
                    "processes": [],
                }

                for proc_id, process in running_processes.items():
                    if process.is_running:
                        status["processes"].append(
                            {
                                "process_id": proc_id,
                                "runtime": time.time() - process.start_time,
                                "memory_allocated": process.memory_usage,
                            }
                        )

                self._set_response()
                self.wfile.write(json.dumps(status).encode("utf-8"))
            else:
                self._set_response(404)
                self.wfile.write(json.dumps({"error": "Not found"}).encode("utf-8"))

    # Start the server in a separate thread
    server_address = ("", 8001)  # Different port from the backend
    httpd = HTTPServer(server_address, CommandHandler)

    server_thread = threading.Thread(target=httpd.serve_forever)
    server_thread.daemon = True
    server_thread.start()

    logger.info(f"API server started on port 8001")


def main():
    """Main entry point for the worker."""
    import signal

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info(f"Starting GPU worker on node {NODE_ID}, GPU {GPU_ID}")

    # Check GPU availability
    if torch.cuda.is_available():
        logger.info(
            f"CUDA is available, detected: {torch.cuda.get_device_name(int(GPU_ID))}"
        )
    else:
        logger.warning("CUDA is not available! Running in CPU-only mode.")

    # Register with backend
    retry_count = 0
    while retry_count < 5 and not register_with_backend():
        logger.info(
            f"Retrying backend registration in 5 seconds... ({retry_count+1}/5)"
        )
        time.sleep(5)
        retry_count += 1

    # Start status reporting thread
    status_thread = threading.Thread(target=report_status)
    status_thread.daemon = True
    status_thread.start()

    # Start API server to receive commands
    start_api_server()

    # Main loop - check for terminated processes
    try:
        while not should_exit.is_set():
            for proc_id in list(running_processes.keys()):
                if (
                    proc_id in running_processes
                    and not running_processes[proc_id].is_running
                ):
                    logger.info(f"Process {proc_id} has terminated, cleaning up")
                    del running_processes[proc_id]

            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        logger.info("Shutting down worker...")
        should_exit.set()
        cleanup()
        if status_thread.is_alive():
            status_thread.join(timeout=5.0)


if __name__ == "__main__":
    main()
