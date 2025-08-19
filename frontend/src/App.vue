<script setup>
import TicketDetailModal from './components/TicketDetailModal.vue'
import CreateTicketModal from './components/CreateTicketModal.vue' 
import { ref, onMounted, computed, watch } from 'vue' 


const currentWeight = ref('0')
const openTickets = ref([])
const completedTickets = ref([])
const apiError = ref(null)
const wsStatus = ref('Connecting...')
const activeTab = ref('inProgress')
const carQueue = ref([]);

const selectedDate = ref(new Date().toISOString().split('T')[0]);

// State สำหรับ Inline Editing
const selectedTicketId = ref(null) // <-- State ใหม่: เก็บ ID ของบัตรที่ถูกเลือก

// State สำหรับ Modal (ยังคงใช้สำหรับดูรายละเอียด)
const detailTicket = ref(null)     // <-- เปลี่ยนชื่อจาก selectedTicket
const isModalVisible = ref(false)

// State สำหรับ Loading
const isCreatingTicket = ref(false)
const isUpdatingTicket = ref(false)
const isCancellingTicket = ref(false) 

const isCreateModalVisible = ref(false);
const initialWeightForNewTicket = ref(0);

// --- Computed Property ใหม่ ---
// หาข้อมูลของบัตรที่ถูกเลือกจาก openTickets
const selectedTicketObject = computed(() => {
  if (!selectedTicketId.value) return null;
  return openTickets.value.find(t => t.WE_ID === selectedTicketId.value);
});

const weightFontSize = computed(() => {
  const len = (currentWeight.value || '').toString().length;
  if (len <= 6) return '6.7rem';
  if (len <= 8) return '6rem';
  if (len <= 10) return '5rem';
  return '4rem';
});


const API_BASE_URL = 'http://localhost:8000'

// --- WebSocket Configuration ---
// URL ของ Agent ที่เรารันไว้ (ws://127.0.0.1:8765)
const WEBSOCKET_URL = 'ws://localhost:8765'

// --- Functions ---

/**
 * ฟังก์ชันสำหรับดึงข้อมูลบัตรชั่งที่ยังไม่เสร็จจาก Backend API
 */


async function fetchOpenTickets(dateStr) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/tickets/?target_date=${dateStr}`)
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
    openTickets.value = await response.json()
  } catch (error) {
    console.error("Could not fetch open tickets:", error)
    apiError.value = "ไม่สามารถดึงข้อมูลบัตรชั่ง 'กำลังดำเนินการ' ได้"
  }
}

async function fetchCompletedTickets(dateStr) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/tickets/completed?target_date=${dateStr}`)
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
    completedTickets.value = await response.json()
  } catch (error) {
    console.error("Could not fetch completed tickets:", error)
    apiError.value = "ยังไม่มีรายการชั่งชั่งเข้า"
  }
}

async function showTicketDetails(ticket_id) {
  selectTicket(ticket_id);
  // ไม่ต้องเปิด Modal หรือเคลียร์ค่าที่นี่ก่อน
  try {
    const response = await fetch(`${API_BASE_URL}/api/tickets/${ticket_id}`);
    if (!response.ok) throw new Error(`Ticket not found`);
    
    // เมื่อ fetch สำเร็จแล้ว ค่อยมาอัปเดต state และเปิด Modal
    detailTicket.value = await response.json();
    isModalVisible.value = true; // เปิด Modal ที่นี่

  } catch (error) {
    console.error("Failed to fetch ticket details:", error);
    alert("ไม่สามารถดึงข้อมูลรายละเอียดได้");
    // ไม่ต้องทำอะไรกับ Modal ถ้า fetch ล้มเหลว
  }
}
async function fetchCarQueue() {
  try {
    const response = await fetch(`${API_BASE_URL}/api/car-queue/`);
    if (!response.ok) throw new Error('Could not fetch car queue');
    carQueue.value = await response.json();
  } catch (error) {
    console.error(error);
    // อาจจะแสดง error ให้ผู้ใช้เห็นในอนาคต
  }
}


function closeModal() {
  isModalVisible.value = false
  detailTicket.value = null
}

// --- ฟังก์ชันใหม่สำหรับ Inline Editing ---
function selectTicket(ticketId) {
  // ถ้าคลิกซ้ำที่แถวเดิม ให้ยกเลิกการเลือก
  if (selectedTicketId.value === ticketId) {
    selectedTicketId.value = null;
  } else {
    selectedTicketId.value = ticketId;
  }
}


/**
 * ฟังก์ชันสำหรับเชื่อมต่อ WebSocket
 */
function connectWebSocket() {
  const ws = new WebSocket(WEBSOCKET_URL)

  ws.onopen = () => {
    console.log("WebSocket connected.")
    wsStatus.value = "Connected"
  }

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      if (data.hasOwnProperty('weight')) {
        // จัดรูปแบบตัวเลขให้มี comma
        currentWeight.value = parseInt(data.weight).toLocaleString('en-US')
      }
    } catch (e) {
      console.error("Error parsing WebSocket message:", e)
    }
  }

  ws.onclose = () => {
    console.log("WebSocket disconnected. Reconnecting...")
    wsStatus.value = "Disconnected. Retrying..."
    // พยายามเชื่อมต่อใหม่ทุกๆ 3 วินาที
    setTimeout(connectWebSocket, 3000)
  }

  ws.onerror = (error) => {
    console.error("WebSocket error:", error)
    wsStatus.value = "Connection Error"
    ws.close() // การปิดจะทำให้ onclose ทำงานและพยายามเชื่อมต่อใหม่
  }
}

watch(selectedDate, async (newDate) => {
  apiError.value = null; // เคลียร์ error เก่า
  // เมื่อวันที่เปลี่ยน ให้โหลดข้อมูลของทั้งสองตารางใหม่
  await Promise.all([
    fetchOpenTickets(newDate),
    fetchCompletedTickets(newDate)
  ]);
});

// --- Lifecycle Hook ---
// onMounted คือฟังก์ชันที่จะถูกเรียกใช้งานแค่ 1 ครั้ง
// หลังจากที่หน้าเว็บถูกสร้างขึ้นมาเสร็จสมบูรณ์
async function fetchInitialData() {
  await Promise.all([
    fetchOpenTickets(selectedDate.value),
    fetchCompletedTickets(selectedDate.value)
  ]);
}

onMounted(() => {
  fetchInitialData(); // <-- เรียกฟังก์ชันใหม่
  connectWebSocket();
});

// --- เพิ่มฟังก์ชันใหม่สำหรับสร้างบัตรชั่ง ---
async function handleCreateTicket(ticketData) {
  isCreatingTicket.value = true; // ยังคงใช้ isCreatingTicket สำหรับ loading

  try {
    // ใช้ ticketData ที่ส่งมาจาก Modal
    const response = await fetch(`${API_BASE_URL}/api/tickets/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(ticketData), 
    });

    if (!response.ok) throw new Error('Server error!');

    alert('สร้างบัตรชั่งใหม่สำเร็จ!');
    isCreateModalVisible.value = false; // ปิด Modal
    await fetchOpenTickets(selectedDate.value);
    
  } catch (error) {
    console.error('Failed to create ticket:', error);
    alert('เกิดข้อผิดพลาดในการสร้างบัตรชั่ง');
  } finally {
    isCreatingTicket.value = false;
  }
}

// --- ปรับปรุง handleWeighOut ---
async function handleWeighOut() {
  // ตรวจสอบว่ามีบัตรถูกเลือกอยู่หรือไม่
  if (!selectedTicketId.value) {
    alert('กรุณาเลือกบัตรชั่งที่ต้องการบันทึก');
    return;
  }

  const weightOutValue = parseInt(currentWeight.value.replace(/,/g, ''), 10);
  if (isNaN(weightOutValue)) {
     alert('ค่าน้ำหนักปัจจุบันไม่ถูกต้อง');
     return;
  }

  isUpdatingTicket.value = true;
  const ticketIdToUpdate = selectedTicketId.value;

  try {
    const response = await fetch(`${API_BASE_URL}/api/tickets/${ticketIdToUpdate}/weigh-out`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ WE_WEIGHTOUT: weightOutValue }),
    });

    if (!response.ok) throw new Error('Server error during weigh-out!');

    alert('บันทึกน้ำหนักชั่งออกสำเร็จ!');
    selectedTicketId.value = null; // ยกเลิกการเลือกบัตร

    await Promise.all([ fetchOpenTickets(), fetchCompletedTickets() ]);

  } catch (error) {
    console.error('Failed to update weigh-out:', error);
    alert('เกิดข้อผิดพลาดในการบันทึกน้ำหนักชั่งออก');
  } finally {
    isUpdatingTicket.value = false;
  }
}
async function handleCancelTicket() {
  if (!selectedTicketId.value) {
    alert('กรุณาเลือกบัตรชั่งที่ต้องการยกเลิก');
    return;
  }

  // ยืนยันเพื่อความปลอดภัย
  if (!confirm(`คุณต้องการยกเลิกบัตรชั่งเลขที่ ${selectedTicketId.value} ใช่หรือไม่?`)) {
    return; // ถ้าผู้ใช้กด Cancel ให้ออกจากฟังก์ชัน
  }

  isCancellingTicket.value = true;
  const ticketIdToCancel = selectedTicketId.value;

  try {
    const response = await fetch(`${API_BASE_URL}/api/tickets/${ticketIdToCancel}/cancel`, {
      method: 'DELETE', // <-- ใช้ method DELETE
    });

    if (!response.ok) {
      throw new Error('Server error during cancellation!');
    }

    alert('ยกเลิกบัตรชั่งสำเร็จ!');
    selectedTicketId.value = null; // ยกเลิกการเลือกบัตร

    // โหลดข้อมูลตาราง "กำลังดำเนินการ" ใหม่อย่างเดียวก็พอ
    await fetchOpenTickets(selectedDate.value);

  } catch (error) {
    console.error('Failed to cancel ticket:', error);
    alert('เกิดข้อผิดพลาดในการยกเลิกบัตรชั่ง');
  } finally {
    isCancellingTicket.value = false;
  }
}
// ---------------------------------------------
async function handleTicketUpdate(updatedTicketData) {
  const ticketId = updatedTicketData.WE_ID;

  // สร้าง object ที่จะส่งไป API
  const payload = {
    WE_LICENSE: updatedTicketData.WE_LICENSE,
  };

  try {
    const response = await fetch(`${API_BASE_URL}/api/tickets/${ticketId}`, {
      // V V V V V V V V V V V V V V V V V V V V V
      // ใส่เนื้อหาที่ถูกต้องกลับเข้ามาที่นี่
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      // ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^
    });

    if (!response.ok) {
      throw new Error('Failed to update ticket');
    }

    alert('แก้ไขข้อมูลสำเร็จ!');
    
    // เรียกใช้ฟังก์ชัน refresh
    await refreshTicketData(ticketId);
    
  } catch (error) {
    console.error('Error updating ticket:', error);
    alert('เกิดข้อผิดพลาดในการแก้ไขข้อมูล');
  }
}

async function refreshTicketData(ticketId) {
  // ปิด Modal ก่อน
  closeModal(); 

  // รอสักครู่เพื่อให้ UI ตอบสนอง
  await new Promise(resolve => setTimeout(resolve, 100));

  // โหลดข้อมูลตารางหลักใหม่
  await Promise.all([
      fetchOpenTickets(selectedDate.value),
      fetchCompletedTickets(selectedDate.value)
  ]);
  
  // เปิด Modal ของบัตรใบเดิมขึ้นมาใหม่ เพื่อให้เห็นข้อมูลที่อัปเดต
  await showTicketDetails(ticketId);
}

// --- เพิ่มฟังก์ชันใหม่สำหรับเปิด Modal ---
async function openCreateTicketModal() {
  // 1. โหลดข้อมูลคิวล่าสุดทุกครั้งที่เปิด
  await fetchCarQueue();

  // 2. อ่านค่าน้ำหนักปัจจุบัน
  const weightValue = parseInt(currentWeight.value.replace(/,/g, ''), 10);
  if (isNaN(weightValue)) {
     alert('ค่าน้ำหนักไม่ถูกต้อง');
     return;
  }
  initialWeightForNewTicket.value = weightValue;
  isCreateModalVisible.value = true;
}
// ------------------------------------

</script>

<template>
  <div class="app-container">
    <main>
      <div class="left-panel card">
        <!-- ส่วนแสดงน้ำหนัก Real-time -->
        <div class="weight-display-container">
          <div class="weight-display">
            <span :style="{ fontSize: weightFontSize }">{{ currentWeight }}</span>
          </div>
        </div>

        <!-- เส้นแบ่ง -->
        <hr class="divider">
        <div class="create-ticket-panel">
          <button @click="openCreateTicketModal" class="create-ticket-button">
            สร้างบัตรชั่งใหม่
          </button>
        </div>

        <!-- ส่วน Action Panel -->
        <div class="action-panel">
          <div class="selected-ticket-info">
            <label>บัตรที่เลือก:</label>
            <div v-if="selectedTicketObject" class="ticket-id-display">
              {{ selectedTicketObject.WE_ID }} ({{ selectedTicketObject.WE_LICENSE }})
            </div>
            <div v-else class="no-ticket-selected">
              - ยังไม่ได้เลือก -
            </div>
          </div>
          <button 
            class="weigh-out-button"
            @click="handleWeighOut"
            :disabled="!selectedTicketId || isUpdatingTicket"
          >
            {{ isUpdatingTicket ? 'กำลังบันทึก...' : 'บันทึกน้ำหนักชั่งออก' }}
          </button>
          <button 
            class="cancel-button"
            @click="handleCancelTicket"
            :disabled="!selectedTicketId || isUpdatingTicket || isCancellingTicket"
          >
            {{ isCancellingTicket ? 'กำลังยกเลิก...' : 'ยกเลิกบัตรชั่ง' }}
          </button>
        </div>

        <!-- เส้นแบ่ง -->
        <hr class="divider">

        <!-- ฟอร์มสร้างบัตรชั่งใหม่ -->
        <div class="create-ticket-form">
          <form @submit.prevent="handleCreateTicket">
            <div class="form-group">
              <label for="license-plate">ทะเบียนรถ</label>
              <input 
                id="license-plate"
                type="text" 
                v-model="newTicketLicense"
                placeholder="กรอกทะเบียนรถ..."
                required
              >
            </div>
            <div class="form-group">
              <label for="vendor-name">ชื่อลูกค้า</label>
              <input id="vendor-name" type="text" v-model="newTicketVendor">
            </div>
            <div class="form-group">
              <label for="material-name">ชื่อสินค้า (กรณีชั่งแยก)</label>
              <input id="material-name" type="text" v-model="newTicketMaterial">
            </div>
            <button type="submit" :disabled="isCreatingTicket">
              {{ isCreatingTicket ? 'กำลังบันทึก...' : 'บันทึกการชั่งเข้า' }}
            </button>
          </form>
        </div>
      </div>

      <div class="right-panel card">
        <!-- Tabs สำหรับสลับมุมมอง -->
        <div class="date-filter-container">
          <label for="date-filter">เลือกวันที่:</label>
          <input type="date" id="date-filter" v-model="selectedDate">
        </div>
        <div class="tabs">
          <button :class="{ active: activeTab === 'inProgress' }" @click="activeTab = 'inProgress'">
            กำลังดำเนินการ ({{ openTickets.length }})
          </button>
          <button :class="{ active: activeTab === 'completed' }" @click="activeTab = 'completed'">
            เสร็จสิ้นแล้ว ({{ completedTickets.length }})
          </button>
        </div>

        <!-- แสดงข้อความ Error ถ้ามี -->
        <div v-if="apiError" class="error-message">{{ apiError }}</div>

        <!-- ส่วนแสดงตาราง -->
        <div class="table-container" v-else>
          <!-- ตารางสำหรับบัตรกำลังดำเนินการ -->
          <div v-show="activeTab === 'inProgress'">
            <table>
              <thead>
                <tr>
                  <th>เลขที่บัตร</th>
                  <th>ทะเบียนรถ</th>
                  <th>ชื่อลูกค้า</th>
                  <th>เวลาชั่งเข้า</th>
                  <th>น้ำหนักชั่งเข้า (กก.)</th>
                </tr>
              </thead>
              <tbody>
                <tr 
                  v-for="ticket in openTickets" 
                  :key="ticket.WE_ID" 
                  @click="selectTicket(ticket.WE_ID)" 
                  :class="{ 'clickable-row': true, 'active-row': selectedTicketId === ticket.WE_ID }"
                >
                  <td>
                    <button class="detail-btn" @click.stop="showTicketDetails(ticket.WE_ID)">ดู</button>
                    {{ ticket.WE_ID }}
                  </td>
                  <td>{{ ticket.WE_LICENSE }}</td>
                  <td>{{ ticket.WE_VENDOR || '-' }}</td>
                  <td>{{ new Date(ticket.WE_TIMEIN).toLocaleString('th-TH') }}</td>
                  <td>{{ ticket.WE_WEIGHTIN.toLocaleString('en-US') }}</td>
                </tr>
                <tr v-if="!apiError && openTickets.length === 0">
                  <td colspan="5" style="text-align: center;">ไม่พบรายการ</td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- ตารางสำหรับบัตรที่เสร็จแล้ว -->
          <div v-show="activeTab === 'completed'">
            <table>
              <thead>
                <tr>
                  <th>เลขที่บัตร</th>
                  <th>ทะเบียนรถ</th>
                  <th>ชื่อลูกค้า</th>
                  <th>เวลาชั่งออก</th>
                  <th>น้ำหนักสุทธิ (กก.)</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="ticket in completedTickets" :key="ticket.WE_ID" @click="showTicketDetails(ticket.WE_ID)" class="clickable-row">
                  <td>
                    <button class="detail-btn" @click.stop="showTicketDetails(ticket.WE_ID)">ดู</button>
                    {{ ticket.WE_ID }}
                  </td>
                  <td>{{ ticket.WE_LICENSE }}</td>
                  <td>{{ ticket.WE_VENDOR || '-' }}</td>
                  <td>{{ new Date(ticket.WE_TIMEOUT).toLocaleString('th-TH') }}</td>
                  <td>{{ ticket.WE_WEIGHTNET?.toLocaleString('en-US') || '0' }}</td>
                </tr>
                <tr v-if="!apiError && completedTickets.length === 0">
                  <td colspan="5" style="text-align: center;">ไม่พบรายการของวันนี้</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </main>
    
    <!-- Modal Component สำหรับแสดงรายละเอียด -->
    <TicketDetailModal 
    :visible="isModalVisible" 
    :ticket="detailTicket"
    @close="closeModal"
    @weigh-out="handleWeighOut"
    @ticket-updated="refreshTicketData(detailTicket.WE_ID)"
    />
    <CreateTicketModal
      :visible="isCreateModalVisible"
      :initial-weight-in="initialWeightForNewTicket"
      :car-queue="carQueue"
      @close="isCreateModalVisible = false"
      @save="handleCreateTicket"
    />
  </div>
</template>

<style scoped>
/* =============================================== */
/* 1. CSS Variables & Global Styles              */
/* =============================================== */
/* src/assets/main.css */
:root {
    --primary-color: #000000; /* สีที่ต้องการ */
    --secondary-color: #35495e;
    --bg-color: #f0f2f5;
    --text-color: #2c3e50;
    --card-bg: #ffffff;
    --error-color: #e53935;
    --danger-color: #f44336;
    --danger-hover-color: #d32f2f;
    --highlight-color: #d1ecf1;
}

html, body, #app {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
    height: 100%;
    overflow: hidden; /* ป้องกัน scrollbar ที่ body */
    background-color: #f0f2f5; /* ย้ายสีพื้นหลังมาไว้ที่นี่ */
    font-family: sans-serif;
}
/* =============================================== */
/* 2. Main Layout (โครงสร้างหลัก)                 */
/* =============================================== */
.app-container {
  display: flex;
  flex-direction: column;
  height: 100vh; /* ทำให้แอปสูงเต็มหน้าจอ */
  background-color: var(--bg-color);
}

main {
  display: flex;
  gap: 1.5rem;
  padding: 1.5rem;
  flex-grow: 1;
  overflow: hidden;
}

.left-panel {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  width: 360px; 
  flex-shrink: 0;
  overflow-y: auto;
  padding-right: 10px;
}

.right-panel {
  flex-grow: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* =============================================== */
/* 3. Reusable Components                          */
/* =============================================== */
.card {
  background-color: var(--card-bg);
  padding: 1.5rem;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.divider {
  border: none;
  border-top: 1px solid #eee;
  margin: 0.5rem 0;
}

.error-message {
  color: var(--error-color);
  background-color: #ffcdd2;
  border: 1px solid var(--error-color);
  padding: 1rem;
  border-radius: 4px;
}

/* =============================================== */
/* 4. Left Panel Components                        */
/* =============================================== */

.weight-display {
  font-size: 7rem;
  font-weight: bold;
  color: #000000; /* เปลี่ยนสีฟ้อนที่นี่ */
  background-color: #eef7f3;
  padding: 1.5rem;
  border-radius: 8px;
  text-align: center; 
  display: flex;
  justify-content: center;
  align-items: center;
  overflow: hidden;
  line-height: 1;
}

.action-panel {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
/* เพิ่ม Style ใหม่ */
.action-buttons {
  display: flex;
  gap: 0.5rem; /* ระยะห่างระหว่างปุ่ม */
}
/* Style สำหรับปุ่มยกเลิก */
button.cancel-button {
  background-color: #757575; /* สีเทา */
}
button.cancel-button:hover:not(:disabled) {
  background-color: #616161;
}

.selected-ticket-info {
  background-color: #f0f2f5;
  padding: 0.8rem;
  border-radius: 4px;
}
.selected-ticket-info label {
  font-weight: bold;
  display: block;
  font-size: 0.9rem;
  color: #666;
}
.ticket-id-display {
  font-weight: bold;
  font-size: 1.2rem;
  color: var(--primary-color);
}
.no-ticket-selected {
  font-style: italic;
  color: #888;
}
.form-group {
  margin-bottom: 1rem;
}
.form-group label {
  display: block;
  font-weight: bold;
  margin-bottom: 0.5rem;
}
.form-group input {
  width: 100%;
  padding: 0.8rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 1rem;
  box-sizing: border-box;
}
.weight-preview {
  font-size: 1.5rem;
  font-weight: bold;
  color: var(--primary-color);
  background-color: #f0f2f5;
  padding: 0.8rem;
  border-radius: 4px;
  text-align: right;
}

button.weigh-out-button {
  background-color: var(--danger-color, #f44336);
}
button.weigh-out-button:hover:not(:disabled) {
  background-color: var(--danger-hover-color, #d32f2f);
}
.create-ticket-form button[type="submit"] {
  background-color: var(--primary-color, #42b883);
}

.create-ticket-form button[type="submit"]:hover:not(:disabled) {
  background-color: #36a474;
}

button.weigh-out-button,
button.cancel-button {
  width: 100%;
  padding: 1rem;
  color: white;
  border: none;
  border-radius: 4px;
  font-size: 1.1rem;
  font-weight: bold;
  cursor: pointer;
  transition: background-color 0.2s;
}
button:disabled {
  background-color: #ccc;
  cursor: not-allowed;
}
.create-ticket-form button[type="submit"] {
  width: 100%;
  padding: 1rem;
  color: white;
  border: none;
  border-radius: 4px;
  font-size: 1.1rem;
  font-weight: bold;
  cursor: pointer;
  transition: background-color 0.2s;
  background-color: var(--primary-color, #42b883); /* <-- ยืนยันสีเขียวที่นี่ */
}


/* =============================================== */
/* 5. Right Panel Components                       */
/* =============================================== */
.date-filter-container {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 1rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid #eee;
  flex-shrink: 0;
}
.date-filter-container label {
  font-weight: bold;
}
.date-filter-container input[type="date"] {
  padding: 0.5rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 1rem;
}

.tabs {
  display: flex;
  border-bottom: 2px solid #ddd;
  margin-bottom: 1rem;
  flex-shrink: 0;
}
.tabs button {
  padding: 0.8rem 1.2rem;
  border: none;
  background-color: transparent;
  cursor: pointer;
  font-size: 1rem;
  color: #666;
  position: relative;
  top: 2px;
}
.tabs button.active {
  border-bottom: 2px solid var(--primary-color);
  font-weight: bold;
  color: var(--primary-color);
}

/* --- Table Styles --- */
.table-container {
  flex-grow: 1;
  overflow-y: auto;
  min-height: 0; /* <-- จุดแก้ไขสำคัญยังคงอยู่ */
}
table {
  width: 100%;
  border-collapse: collapse;
}
th, td {
  padding: 0.8rem 1rem;
  border-bottom: 1px solid #ddd;
  text-align: left;
  white-space: nowrap;
}
th {
  background-color: #f9fafb;
  position: sticky;
  top: 0;
}
.clickable-row {
  cursor: pointer;
  transition: background-color 0.2s ease;
}
.clickable-row:hover {
  background-color: #f0f8ff;
}
.active-row {
  background-color: var(--highlight-color) !important;
  font-weight: bold;
}
.detail-btn {
  margin-right: 0.5rem;
  padding: 0.2rem 0.5rem;
  font-size: 0.8rem;
  cursor: pointer;
}

.weight-display span {
  display: block;
  max-width: 100%;
  white-space: nowrap;
}

.create-ticket-button {
  width: 100%;
  padding: 1rem;
  color: white;
  border: none;
  border-radius: 4px;
  font-size: 1.1rem;
  font-weight: bold;
  cursor: pointer;
  transition: background-color 0.2s;
  background-color: var(--primary-color);
}
.create-ticket-button:hover {
  background-color: #36a474;
}

</style>