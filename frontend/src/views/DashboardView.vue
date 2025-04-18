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
          Refresh Status
        </button>
        <button @click="resetCluster" class="btn reset-btn" :disabled="isResetting">
          Reset Cluster
        </button>
      </div>
      
      <div class="gpus-container">
        <div class="gpu-card" v-for="gpu in gpuStatus" :key="gpu.id" :class="{ 'gpu-reserved': gpu.reserved }">
          <div class="gpu-header">
            <h3>GPU {{ gpu.id }}</h3>
            <span class="gpu-status" :class="gpu.reserved ? 'status-reserved' : 'status-available'">
              {{ gpu.reserved ? 'Reserved' : 'Available' }}
            </span>
          </div>
          
          <div class="gpu-info">
            <div class="info-row">
              <span class="label">Memory:</span>
              <span class="value">{{ gpu.memory }} GB</span>
            </div>
            <div class="info-row">
              <span class="label">Utilization:</span>
              <span class="value">{{ gpu.utilization }}%</span>
            </div>
            <div class="info-row" v-if="gpu.reserved">
              <span class="label">Reserved by:</span>
              <span class="value">{{ gpu.user || 'Unknown' }}</span>
            </div>
            <div class="info-row" v-if="gpu.reserved">
              <span class="label">Until:</span>
              <span class="value">{{ formatTime(gpu.end_time) }}</span>
            </div>
          </div>
          
          <div class="gpu-actions">
            <button 
              v-if="!gpu.reserved" 
              @click="reserveGpu(gpu.id)" 
              class="btn reserve-btn"
              :disabled="isReserving"
            >
              Reserve
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';

// API URL from environment variable
const apiBaseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Reactive state
const gpuStatus = ref([]);
const loading = ref(true);
const error = ref(null);
const isReserving = ref(false);
const isResetting = ref(false);

// Fetch GPU status on component mount
onMounted(() => {
  refreshClusterStatus();
});

// Format time for display
const formatTime = (timestamp) => {
  if (!timestamp) return 'N/A';
  return new Date(timestamp).toLocaleString();
};

// Fetch cluster status from API
const refreshClusterStatus = async () => {
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
  } catch (err) {
    error.value = err.message;
    console.error('Failed to reserve GPU:', err);
  } finally {
    isReserving.value = false;
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

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.gpus-container {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
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

.loading, .error {
  padding: 2rem;
  text-align: center;
  font-size: 1.125rem;
}

.error {
  color: #e74c3c;
}
</style>