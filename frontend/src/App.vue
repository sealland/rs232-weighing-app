<script setup>
import TicketDetailModal from './components/TicketDetailModal.vue'
import { ref, onMounted, computed } from 'vue' 

// --- State Management ---
// สร้างตัวแปรแบบ reactive เพื่อให้หน้าเว็บอัปเดตตามเมื่อค่าเปลี่ยน
const currentWeight = ref('0') // สำหรับเก็บน้ำหนักปัจจุบัน
const openTickets = ref([])     // สำหรับเก็บรายการบัตรชั่ง
const apiError = ref(null)      // สำหรับเก็บข้อความ error จาก API
const wsStatus = ref('Connecting...') // สำหรับสถานะ WebSocket
const completedTickets = ref([]) 
const activeTab = ref('inProgress') 

// --- API Configuration ---
// URL ของ Backend API ที่เรารันไว้ (http://127.0.0.1:8000)
const selectedTicket = ref(null)      // <-- 2. เพิ่ม state สำหรับเก็บข้อมูลบัตรที่ถูกเลือก
const isModalVisible = ref(false)     // <-- 3. เพิ่ม state สำหรับควบคุมการแสดงผล Modal

const newTicketLicense = ref('') // เก็บค่าทะเบียนรถที่กรอก
const isCreatingTicket = ref(false) // ใช้สำหรับแสดงสถานะ loading ตอนกดบันทึก
const isUpdatingTicket = ref(false)


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
  isModalVisible.value = true // เปิด Modal ทันที (จะแสดง Loading...)
  selectedTicket.value = null // เคลียร์ข้อมูลเก่า
  try {
    const response = await fetch(`${API_BASE_URL}/api/tickets/${ticket_id}`)
    if (!response.ok) {
      throw new Error(`Ticket not found or API error: ${response.status}`)
    }
    selectedTicket.value = await response.json() // นำข้อมูลที่ได้มาใส่ใน state
  } catch (error) {
    console.error("Failed to fetch ticket details:", error)
    alert("ไม่สามารถดึงข้อมูลรายละเอียดได้")
    isModalVisible.value = false // ปิด Modal ถ้าเกิด Error
  }
}

// 5. เพิ่มฟังก์ชันสำหรับปิด Modal
function closeModal() {
  isModalVisible.value = false
  selectedTicket.value = null
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
async function handleWeighOut() {
  if (!selectedTicket.value) return;

  // แปลงค่าน้ำหนักปัจจุบันกลับเป็นตัวเลข
  const weightOutValue = parseInt(currentWeight.value.replace(/,/g, ''), 10);
  if (isNaN(weightOutValue)) {
     alert('ค่าน้ำหนักปัจจุบันไม่ถูกต้อง');
     return;
  }

  isUpdatingTicket.value = true; // เริ่มสถานะ loading
  const ticketId = selectedTicket.value.WE_ID;

  try {
    const response = await fetch(`${API_BASE_URL}/api/tickets/${ticketId}/weigh-out`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        WE_WEIGHTOUT: weightOutValue,
      }),
    });

    if (!response.ok) {
      throw new Error('Server responded with an error during weigh-out!');
    }

    alert('บันทึกน้ำหนักชั่งออกสำเร็จ!');
    closeModal(); // ปิด Modal หลังจากสำเร็จ

    // โหลดข้อมูลทั้งสองตารางใหม่ เพื่อให้บัตรย้ายจาก "กำลังดำเนินการ" -> "เสร็จสิ้นแล้ว"
    // ใช้ Promise.all เพื่อให้โหลดพร้อมกัน
    await Promise.all([
      fetchOpenTickets(),
      fetchCompletedTickets()
    ]);

  } catch (error) {
    console.error('Failed to update weigh-out:', error);
    alert('เกิดข้อผิดพลาดในการบันทึกน้ำหนักชั่งออก');
  } finally {
    isUpdatingTicket.value = false; // สิ้นสุดสถานะ loading
  }
}
</script>

<template>
  <header>
    <h1>ระบบชั่งน้ำหนัก</h1>
    <div class="status-bar">
      สถานะ WebSocket: <span :class="wsStatus.toLowerCase().replace(/\s/g, '-')">{{ wsStatus }}</span>
    </div>
  </header>

  <main>
    <div class="left-panel">
      <!-- ส่วนแสดงน้ำหนัก Real-time -->
      <div class="weight-display-container card">
        <h2>น้ำหนักปัจจุบัน</h2>
        <div class="weight-display">
          <span>{{ currentWeight }}</span>
        </div>
      </div>
      
      <!-- ฟอร์มสร้างบัตรชั่งใหม่ -->
      <div class="create-ticket-form card">
        <h2>สร้างบัตรชั่งใหม่ / ชั่งเข้า</h2>
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

      <!-- ส่วนแสดงตารางตาม activeTab ที่ถูกเลือก -->
      <div v-else>
        <!-- ตารางสำหรับบัตรกำลังดำเนินการ -->
        <div v-show="activeTab === 'inProgress'">
          <table>
            <thead>
              <tr>
                <th>เลขที่บัตร</th>
                <th>ทะเบียนรถ</th>
                <th>เวลาชั่งเข้า</th>
                <th>น้ำหนักชั่งเข้า (กก.)</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="ticket in openTickets" :key="ticket.WE_ID" @click="showTicketDetails(ticket.WE_ID)" class="clickable-row">
                <td>{{ ticket.WE_ID }}</td>
                <td>{{ ticket.WE_LICENSE }}</td>
                <td>{{ new Date(ticket.WE_TIMEIN).toLocaleString('th-TH') }}</td>
                <td>{{ ticket.WE_WEIGHTIN.toLocaleString('en-US') }}</td>
              </tr>
              <tr v-if="!apiError && openTickets.length === 0">
                <td colspan="4" style="text-align: center;">ไม่พบรายการ</td>
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
                <th>เวลาชั่งออก</th>
                <th>น้ำหนักสุทธิ (กก.)</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="ticket in completedTickets" :key="ticket.WE_ID" @click="showTicketDetails(ticket.WE_ID)" class="clickable-row">
                <td>{{ ticket.WE_ID }}</td>
                <td>{{ ticket.WE_LICENSE }}</td>
                <td>{{ new Date(ticket.WE_TIMEOUT).toLocaleString('th-TH') }}</td>
                <td>{{ ticket.WE_WEIGHTNET?.toLocaleString('en-US') || '0' }}</td>
              </tr>
              <tr v-if="!apiError && completedTickets.length === 0">
                <td colspan="4" style="text-align: center;">ไม่พบรายการของวันนี้</td>
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
    :ticket="selectedTicket"
    @close="closeModal"
    @weigh-out="handleWeighOut"
  />
</template>

<style scoped>
/* ส่วนของ CSS เหมือนเดิม แต่เพิ่ม style สำหรับ status bar และ error message */

:root {
  --primary-color: #42b883;
  --secondary-color: #35495e;
  --bg-color: #f0f2f5;
  --text-color: #2c3e50;
  --card-bg: #ffffff;
  --error-color: #e53935;
  --connected-color: #43a047;
  --connecting-color: #f9a825;
}
main {
  display: flex;
  gap: 2rem;
  align-items: flex-start;
}
.left-panel {
  display: flex;
  flex-direction: column;
  gap: 2rem;
  width: 380px; /* กำหนดความกว้างคงที่ */
  flex-shrink: 0;
}
.right-panel {
  flex-grow: 1; /* ให้ตารางยืดขยายเต็มพื้นที่ที่เหลือ */
}

/* ใช้ card style ร่วมกับ tickets-container เดิม */
.card {
  background-color: var(--card-bg);
  padding: 2rem;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

/* CSS สำหรับฟอร์มใหม่ */
.create-ticket-form h2 {
  margin-top: 0;
  border-bottom: 1px solid #eee;
  padding-bottom: 1rem;
  margin-bottom: 1.5rem;
}
.form-group {
  margin-bottom: 1.5rem;
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
button[type="submit"] {
  width: 100%;
  padding: 1rem;
  background-color: var(--primary-color);
  color: white;
  border: none;
  border-radius: 4px;
  font-size: 1.1rem;
  font-weight: bold;
  cursor: pointer;
  transition: background-color 0.2s;
}
button[type="submit"]:hover {
  background-color: #36a474;
}
button[type="submit"]:disabled {
  background-color: #ccc;
  cursor: not-allowed;
}
body {
  background-color: var(--bg-color);
  color: var(--text-color);
  font-family: sans-serif;
  margin: 0;
}

header {
  background-color: var(--secondary-color);
  color: white;
  padding: 1rem 2rem;
  text-align: center;
  position: relative;
}

.tabs {
  display: flex;
  border-bottom: 2px solid #ddd;
  margin-bottom: 1.5rem;
}
.tabs button {
  padding: 1rem 1.5rem;
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
/* 8. เพิ่ม CSS สำหรับแถวที่คลิกได้ */
.clickable-row {
  cursor: pointer;
  transition: background-color 0.2s ease;
}
.clickable-row:hover {
  background-color: #f0f8ff; /* Light blue on hover */
}

.status-bar {
  position: absolute;
  top: 50%;
  right: 2rem;
  transform: translateY(-50%);
  font-size: 0.9rem;
  background-color: rgba(255, 255, 255, 0.1);
  padding: 0.3rem 0.8rem;
  border-radius: 12px;
}
.status-bar .connected { color: var(--connected-color); font-weight: bold; }
.status-bar .connecting...,
.status-bar .disconnected.-retrying... { color: var(--connecting-color); font-weight: bold; }
.status-bar .connection-error { color: var(--error-color); font-weight: bold; }


main {
  display: flex;
  padding: 2rem;
  gap: 2rem;
  align-items: flex-start;
}

.weight-display-container {
  background-color: var(--card-bg);
  padding: 2rem;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  text-align: center;
  min-width: 350px;
}

.weight-display {
  font-size: 4rem;
  font-weight: bold;
  color: var(--primary-color);
  background-color: #eef7f3;
  padding: 2rem;
  border-radius: 8px;
  margin-top: 1rem;
}

.tickets-container {
  flex-grow: 1;
  background-color: var(--card-bg);
  padding: 2rem;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 1rem;
}

th, td {
  padding: 0.8rem 1rem;
  border-bottom: 1px solid #ddd;
  text-align: left;
}

th {
  background-color: #f9fafb;
}

.error-message {
  color: var(--error-color);
  background-color: #ffcdd2;
  border: 1px solid var(--error-color);
  padding: 1rem;
  border-radius: 4px;
  margin-top: 1rem;
}
</style>