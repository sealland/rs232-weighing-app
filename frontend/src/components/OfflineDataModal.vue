<template>
  <div v-if="isVisible" class="modal-overlay" @click.self="closeModal">
    <div class="modal-content">
      <div class="modal-header">
        <h2>Offline Data Management</h2>
        <button @click="closeModal" class="close-button">&times;</button>
      </div>
      <div class="modal-body">
        <div class="sync-controls">
          <button @click="syncAllData" :disabled="isLoading || !unsyncedTickets.length">
            <span v-if="isLoading">🔄 Syncing... ({{ syncProgress }} / {{ unsyncedTickets.length }})</span>
            <span v-else>🚀 Sync All to Server ({{ unsyncedTickets.length }} items)</span>
          </button>
          <button @click="fetchLocalData" :disabled="isLoading" class="refresh-button">
            🔃 Refresh
            </button>
          </div>
          
        <p v-if="isLoading" class="loading-text">Loading local data...</p>
        <p v-if="error" class="error-text">{{ error }}</p>

        <div v-if="!isLoading && !localTickets.length" class="no-data">
          No local data found.
          </div>
          
        <div class.bind="local-data-tables" v-if="!isLoading && localTickets.length">
          <h3>Unsynced Tickets</h3>
          <table class="data-table">
            <thead>
              <tr>
                <th>Local ID</th>
                <th>License Plate</th>
                <th>Weight In</th>
                <th>Status</th>
                <th>Items</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="ticket in unsyncedTickets" :key="ticket.WE_ID">
                <td>{{ ticket.WE_ID.substring(0, 12) }}...</td>
                <td>{{ ticket.WE_LICENSE }}</td>
                <td>{{ ticket.WE_WEIGHTIN?.toLocaleString() }}</td>
                <td><span class="status-tag new">{{ ticket.sync_status }}</span></td>
                <td>{{ ticket.items?.length || 0 }}</td>
              </tr>
               <tr v-if="!unsyncedTickets.length">
                <td colspan="5" class="text-center">No unsynced tickets.</td>
              </tr>
            </tbody>
          </table>

          <h3>Synced Tickets</h3>
           <table class="data-table">
            <thead>
              <tr>
                <th>Local ID</th>
                <th>Server ID</th>
                <th>License Plate</th>
                <th>Status</th>
                </tr>
              </thead>
            <tbody>
              <tr v-for="ticket in syncedTickets" :key="ticket.WE_ID">
                <td>{{ ticket.WE_ID.substring(0, 12) }}...</td>
                <td>{{ ticket.server_id }}</td>
                <td>{{ ticket.WE_LICENSE }}</td>
                <td><span class="status-tag synced">{{ ticket.sync_status }}</span></td>
              </tr>
              <tr v-if="!syncedTickets.length">
                <td colspan="4" class="text-center">No synced tickets found in local data.</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  </template>
  
  <script setup>
import { ref, watch, computed } from 'vue';
  
  const props = defineProps({
  isVisible: Boolean,
  apiUrl: String,
  offlineApiUrl: String,
});

const emit = defineEmits(['close', 'sync-completed']);

const localTickets = ref([]);
const isLoading = ref(false);
const error = ref(null);
const syncProgress = ref(0);

const unsyncedTickets = computed(() => 
  localTickets.value.filter(t => t.sync_status !== 'synced')
);
const syncedTickets = computed(() => 
  localTickets.value.filter(t => t.sync_status === 'synced')
);


async function fetchLocalData() {
  isLoading.value = true;
  error.value = null;
  try {
    // Fetch both open and completed tickets from local server
    const [openRes, completedRes] = await Promise.all([
      fetch(`${props.offlineApiUrl}/api/tickets/`),
      fetch(`${props.offlineApiUrl}/api/tickets/completed`),
    ]);

    if (!openRes.ok || !completedRes.ok) {
      throw new Error('Failed to fetch local data.');
    }

    const openTickets = await openRes.json();
    const completedTickets = await completedRes.json();
    
    localTickets.value = [...openTickets, ...completedTickets];

  } catch (err) {
    console.error('Error fetching local data:', err);
    error.value = 'Could not connect to the local data server. Is the RS232 client running?';
    localTickets.value = [];
  } finally {
    isLoading.value = false;
  }
}

async function syncAllData() {
    isLoading.value = true;
    error.value = null;
    syncProgress.value = 0;
    
    const ticketsToSync = [...unsyncedTickets.value];

    for (const ticket of ticketsToSync) {
        try {
            let response;
            if (ticket.sync_status === 'new') {
                // Sync new ticket
                response = await fetch(`${props.apiUrl}/api/tickets/`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(ticket),
                });
            } else if (ticket.sync_status === 'updated') {
                 // Sync updated ticket
                const payload = { WE_WEIGHTOUT: ticket.WE_WEIGHTOUT };
                response = await fetch(`${props.apiUrl}/api/tickets/${ticket.server_id}`, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload),
                });
            }

            if (!response.ok) {
                throw new Error(`Failed to sync ticket ${ticket.WE_ID}`);
            }
            
            const syncedTicket = await response.json();

            // Mark as synced in local DB
            await fetch(`${props.offlineApiUrl}/api/tickets/mark-synced`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ local_id: ticket.WE_ID, server_id: syncedTicket.WE_ID }),
            });


        } catch (err) {
            console.error(`Error syncing ticket ${ticket.WE_ID}:`, err);
            error.value = `Error syncing ticket ${ticket.WE_ID}. Please try again.`;
            // Stop on first error
            break; 
        } finally {
            syncProgress.value++;
        }
    }
    
    isLoading.value = false;
    if (!error.value) {
      alert('Sync completed successfully!');
      emit('sync-completed');
    }
    await fetchLocalData(); // Refresh list
}


function closeModal() {
  emit('close');
}

watch(() => props.isVisible, (newValue) => {
  if (newValue) {
    fetchLocalData();
  }
});
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(0, 0, 0, 0.6);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 2000;
}

.modal-content {
  background-color: #fff;
  border-radius: 8px;
  width: 90%;
  max-width: 800px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 5px 15px rgba(0,0,0,0.3);
}

.modal-header {
  padding: 15px 20px;
  border-bottom: 1px solid #eee;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.modal-header h2 {
  margin: 0;
  font-size: 1.25rem;
  color: #333;
}

.close-button {
  background: none;
  border: none;
  font-size: 1.75rem;
  cursor: pointer;
  color: #aaa;
}
.close-button:hover {
    color: #333;
}

.modal-body {
  padding: 20px;
  overflow-y: auto;
}

.sync-controls {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
}

.sync-controls button {
  padding: 10px 15px;
  border: none;
  border-radius: 5px;
  cursor: pointer;
  font-size: 0.9rem;
  font-weight: bold;
  transition: background-color 0.3s;
}

.sync-controls button:disabled {
  background-color: #ccc;
  cursor: not-allowed;
}

.sync-controls button:not(:disabled) {
  background-color: #2196F3;
  color: white;
}
.sync-controls button:not(:disabled):hover {
    background-color: #1976D2;
}

.refresh-button {
    background-color: #757575 !important;
}
.refresh-button:hover {
    background-color: #616161 !important;
}

.error-text {
  color: #D32F2F;
  background-color: #FFCDD2;
  padding: 10px;
  border-radius: 4px;
}

.no-data {
    text-align: center;
    color: #757575;
    padding: 20px;
}
.text-center {
    text-align: center;
    color: #999;
}

.local-data-tables h3 {
    margin-top: 20px;
    margin-bottom: 10px;
    border-bottom: 2px solid #eee;
    padding-bottom: 5px;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}

.data-table th, .data-table td {
  border: 1px solid #ddd;
  padding: 8px;
  text-align: left;
}

.data-table th {
  background-color: #f7f7f7;
  font-weight: bold;
}

.data-table tbody tr:nth-child(even) {
  background-color: #f9f9f9;
}

.status-tag {
    padding: 3px 8px;
    border-radius: 12px;
    font-size: 0.8rem;
    font-weight: bold;
    color: white;
}
.status-tag.new {
    background-color: #FF9800; /* Orange */
}
.status-tag.updated {
    background-color: #2196F3; /* Blue */
}
.status-tag.synced {
    background-color: #4CAF50; /* Green */
}
</style>