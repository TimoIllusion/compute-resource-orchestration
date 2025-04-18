#!/usr/bin/env python3
"""
GPU Worker Process

This script runs on GPU worker containers and performs the following functions:
1. Handles communication with the orchestration backend
2. Runs configurable PyTorch workloads to simulate GPU usage
3. Reports GPU metrics back to the backend
"""

import os
import time
import json
import signal
import logging
import threading
import subprocess
import uuid
from typing import Dict, List, Any, Optional

import torch
import numpy as np
import requests
import pynvml
import psutil
from torch import nn
import GPUtil

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("gpu_worker")

# Get environment variables
NODE_ID = os.environ.get("NODE_ID", "node1")
GPU_ID = os.environ.get("GPU_ID", "0")
BACKEND_URL = os.environ.get("BACKEND_URL", "http://backend:8000")
DEV_MODE = os.environ.get("DEV_MODE", "0") == "1"
UPDATE_INTERVAL = int(os.environ.get("UPDATE_INTERVAL", "5"))  # seconds

# Global state
running_processes = {}
worker_id = str(uuid.uuid4())
should_exit = threading.Event()


class GPUProcess:
    """Represents a running GPU workload process."""

    def __init__(self, process_id: str, memory_usage: float, duration: int = -1):
        self.process_id = process_id
        self.memory_usage = memory_usage  # in GB
        self.duration = duration  # in seconds, -1 for indefinite
        self.start_time = time.time()
        self.thread = None
        self.is_running = False

    def start(self):
        """Start the GPU workload in a separate thread."""
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
        """Run a PyTorch workload that consumes the specified amount of GPU memory."""
        try:
            # Ensure GPU is available
            if not torch.cuda.is_available():
                logger.error(f"CUDA not available for process {self.process_id}")
                return

            # Set device
            device = torch.device(f"cuda:{GPU_ID}")
            logger.info(
                f"Starting process {self.process_id} on GPU {GPU_ID} with {self.memory_usage}GB memory allocation"
            )

            # Allocate memory - each float32 is 4 bytes
            # Convert GB to bytes and calculate number of elements needed
            num_elements = int((self.memory_usage * 1024 * 1024 * 1024) / 4)

            # Create tensors that will consume the specified amount of memory
            x = torch.rand(num_elements, device=device)

            # Create a simple model for computation
            model = nn.Sequential(
                nn.Linear(100, 200),
                nn.ReLU(),
                nn.Linear(200, 100),
                nn.ReLU(),
            ).to(device)

            end_time = (
                time.time() + self.duration if self.duration > 0 else float("inf")
            )

            # Run computations until stopped or duration expires
            while self.is_running and time.time() < end_time:
                # Create random input for the model
                inputs = torch.rand(32, 100, device=device)

                # Run forward pass
                outputs = model(inputs)

                # Run some matrix operations to simulate computation
                for _ in range(100):
                    y = torch.matmul(outputs, torch.rand_like(outputs))
                    z = torch.nn.functional.relu(y)

                # Update tensor to prevent optimization
                x = x * 0.999 + torch.rand(1, device=device) * 0.001

                # Simulate some computation time
                time.sleep(0.1)

            logger.info(f"Process {self.process_id} completed")

        except Exception as e:
            logger.error(f"Error in process {self.process_id}: {e}")
        finally:
            self.is_running = False


def get_gpu_metrics() -> Dict[str, Any]:
    """Get current GPU metrics using pynvml."""
    try:
        # Initialize pynvml
        pynvml.nvmlInit()

        # Get handle to the GPU
        handle = pynvml.nvmlDeviceGetHandleByIndex(int(GPU_ID))

        # Get memory info
        mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        total_mem = mem_info.total / (1024 * 1024 * 1024)  # Convert to GB
        used_mem = mem_info.used / (1024 * 1024 * 1024)  # Convert to GB
        free_mem = mem_info.free / (1024 * 1024 * 1024)  # Convert to GB

        # Get utilization rates
        utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
        gpu_util = utilization.gpu  # GPU utilization percentage
        mem_util = utilization.memory  # Memory utilization percentage

        # Get temperature
        temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)

        # Get power usage if available
        try:
            power = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0  # Convert to W
        except pynvml.NVMLError:
            power = 0.0

        # Get processes running on the GPU
        processes = []
        try:
            proc_info = pynvml.nvmlDeviceGetComputeRunningProcesses(handle)
            for proc in proc_info:
                pid = proc.pid
                used_mem_proc = proc.usedGpuMemory / (
                    1024 * 1024 * 1024
                )  # Convert to GB

                # Try to get process name
                try:
                    p = psutil.Process(pid)
                    process_name = p.name()
                    cmd_line = " ".join(p.cmdline())
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    process_name = "Unknown"
                    cmd_line = "Unknown"

                processes.append(
                    {
                        "pid": pid,
                        "name": process_name,
                        "command": cmd_line,
                        "memory_usage": used_mem_proc,
                    }
                )
        except pynvml.NVMLError:
            pass

        pynvml.nvmlShutdown()

        return {
            "node_id": NODE_ID,
            "gpu_id": GPU_ID,
            "timestamp": time.time(),
            "memory": {"total": total_mem, "used": used_mem, "free": free_mem},
            "utilization": {"gpu": gpu_util, "memory": mem_util},
            "temperature": temp,
            "power": power,
            "processes": processes,
        }

    except Exception as e:
        logger.error(f"Error getting GPU metrics: {e}")
        # Return fallback metrics
        return {
            "node_id": NODE_ID,
            "gpu_id": GPU_ID,
            "timestamp": time.time(),
            "memory": {"total": 0.0, "used": 0.0, "free": 0.0},
            "utilization": {"gpu": 0, "memory": 0},
            "temperature": 0,
            "power": 0.0,
            "processes": [],
        }


def report_metrics():
    """Report GPU metrics to the backend."""
    while not should_exit.is_set():
        try:
            metrics = get_gpu_metrics()

            # Add information about our managed processes
            managed_procs = []
            for proc_id, process in running_processes.items():
                if process.is_running:
                    managed_procs.append(
                        {
                            "process_id": proc_id,
                            "memory_allocated": process.memory_usage,
                            "runtime": time.time() - process.start_time,
                            "duration": process.duration,
                        }
                    )

            metrics["managed_processes"] = managed_procs

            # Send metrics to backend
            response = requests.post(
                f"{BACKEND_URL}/gpu_metrics",
                json=metrics,
                headers={"Content-Type": "application/json"},
            )

            if response.status_code == 200:
                logger.debug("Metrics reported successfully")
            else:
                logger.warning(f"Failed to report metrics: {response.status_code}")

        except Exception as e:
            logger.error(f"Error reporting metrics: {e}")

        # Wait for the next update interval
        time.sleep(UPDATE_INTERVAL)


def start_process_handler(memory_usage: float, duration_minutes: int = -1) -> str:
    """Start a new GPU process with specified memory usage."""
    process_id = f"proc_{str(uuid.uuid4())[:8]}"
    duration_seconds = duration_minutes * 60 if duration_minutes > 0 else -1

    process = GPUProcess(process_id, memory_usage, duration_seconds)
    process.start()

    running_processes[process_id] = process
    return process_id


def stop_process_handler(process_id: str) -> bool:
    """Stop a running GPU process."""
    if process_id in running_processes:
        success = running_processes[process_id].stop()
        if success:
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
            "capabilities": {
                "cuda_version": torch.version.cuda,
                "torch_version": torch.__version__,
                "compute_capability": (
                    torch.cuda.get_device_capability(int(GPU_ID))
                    if torch.cuda.is_available()
                    else None
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


def start_dummy_workloads():
    """Start some dummy workloads for demonstration purposes in dev mode."""
    if DEV_MODE:
        logger.info("Starting dummy workloads for demonstration")
        # Start a small workload (1GB) that runs for 10 minutes
        start_process_handler(1.0, 10)
        time.sleep(2)  # Wait to ensure first process starts
        # Start a medium workload (2GB) that runs indefinitely
        start_process_handler(2.0, -1)


def main():
    """Main entry point for the worker."""
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
        logger.warning("CUDA is not available! Running in limited mode.")

    # Try to register with backend
    retry_count = 0
    while retry_count < 5 and not register_with_backend():
        logger.info(
            f"Retrying backend registration in 5 seconds... ({retry_count+1}/5)"
        )
        time.sleep(5)
        retry_count += 1

    # Start metrics reporting thread
    metrics_thread = threading.Thread(target=report_metrics)
    metrics_thread.daemon = True
    metrics_thread.start()

    # Start dummy workloads in dev mode
    start_dummy_workloads()

    # Main loop - check for terminated processes and clean them up
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
        if metrics_thread.is_alive():
            metrics_thread.join(timeout=5.0)


if __name__ == "__main__":
    main()
