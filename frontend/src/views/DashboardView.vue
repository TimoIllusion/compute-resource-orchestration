<template>
  <div class="dashboard">
    <h1>GPU Cluster Dashboard</h1>
    
    <div v-if="loading" class="loading">
      Loading cluster status...
    </div>
    
    <div v-else-if="error" class="error">
      Failed to load cluster status: {{ error }}
    </div>
    
    <div v-else>
      <div class="actions">
        <button @click="refreshClusterStatus" class="btn refresh-btn">
          <i class="fas fa-sync"></i> Refresh Status
        </button>
        <button @click="resetCluster" class="btn reset-btn" :disabled="isResetting">
          <i class="fas fa-redo"></i> Reset Cluster
        </button>
      </div>
      
      <div class="gpus-container">
        <div class="gpu-card" v-for="gpu in gpuStatus" :key="`${gpu.node_id}_${gpu.gpu_id}`" 
             :class="{ 'gpu-reserved': isGpuReserved(gpu) }">
          <div class="gpu-header">
            <h3>{{ gpu.node_id }} - GPU {{ gpu.gpu_id }}</h3>
            <span class="gpu-status" :class="isGpuReserved(gpu) ? 'status-reserved' : 'status-available'">
              {{ isGpuReserved(gpu) ? 'Reserved' : 'Available' }}
            </span>
          </div>
          
          <!-- Memory usage visualization -->
          <div class="memory-bar">
            <div class="memory-label">Memory Usage:</div>
            <div class="memory-progress">
              <div class="memory-used" :style="{ width: getMemoryUsagePercent(gpu) + '%' }"></div>
            </div>
            <div class="memory-text">
              {{ getMemoryUsed(gpu) }} / {{ getMemoryTotal(gpu) }} GB
            </div>
          </div>
          
          <div class="gpu-info">
            <div class="info-row">
              <span class="label">Utilization:</span>
              <span class="value">{{ getGpuUtilization(gpu) }}%</span>
            </div>
            <div class="info-row">
              <span class="label">Temperature:</span>
              <span class="value">{{ getGpuTemperature(gpu) }}°C</span>
            </div>
            <div class="info-row" v-if="getGpuPower(gpu) > 0">
              <span class="label">Power:</span>
              <span class="value">{{ getGpuPower(gpu) }} W</span>
            </div>
            <div class="info-row" v-if="isGpuReserved(gpu)">
              <span class="label">Reserved by:</span>
              <span class="value">{{ getReservationUser(gpu) || 'Unknown' }}</span>
            </div>
            <div class="info-row" v-if="isGpuReserved(gpu)">
              <span class="label">Until:</span>
              <span class="value">{{ formatTime(getReservationEndTime(gpu)) }}</span>
            </div>
          </div>
          
          <div v-if="hasRunningProcesses(gpu)" class="processes-section">
            <h4>Running Processes</h4>
            <div class="process" v-for="(process, index) in getRunningProcesses(gpu)" :key="index">
              <div class="process-header">
                <div>{{ process.name || 'Process' }} {{ process.pid ? `(PID: ${process.pid})` : '' }}</div>
                <div class="process-memory">{{ process.memory_usage || process.memory_allocated || 0 }} GB</div>
              </div>
              <div class="process-info" v-if="process.type === 'managed'">
                Runtime: {{ formatDuration(process.runtime || 0) }}
              </div>
            </div>
          </div>

          <div class="gpu-actions">
            <button 
              v-if="!isGpuReserved(gpu)"
              @click="reserveGpu(gpu.gpu_id)"
              class="btn reserve-btn"
              :disabled="isReserving"
            >
              <i class="fas fa-lock"></i> Reserve
            </button>

            <button 
              v-if="canStartProcess(gpu)"
              @click="startProcess(gpu.gpu_id)"
              class="btn process-btn"
              :disabled="isProcessing"
            >
              <i class="fas fa-play"></i> Start Process
            </button>
            
            <!-- New workload buttons -->
            <button
              v-if="isGpuReserved(gpu) && !hasRunningWorkload(gpu)"
              @click="startDummyWorkload(gpu.gpu_id)"
              class="btn workload-btn"
              :disabled="isProcessing"
            >
              <i class="fas fa-cogs"></i> Run Dummy Workload
            </button>
            
            <button
              v-if="isGpuReserved(gpu) && hasRunningWorkload(gpu)"
              @click="stopWorkload(getRunningWorkloadId(gpu))"
              class="btn stop-workload-btn"
              :disabled="isProcessing"
            >
              <i class="fas fa-stop"></i> Stop Workload
            </button>
            
            <button
              v-if="isGpuReserved(gpu)"
              @click="startCustomWorkload(gpu.gpu_id)"
              class="btn custom-workload-btn"
              :disabled="isProcessing"
            >
              <i class="fas fa-code"></i> Custom Workload
            </button>
          </div>
        </div>
      </div>
      
      <!-- Process Management Section -->
      <div class="processes-management" v-if="allProcesses.length > 0">
        <h2>All Running Processes</h2>
        <table class="processes-table">
          <thead>
            <tr>
              <th>Process ID</th>
              <th>GPU</th>
              <th>Memory Usage</th>
              <th>Runtime</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="process in allProcesses" :key="process.process_id || process.pid">
              <td>{{ process.process_id || process.pid }}</td>
              <td>{{ process.node_id }}-{{ process.gpu_id }}</td>
              <td>{{ process.memory_usage || process.memory_allocated || 0 }} GB</td>
              <td>{{ process.runtime ? formatDuration(process.runtime) : 'N/A' }}</td>
              <td>
                <button 
                  v-if="process.type === 'managed'"
                  @click="stopProcess(process.process_id)" 
                  class="btn stop-btn"
                  :disabled="isProcessing"
                >
                  Stop
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, computed } from 'vue';

// API URL from environment variable
const apiBaseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Reactive state
const gpuStatus = ref([]);
const allProcesses = ref([]);
const loading = ref(true);
const error = ref(null);
const isReserving = ref(false);
const isResetting = ref(false);
const isProcessing = ref(false);
const refreshInterval = ref(null);

// Get all reservations
const reservations = ref([]);
const fetchReservations = async () => {
  try {
    const response = await fetch(`${apiBaseUrl}/reservations`);
    if (!response.ok) {
      throw new Error(`Error ${response.status}: ${response.statusText}`);
    }
    reservations.value = await response.json();
  } catch (err) {
    console.error('Failed to fetch reservations:', err);
  }
};

// Get all processes
const fetchProcesses = async () => {
  try {
    const response = await fetch(`${apiBaseUrl}/processes`);
    if (!response.ok) {
      throw new Error(`Error ${response.status}: ${response.statusText}`);
    }
    allProcesses.value = await response.json();
  } catch (err) {
    console.error('Failed to fetch processes:', err);
  }
};

// Fetch GPU status on component mount and start auto-refresh
onMounted(() => {
  refreshClusterStatus();
  fetchReservations();
  fetchProcesses();
  
  // Set up auto-refresh every 5 seconds
  refreshInterval.value = setInterval(() => {
    refreshClusterStatus();
    fetchReservations();
    fetchProcesses();
  }, 5000);
});

// Clear interval on component unmount
onBeforeUnmount(() => {
  if (refreshInterval.value) {
    clearInterval(refreshInterval.value);
  }
});

// Format time for display
const formatTime = (timestamp) => {
  if (!timestamp) return 'N/A';
  return new Date(timestamp).toLocaleString();
};

// Format duration in seconds to human readable format
const formatDuration = (seconds) => {
  if (!seconds && seconds !== 0) return 'N/A';
  
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);
  
  return [
    hours > 0 ? `${hours}h` : '',
    minutes > 0 ? `${minutes}m` : '',
    `${secs}s`
  ].filter(Boolean).join(' ');
};

// Check if GPU is reserved
const isGpuReserved = (gpu) => {
  return reservations.value.some(r => r.gpu_id === gpu.gpu_id);
};

// Get reservation user for a GPU
const getReservationUser = (gpu) => {
  const reservation = reservations.value.find(r => r.gpu_id === gpu.gpu_id);
  return reservation ? reservation.user : null;
};

// Get reservation end time for a GPU
const getReservationEndTime = (gpu) => {
  const reservation = reservations.value.find(r => r.gpu_id === gpu.gpu_id);
  return reservation ? reservation.end_time : null;
};

// Memory usage methods
const getMemoryTotal = (gpu) => {
  if (gpu.real_metrics?.memory?.total) {
    return gpu.real_metrics.memory.total.toFixed(1);
  }
  return gpu.max_memory || 0;
};

const getMemoryUsed = (gpu) => {
  if (gpu.real_metrics?.memory?.used) {
    return gpu.real_metrics.memory.used.toFixed(1);
  }
  return gpu.used_memory || 0;
};

const getMemoryUsagePercent = (gpu) => {
  const total = parseFloat(getMemoryTotal(gpu));
  const used = parseFloat(getMemoryUsed(gpu));
  
  if (total && total > 0) {
    return Math.min(Math.round((used / total) * 100), 100);
  }
  return 0;
};

// Get GPU utilization
const getGpuUtilization = (gpu) => {
  if (gpu.real_metrics?.utilization?.gpu !== undefined) {
    return gpu.real_metrics.utilization.gpu;
  }
  return 0;
};

// Get GPU temperature
const getGpuTemperature = (gpu) => {
  if (gpu.real_metrics?.temperature !== undefined) {
    return gpu.real_metrics.temperature;
  }
  return 'N/A';
};

// Get GPU power
const getGpuPower = (gpu) => {
  if (gpu.real_metrics?.power) {
    return gpu.real_metrics.power.toFixed(1);
  }
  return 0;
};

// Check if GPU has running processes
const hasRunningProcesses = (gpu) => {
  if (gpu.real_metrics?.processes && gpu.real_metrics.processes.length > 0) {
    return true;
  }
  if (gpu.real_metrics?.managed_processes && gpu.real_metrics.managed_processes.length > 0) {
    return true;
  }
  return false;
};

// Get running processes on a GPU
const getRunningProcesses = (gpu) => {
  const processes = [];
  
  if (gpu.real_metrics?.processes) {
    processes.push(...gpu.real_metrics.processes.map(p => ({ ...p, type: 'system' })));
  }
  
  if (gpu.real_metrics?.managed_processes) {
    processes.push(...gpu.real_metrics.managed_processes.map(p => ({ ...p, type: 'managed' })));
  }
  
  return processes;
};

// Check if we can start a process on this GPU
const canStartProcess = (gpu) => {
  // Allow starting process if GPU is not reserved
  return !isGpuReserved(gpu);
};

// Fetch cluster status from API
const refreshClusterStatus = async () => {
  if (loading.value) return;
  
  loading.value = true;
  error.value = null;
  
  try {
    const response = await fetch(`${apiBaseUrl}/status`);
    
    if (!response.ok) {
      throw new Error(`Error ${response.status}: ${response.statusText}`);
    }
    
    gpuStatus.value = await response.json();
  } catch (err) {
    error.value = err.message;
    console.error('Failed to fetch cluster status:', err);
  } finally {
    loading.value = false;
  }
};

// Reset the cluster (clear all reservations)
const resetCluster = async () => {
  if (isResetting.value) return;
  
  isResetting.value = true;
  
  try {
    const response = await fetch(`${apiBaseUrl}/reset`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    });
    
    if (!response.ok) {
      throw new Error(`Error ${response.status}: ${response.statusText}`);
    }
    
    await refreshClusterStatus();
    await fetchReservations();
  } catch (err) {
    error.value = err.message;
    console.error('Failed to reset cluster:', err);
  } finally {
    isResetting.value = false;
  }
};

// Reserve a GPU
const reserveGpu = async (gpuId) => {
  if (isReserving.value) return;
  
  isReserving.value = true;
  
  try {
    // For now, hardcode the user and duration - these would come from a form or logged-in user
    const user = prompt('Enter your username:', 'default_user');
    const duration_hours = parseInt(prompt('Enter reservation duration in hours:', '1'));
    
    if (!user) {
      isReserving.value = false;
      return;
    }
    
    const response = await fetch(`${apiBaseUrl}/reserve`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ user, duration_hours }),
    });
    
    if (!response.ok) {
      throw new Error(`Error ${response.status}: ${response.statusText}`);
    }
    
    const result = await response.json();
    alert(`GPU ${result.gpu_id} reserved successfully. Reservation ID: ${result.reservation_id}`);
    
    await refreshClusterStatus();
    await fetchReservations();
  } catch (err) {
    error.value = err.message;
    console.error('Failed to reserve GPU:', err);
  } finally {
    isReserving.value = false;
  }
};

// Start a process on a GPU
const startProcess = async (gpuId) => {
  if (isProcessing.value) return;
  
  isProcessing.value = true;
  
  try {
    const memory_usage = parseFloat(prompt('Enter memory usage in GB:', '1.0'));
    const duration_minutes = parseInt(prompt('Enter process duration in minutes (0 for indefinite):', '30'));
    
    if (isNaN(memory_usage) || memory_usage <= 0) {
      alert('Please enter a valid memory size');
      return;
    }
    
    const response = await fetch(`${apiBaseUrl}/start_process`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ gpu_id: gpuId, memory_usage, duration_minutes }),
    });
    
    if (!response.ok) {
      throw new Error(`Error ${response.status}: ${response.statusText}`);
    }
    
    const result = await response.json();
    alert(`Process started on GPU ${gpuId}. Process ID: ${result.process_id}`);
    
    await refreshClusterStatus();
    await fetchProcesses();
  } catch (err) {
    error.value = err.message;
    console.error('Failed to start process:', err);
  } finally {
    isProcessing.value = false;
  }
};

// Stop a running process
const stopProcess = async (processId) => {
  if (isProcessing.value) return;
  
  isProcessing.value = true;
  
  try {
    const response = await fetch(`${apiBaseUrl}/stop_process/${processId}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    });
    
    if (!response.ok) {
      throw new Error(`Error ${response.status}: ${response.statusText}`);
    }
    
    alert(`Process ${processId} stopped successfully.`);
    
    await refreshClusterStatus();
    await fetchProcesses();
  } catch (err) {
    error.value = err.message;
    console.error('Failed to stop process:', err);
  } finally {
    isProcessing.value = false;
  }
};

// Check if GPU has a running workload specifically
const hasRunningWorkload = (gpu) => {
  if (!gpu.real_metrics?.managed_processes) return false;
  return gpu.real_metrics.managed_processes.some(p => p.process_id && p.process_id.startsWith('proc_'));
};

// Get running workload ID if available
const getRunningWorkloadId = (gpu) => {
  if (!gpu.real_metrics?.managed_processes) return null;
  const workload = gpu.real_metrics.managed_processes.find(p => p.process_id && p.process_id.startsWith('proc_'));
  return workload ? workload.process_id : null;
};

// Start a simple dummy workload on a reserved GPU
const startDummyWorkload = async (gpuId) => {
  if (isProcessing.value) return;
  
  isProcessing.value = true;
  
  try {
    // Default memory usage for dummy workload: 1GB
    const memory_usage = 1.0;
    // Run indefinitely until stopped
    const duration_minutes = -1;
    
    const response = await fetch(`${apiBaseUrl}/run_workload`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ 
        gpu_id: gpuId, 
        memory_usage, 
        duration_minutes 
      }),
    });
    
    if (!response.ok) {
      throw new Error(`Error ${response.status}: ${response.statusText}`);
    }
    
    const result = await response.json();
    alert(`Dummy workload started on GPU ${gpuId}. Process ID: ${result.process_id}`);
    
    await refreshClusterStatus();
    await fetchProcesses();
  } catch (err) {
    error.value = err.message;
    console.error('Failed to start dummy workload:', err);
  } finally {
    isProcessing.value = false;
  }
};

// Start a custom workload with PyTorch code
const startCustomWorkload = async (gpuId) => {
  if (isProcessing.value) return;
  
  isProcessing.value = true;
  
  try {
    // Get memory usage and custom code from user
    const memory_usage = parseFloat(prompt('Enter memory usage in GB:', '1.0'));
    
    const defaultCode = 
`# PyTorch code to run on the GPU
import time

# Use the device provided in the environment
# Access with the 'device' variable

# Create some tensors on the GPU
a = torch.rand(8000, 8000, device=device)
b = torch.rand(8000, 8000, device=device)

# Run computation until the worker stops us
while is_running():
    # Matrix multiplication
    c = torch.matmul(a, b)
    
    # Print some info to the logs
    logger.info(f"Running custom code on {device}")
    
    # Sleep a bit to avoid maxing out the GPU
    time.sleep(1.0)
`;

    const custom_code = prompt('Enter custom PyTorch code to execute:', defaultCode);
    
    if (!custom_code || isNaN(memory_usage) || memory_usage <= 0) {
      alert('Please enter valid memory size and code');
      isProcessing.value = false;
      return;
    }
    
    const response = await fetch(`${apiBaseUrl}/run_workload`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ 
        gpu_id: gpuId, 
        memory_usage, 
        duration_minutes: -1,
        custom_code 
      }),
    });
    
    if (!response.ok) {
      throw new Error(`Error ${response.status}: ${response.statusText}`);
    }
    
    const result = await response.json();
    alert(`Custom workload started on GPU ${gpuId}. Process ID: ${result.process_id}`);
    
    await refreshClusterStatus();
    await fetchProcesses();
  } catch (err) {
    error.value = err.message;
    console.error('Failed to start custom workload:', err);
  } finally {
    isProcessing.value = false;
  }
};

// Stop a running workload
const stopWorkload = async (processId) => {
  if (isProcessing.value || !processId) return;
  
  isProcessing.value = true;
  
  try {
    const response = await fetch(`${apiBaseUrl}/stop_workload/${processId}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    });
    
    if (!response.ok) {
      throw new Error(`Error ${response.status}: ${response.statusText}`);
    }
    
    const result = await response.json();
    alert(`Workload ${processId} stopped successfully.`);
    
    await refreshClusterStatus();
    await fetchProcesses();
  } catch (err) {
    error.value = err.message;
    console.error('Failed to stop workload:', err);
  } finally {
    isProcessing.value = false;
  }
};
</script>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 2rem;
}

.actions {
  display: flex;
  gap: 1rem;
  margin-bottom: 1rem;
}

.btn {
  padding: 0.5rem 1rem;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 500;
  transition: background-color 0.2s;
  border: none;
}

.refresh-btn {
  background-color: #3498db;
  color: white;
}

.refresh-btn:hover {
  background-color: #2980b9;
}

.reset-btn {
  background-color: #e74c3c;
  color: white;
}

.reset-btn:hover {
  background-color: #c0392b;
}

.reserve-btn {
  background-color: #2ecc71;
  color: white;
}

.reserve-btn:hover {
  background-color: #27ae60;
}

.process-btn {
  background-color: #9b59b6;
  color: white;
  margin-left: 0.5rem;
}

.process-btn:hover {
  background-color: #8e44ad;
}

.stop-btn {
  background-color: #e74c3c;
  color: white;
  padding: 0.25rem 0.5rem;
  font-size: 0.875rem;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.gpus-container {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
  gap: 1.5rem;
}

.gpu-card {
  border-radius: 8px;
  padding: 1.25rem;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  background-color: white;
  transition: transform 0.2s, box-shadow 0.2s;
}

.gpu-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 6px 12px rgba(0, 0, 0, 0.15);
}

.gpu-reserved {
  border-left: 4px solid #e74c3c;
}

.gpu-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.gpu-header h3 {
  margin: 0;
  font-size: 1.25rem;
}

.gpu-status {
  font-size: 0.875rem;
  padding: 0.25rem 0.75rem;
  border-radius: 999px;
}

.status-available {
  background-color: #eafaf1;
  color: #27ae60;
}

.status-reserved {
  background-color: #fdedec;
  color: #e74c3c;
}

.memory-bar {
  margin-bottom: 1.25rem;
}

.memory-label {
  margin-bottom: 0.25rem;
  font-size: 0.875rem;
  font-weight: 500;
}

.memory-progress {
  height: 0.75rem;
  background-color: #ecf0f1;
  border-radius: 999px;
  overflow: hidden;
}

.memory-used {
  height: 100%;
  background-color: #3498db;
  border-radius: 999px;
  transition: width 0.3s ease;
}

.memory-text {
  margin-top: 0.25rem;
  font-size: 0.875rem;
  text-align: right;
}

.gpu-info {
  margin-bottom: 1rem;
}

.info-row {
  display: flex;
  justify-content: space-between;
  margin-bottom: 0.5rem;
}

.label {
  font-weight: 500;
  color: #7f8c8d;
}

.value {
  font-weight: 600;
}

.processes-section {
  margin-top: 1rem;
  margin-bottom: 1rem;
  border-top: 1px solid #ecf0f1;
  padding-top: 0.75rem;
}

.processes-section h4 {
  margin-top: 0;
  margin-bottom: 0.75rem;
  font-size: 1rem;
}

.process {
  background-color: #f8f9fa;
  padding: 0.75rem;
  border-radius: 4px;
  margin-bottom: 0.5rem;
}

.process-header {
  display: flex;
  justify-content: space-between;
  font-weight: 500;
  margin-bottom: 0.25rem;
}

.process-memory {
  color: #2980b9;
}

.process-info {
  font-size: 0.875rem;
  color: #7f8c8d;
}

.gpu-actions {
  margin-top: 1.25rem;
  display: flex;
}

.processes-management {
  margin-top: 3rem;
}

.processes-table {
  width: 100%;
  border-collapse: collapse;
}

.processes-table th, .processes-table td {
  padding: 0.75rem 1rem;
  text-align: left;
  border-bottom: 1px solid #ecf0f1;
}

.processes-table th {
  font-weight: 600;
  background-color: #f8f9fa;
}

.loading, .error {
  padding: 2rem;
  text-align: center;
  font-size: 1.125rem;
}

.error {
  color: #e74c3c;
}
</style>