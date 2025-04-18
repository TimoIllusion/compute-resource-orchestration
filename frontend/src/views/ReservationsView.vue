<template>
  <div class="reservations">
    <h1>GPU Reservations</h1>
    
    <div v-if="loading" class="loading">
      Loading reservations...
    </div>
    
    <div v-else-if="error" class="error">
      Failed to load reservations: {{ error }}
    </div>
    
    <div v-else>
      <div class="actions">
        <button @click="refreshReservations" class="btn refresh-btn">
          Refresh Reservations
        </button>
      </div>
      
      <div v-if="reservations.length === 0" class="no-reservations">
        No active reservations found.
      </div>
      
      <div v-else class="reservations-table-container">
        <table class="reservations-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>GPU</th>
              <th>User</th>
              <th>Start Time</th>
              <th>End Time</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="reservation in reservations" :key="reservation.id">
              <td>{{ reservation.id }}</td>
              <td>GPU {{ reservation.gpu_id }}</td>
              <td>{{ reservation.user }}</td>
              <td>{{ formatTime(reservation.start_time) }}</td>
              <td>{{ formatTime(reservation.end_time) }}</td>
              <td>
                <button 
                  @click="cancelReservation(reservation.id)" 
                  class="btn cancel-btn"
                  :disabled="isCancelling"
                >
                  Cancel
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
import { ref, onMounted } from 'vue';

// API URL from environment variable
const apiBaseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Reactive state
const reservations = ref([]);
const loading = ref(true);
const error = ref(null);
const isCancelling = ref(false);

// Fetch reservations on component mount
onMounted(() => {
  refreshReservations();
});

// Format time for display
const formatTime = (timestamp) => {
  if (!timestamp) return 'N/A';
  return new Date(timestamp).toLocaleString();
};

// Fetch all reservations from API
const refreshReservations = async () => {
  loading.value = true;
  error.value = null;
  
  try {
    const response = await fetch(`${apiBaseUrl}/reservations`);
    
    if (!response.ok) {
      throw new Error(`Error ${response.status}: ${response.statusText}`);
    }
    
    reservations.value = await response.json();
  } catch (err) {
    error.value = err.message;
    console.error('Failed to fetch reservations:', err);
  } finally {
    loading.value = false;
  }
};

// Cancel a reservation
const cancelReservation = async (reservationId) => {
  if (isCancelling.value) return;
  
  if (!confirm(`Are you sure you want to cancel reservation ${reservationId}?`)) {
    return;
  }
  
  isCancelling.value = true;
  
  try {
    const response = await fetch(`${apiBaseUrl}/cancel/${reservationId}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    });
    
    if (!response.ok) {
      throw new Error(`Error ${response.status}: ${response.statusText}`);
    }
    
    const result = await response.json();
    alert(result.message || 'Reservation cancelled successfully.');
    
    await refreshReservations();
  } catch (err) {
    error.value = err.message;
    console.error('Failed to cancel reservation:', err);
  } finally {
    isCancelling.value = false;
  }
};
</script>

<style scoped>
.reservations {
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

.cancel-btn {
  background-color: #e74c3c;
  color: white;
  padding: 0.25rem 0.5rem;
  font-size: 0.875rem;
}

.cancel-btn:hover {
  background-color: #c0392b;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.reservations-table-container {
  overflow-x: auto;
}

.reservations-table {
  width: 100%;
  border-collapse: collapse;
}

.reservations-table th,
.reservations-table td {
  padding: 0.75rem 1rem;
  text-align: left;
}

.reservations-table th {
  background-color: #f8f9fa;
  font-weight: 600;
  border-bottom: 2px solid #e9ecef;
}

.reservations-table tr {
  border-bottom: 1px solid #e9ecef;
}

.reservations-table tr:hover {
  background-color: #f8f9fa;
}

.no-reservations {
  padding: 2rem;
  text-align: center;
  color: #7f8c8d;
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