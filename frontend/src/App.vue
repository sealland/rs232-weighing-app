<script setup>
import TicketDetailModal from './components/TicketDetailModal.vue'
import { ref, onMounted, computed } from 'vue' 

const currentWeight = ref('0')
const openTickets = ref([])
const completedTickets = ref([])
const apiError = ref(null)
const wsStatus = ref('Connecting...')
const activeTab = ref('inProgress')


// State สำหรับ Inline Editing
const selectedTicketId = ref(null) // <-- State ใหม่: เก็บ ID ของบัตรที่ถูกเลือก

// State สำหรับ Modal (ยังคงใช้สำหรับดูรายละเอียด)
const detailTicket = ref(null)     // <-- เปลี่ยนชื่อจาก selectedTicket
const isModalVisible = ref(false)

// State สำหรับ Loading
const isCreatingTicket = ref(false)
const isUpdatingTicket = ref(false)

// --- Computed Property ใหม่ ---
// หาข้อมูลของบัตรที่ถูกเลือกจาก openTickets
const selectedTicketObject = computed(() => {
  if (!selectedTicketId.value) return null;
  return openTickets.value.find(t => t.WE_ID === selectedTicketId.value);
});



const API_BASE_URL = 'http://localhost:8000'

// --- WebSocket Configuration ---
// URL ของ Agent ที่เรารันไว้ (ws://127.0.0.1:8765)
const WEBSOCKET_URL = 'ws://localhost:8765'

// --- Functions ---

/**
 * ฟังก์ชันสำหรับดึงข้อมูลบัตรชั่งที่ยังไม่เสร็จจาก Backend API
 */

 // สร้างวันที่ของวันนี้ในรูปแบบ YYYY-MM-DD
const todayDateString = computed(() => {
  const today = new Date();
  return today.toISOString().split('T')[0];
});

async function fetchOpenTickets() {
  try {
    const response = await fetch(`${API_BASE_URL}/api/tickets/`)
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    const data = await response.json()
    openTickets.value = data // นำข้อมูลที่ได้ไปใส่ในตัวแปร openTickets
    apiError.value = null // เคลียร์ error ถ้าสำเร็จ
  } catch (error) {
    console.error("Could not fetch tickets:", error)
    apiError.value = "ไม่สามารถดึงข้อมูลบัตรชั่งได้ กรุณาตรวจสอบ Backend API"
  }
}

async function fetchCompletedTickets() {
  try {
    // เรียก API ใหม่โดยใช้วันที่ของวันนี้
    const response = await fetch(`${API_BASE_URL}/api/tickets/completed?target_date=${todayDateString.value}`)
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
    completedTickets.value = await response.json()
  } catch (error) {
    console.error("Could not fetch completed tickets:", error)
    apiError.value = "ไม่สามารถดึงข้อมูลบัตรชั่ง 'เสร็จสิ้นแล้ว' ได้"
  }
}

async function showTicketDetails(ticket_id) {
  isModalVisible.value = true
  detailTicket.value = null
  try {
    const response = await fetch(`${API_BASE_URL}/api/tickets/${ticket_id}`)
    if (!response.ok) throw new Error(`Ticket not found`)
    detailTicket.value = await response.json()
  } catch (error) {
    console.error("Failed to fetch ticket details:", error)
    alert("ไม่สามารถดึงข้อมูลรายละเอียดได้")
    isModalVisible.value = false
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

// --- Lifecycle Hook ---
// onMounted คือฟังก์ชันที่จะถูกเรียกใช้งานแค่ 1 ครั้ง
// หลังจากที่หน้าเว็บถูกสร้างขึ้นมาเสร็จสมบูรณ์
onMounted(() => {
  fetchOpenTickets()
  fetchCompletedTickets()
  connectWebSocket()
})

// --- เพิ่มฟังก์ชันใหม่สำหรับสร้างบัตรชั่ง ---
async function handleCreateTicket() {
  // ตรวจสอบข้อมูลเบื้องต้น
  if (!newTicketLicense.value.trim()) {
    alert('กรุณากรอกทะเบียนรถ');
    return;
  }
  
  // แปลงค่าน้ำหนักปัจจุบันกลับเป็นตัวเลข (เอา comma ออก)
  const weightValue = parseInt(currentWeight.value.replace(/,/g, ''), 10);
  if (isNaN(weightValue)) {
     alert('ค่าน้ำหนักไม่ถูกต้อง');
     return;
  }

  isCreatingTicket.value = true; // เริ่มสถานะ loading

  try {
    const response = await fetch(`${API_BASE_URL}/api/tickets/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        WE_LICENSE: newTicketLicense.value,
        WE_WEIGHTIN: weightValue,
      }),
    });

    if (!response.ok) {
      throw new Error('Server responded with an error!');
    }

    // เมื่อสร้างสำเร็จ
    alert('สร้างบัตรชั่งใหม่สำเร็จ!');
    newTicketLicense.value = ''; // ล้างค่าในฟอร์ม
    await fetchOpenTickets(); // โหลดข้อมูลตารางใหม่เพื่อให้เห็นบัตรล่าสุด
    
  } catch (error) {
    console.error('Failed to create ticket:', error);
    alert('เกิดข้อผิดพลาดในการสร้างบัตรชั่ง');
  } finally {
    isCreatingTicket.value = false; // สิ้นสุดสถานะ loading
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
</script>

<template>
  <div class="app-container">
    <main>
      <div class="left-panel card">
        <!-- ส่วนแสดงน้ำหนัก Real-time -->
        <div class="weight-display-container">
          <h2>น้ำหนักปัจจุบัน</h2>
          <div class="weight-display">
            <span>{{ currentWeight }}</span>
          </div>
        </div>

        <!-- เส้นแบ่ง -->
        <hr class="divider">

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
              <label>น้ำหนักชั่งเข้า (จากตาชั่ง)</label>
              <div class="weight-preview">{{ currentWeight }} กก.</div>
            </div>
            <button type="submit" :disabled="isCreatingTicket">
              {{ isCreatingTicket ? 'กำลังบันทึก...' : 'บันทึกการชั่งเข้า' }}
            </button>
          </form>
        </div>
      </div>

      <div class="right-panel card">
        <!-- Tabs สำหรับสลับมุมมอง -->
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
    />
  </div>
</template>

<style scoped>
/* =============================================== */
/* 1. CSS Variables & Global Styles              */
/* =============================================== */
:root {
  --primary-color: #42b883;
  --secondary-color: #35495e;
  --bg-color: #f0f2f5;
  --text-color: #2c3e50;
  --card-bg: #ffffff;
  --error-color: #e53935;
  --danger-color: #f44336;
  --danger-hover-color: #d32f2f;
  --highlight-color: #d1ecf1;
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

.weight-display-container h2 {
  margin-top: 0;
  border-bottom: 1px solid #eee;
  padding-bottom: 1rem;
  margin-bottom: 1.5rem;
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
.weight-display-container {
  text-align: center;
}
.weight-display {
  font-size: 7rem;
  font-weight: bold;
  color: var(--primary-color);
  background-color: #eef7f3;
  padding: 1.5rem;
  border-radius: 8px;
  margin-top: 1rem;
}
.action-panel {
  display: flex;
  flex-direction: column;
  gap: 1rem;
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
  background-color: var(--danger-color);
}
button.weigh-out-button:hover:not(:disabled) {
  background-color: var(--danger-hover-color);
}
button[type="submit"] {
  background-color: var(--primary-color);
}
button[type="submit"]:hover:not(:disabled) {
  background-color: #36a474;
}
button.weigh-out-button, button[type="submit"] {
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

/* =============================================== */
/* 5. Right Panel Components                       */
/* =============================================== */
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
</style>