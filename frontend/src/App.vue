<script setup>
import { ref, onMounted, computed, watch } from 'vue'
import TicketDetailModal from './components/TicketDetailModal.vue'
import CreateTicketModal from './components/CreateTicketModal.vue'
import OfflineDataModal from './components/OfflineDataModal.vue'; // เพิ่ม Component

const API_BASE_URL = 'http://192.168.132.7:8000';
const API_OFFLINE_URL = 'http://localhost:8080'; // <-- เพิ่ม URL สำหรับ Local API
const WEBSOCKET_URL = 'ws://192.168.132.7:8765';

// --- State Management ---
const currentWeight = ref('0')
const openTickets = ref([])
const completedTickets = ref([])
const apiError = ref(null)
const wsStatus = ref('Connecting...')
const activeTab = ref('inProgress')
const selectedDate = ref(new Date().toISOString().split('T')[0]);

// State for car queue
const carQueue = ref([]);

// State for Inline Editing
const selectedTicketId = ref(null)

// State for Detail Modal
const detailTicket = ref(null)
const isModalVisible = ref(false)

// State for Create Modal
const isCreateModalVisible = ref(false);
const initialWeightForNewTicket = ref(0);

// State for Report Type
const selectedTicketDetail = ref(null)

const continuousWeighingData = ref(null);

// State for Loading Actions
const isCreatingTicket = ref(false)
const isUpdatingTicket = ref(false)
const isCancellingTicket = ref(false)
const isPrintingReport = ref(false)

// --- เพิ่ม State สำหรับ Offline Mode ---
const isOnline = ref(navigator.onLine);
const isOfflineModalVisible = ref(false); // State สำหรับเปิด/ปิด Modal ข้อมูล Offline

// เพิ่ม state สำหรับการเลือกการดำเนินการ
const printAction = ref('preview') // 'preview', 'print', หรือ 'download'

// เพิ่ม state สำหรับ branch prefix
const branchPrefix = ref('WE') // หรือค่าอื่นๆ ตามที่ต้องการ

// --- Computed Property ---
const activeApiUrl = computed(() => {
  return isOnline.value ? API_BASE_URL : API_OFFLINE_URL;
});

const selectedTicketObject = computed(() => {
  if (!selectedTicketId.value) return null;

  // ค้นหาในตาราง 'กำลังดำเนินการ' ก่อน
  let ticket = openTickets.value.find(t => t.WE_ID === selectedTicketId.value);
  if (ticket) return ticket;

  // ถ้าไม่เจอ ให้ไปค้นหาในตาราง 'เสร็จสิ้นแล้ว'
  return completedTickets.value.find(t => t.WE_ID === selectedTicketId.value);
});

// --- ฟังก์ชันสำหรับแสดงประเภทรายงาน ---
function getReportTypeText(ticket) {
  // ตรวจสอบว่ามีรายการสินค้าหรือไม่
  if (ticket && ticket.items && ticket.items.length > 0) {
    return 'ชั่งรวม';
  } else {
    return 'ชั่งแยก';
  }
}

// --- ฟังก์ชันสำหรับจัดรูปแบบเวลา ---
function formatTime(timeString) {
  if (!timeString) return 'N/A';
  
  try {
    // ถ้าเป็น string ให้แปลงเป็น Date object
    const date = new Date(timeString);
    
    // ตรวจสอบว่า date ถูกต้องหรือไม่
    if (isNaN(date.getTime())) {
      return timeString; // ถ้าแปลงไม่ได้ให้คืนค่าเดิม
    }
    
    // จัดรูปแบบเป็น HH:MM:SS
    const hours = date.getHours().toString().padStart(2, '0');
    const minutes = date.getMinutes().toString().padStart(2, '0');
    const seconds = date.getSeconds().toString().padStart(2, '0');
    
    return `${hours}:${minutes}:${seconds}`;
  } catch (error) {
    console.error('Error formatting time:', error);
    return timeString; // ถ้าเกิด error ให้คืนค่าเดิม
  }
}


// --- ฟังก์ชันสำหรับยกเลิกบัตรชั่ง ---
function cancelTicket(ticketId) {
  handleCancelTicket();
}

// --- ฟังก์ชันสำหรับเปิด Continuous Weighing Modal ---
function openContinuousWeighingModal() {
  handleStartContinuousWeighing();
}

// --- ฟังก์ชันสำหรับอัปเดตน้ำหนักออก ---
function updateTicketWeighOut(ticketId) {
  handleWeighOut();
}

// --- ฟังก์ชันสำหรับพิมพ์รายงาน ---
function printReport(ticketId, action) {
  printAction.value = action;
  handlePrintReport();
}

// --- ฟังก์ชันสำหรับปิด Detail Modal ---
function closeDetailModal() {
  closeModal();
}

// --- ฟังก์ชันสำหรับปิด Create Modal ---
function closeCreateModal() {
  closeCreateTicketModal();
}

// --- ฟังก์ชันสำหรับจัดการการอัปเดตบัตรชั่ง ---
function handleUpdateTicket(eventData) {
  console.log("🔧 handleUpdateTicket called with:", eventData);
  console.log("🔧 Event data type:", typeof eventData);
  console.log("🔧 Event data keys:", Object.keys(eventData || {}));
  handleTicketUpdate(eventData);
}

// --- ฟังก์ชันสำหรับรีเฟรชข้อมูลทั้งหมด ---
async function refreshAllData() {
  await Promise.all([
    fetchOpenTickets(selectedDate.value),
    fetchCompletedTickets(selectedDate.value)
  ]);
}

// --- ฟังก์ชันสำหรับจัดการการเปลี่ยนแปลงวันที่ ---
async function onDateChanged() {
  // ตรวจสอบว่ามีวันที่ที่ถูกต้องหรือไม่
  if (!selectedDate.value || selectedDate.value.trim() === '') {
    // ถ้าไม่มีวันที่ ให้ใช้วันที่ปัจจุบัน
    selectedDate.value = new Date().toISOString().split('T')[0];
  }
  
  // ล้าง error ก่อนดึงข้อมูลใหม่
  apiError.value = null;
  
  await refreshAllData();
}

// --- ฟังก์ชันสำหรับดึงข้อมูลตามวันที่ ---
async function fetchDataForDate(dateStr) {
  await Promise.all([
    fetchOpenTickets(dateStr),
    fetchCompletedTickets(dateStr)
  ]);
}

// --- API & WebSocket Config ---
// const API_BASE_URL = 'http://192.168.132.7:8000';
// const WEBSOCKET_URL = 'ws://localhost:8765';

// --- Functions: Data Fetching ---
async function fetchOpenTickets(dateStr) {
  try {
    // ตรวจสอบและใช้วันที่ปัจจุบันถ้า dateStr ว่างหรือไม่ถูกต้อง
    const validDate = dateStr && dateStr.trim() !== '' ? dateStr : new Date().toISOString().split('T')[0];
    
    console.log(`Fetching open tickets for date: ${validDate} from: ${activeApiUrl.value}`);
    
    // สร้าง URL ที่ถูกต้องตาม API specification
    const url = new URL(`${activeApiUrl.value}/api/tickets/`);
    url.searchParams.append('target_date', validDate);
    
    const response = await fetch(url.toString());
    
    if (!response.ok) {
      const errorText = await response.text();
      console.error(`API Error ${response.status}:`, errorText);
      throw new Error(`HTTP error! status: ${response.status} - ${errorText}`);
    }
    
    const data = await response.json();
    openTickets.value = data;
    console.log(`Successfully fetched ${data.length} open tickets`);
  } catch (error) {
    console.error("Could not fetch open tickets:", error)
    apiError.value = "ไม่สามารถดึงข้อมูลบัตรชั่ง 'กำลังดำเนินการ' ได้"
    openTickets.value = []; // ล้างข้อมูลเก่า
  }
}
async function fetchCompletedTickets(dateStr) {
  try {
    // ตรวจสอบและใช้วันที่ปัจจุบันถ้า dateStr ว่างหรือไม่ถูกต้อง
    const validDate = dateStr && dateStr.trim() !== '' ? dateStr : new Date().toISOString().split('T')[0];
    
    console.log(`Fetching completed tickets for date: ${validDate} from: ${activeApiUrl.value}`);
    
    // สร้าง URL ที่ถูกต้องตาม API specification
    const url = new URL(`${activeApiUrl.value}/api/tickets/completed`);
    url.searchParams.append('target_date', validDate);
    
    const response = await fetch(url.toString());
    
    if (!response.ok) {
      const errorText = await response.text();
      console.error(`API Error ${response.status}:`, errorText);
      throw new Error(`HTTP error! status: ${response.status} - ${errorText}`);
    }
    
    const data = await response.json();
    completedTickets.value = data;
    console.log(`Successfully fetched ${data.length} completed tickets`);
  } catch (error) {
    console.error("Could not fetch completed tickets:", error)
    apiError.value = "ไม่สามารถดึงข้อมูลบัตรชั่ง 'เสร็จสิ้นแล้ว' ได้"
    completedTickets.value = []; // ล้างข้อมูลเก่า
  }
}
async function fetchCarQueue() {
  try {
    const response = await fetch(`${activeApiUrl.value}/api/car-queue/`);
    if (!response.ok) throw new Error('Could not fetch car queue');
    carQueue.value = await response.json();
  } catch (error) {
    console.error(error);
  }
}
function connectWebSocket() {
  const ws = new WebSocket(WEBSOCKET_URL);
  ws.onopen = () => { wsStatus.value = "Connected"; };
  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data.hasOwnProperty('weight')) {
        currentWeight.value = parseInt(data.weight).toLocaleString('en-US');
      }
    } catch (e) { console.error("Error parsing WebSocket message:", e); }
  };
  ws.onclose = () => {
    wsStatus.value = "Disconnected. Retrying...";
    setTimeout(connectWebSocket, 3000);
  };
  ws.onerror = (error) => {
    console.error("WebSocket error:", error);
    wsStatus.value = "Connection Error";
    ws.close();
  };
}

// --- Functions: Modal Control & Ticket Actions ---
async function openCreateTicketModal() {
  // ใน Offline Mode เราอาจจะไม่สามารถดึง Car Queue ได้
  if (isOnline.value) {
    await fetchCarQueue();
  } else {
    // อาจจะแสดงข้อความเตือน หรือใช้ข้อมูลเก่าถ้ามี
    console.warn("Cannot fetch car queue in offline mode.");
    carQueue.value = []; // ล้างข้อมูลเก่า
  }
  initialWeightForNewTicket.value = parseFloat(currentWeight.value.replace(/,/g, '')) || 0;
  isCreateModalVisible.value = true;
}

function closeCreateTicketModal() {
  isCreateModalVisible.value = false;
}

async function createTicket(ticketData) {
  isCreatingTicket.value = true
  try {
    const response = await fetch(`${activeApiUrl.value}/api/tickets/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(ticketData),
    });
    if (!response.ok) throw new Error('Server error!');
    alert('สร้างบัตรชั่งใหม่สำเร็จ!');
    isCreateModalVisible.value = false;
    await fetchOpenTickets(selectedDate.value);
  } catch (error) {
    console.error('Failed to create ticket:', error);
    alert('เกิดข้อผิดพลาดในการสร้างบัตรชั่ง');
  } finally {
    isCreatingTicket.value = false;
  }
}

async function showTicketDetails(ticket_id) {
  console.log(`🔍 showTicketDetails called with ticket_id: ${ticket_id}`);
  console.log(`🔍 activeApiUrl.value: ${activeApiUrl.value}`);
  console.log(`🔍 isModalVisible before: ${isModalVisible.value}`);
  
  selectTicket(ticket_id);
  try {
    const url = `${activeApiUrl.value}/api/tickets/${ticket_id}`;
    console.log(`🔍 Fetching ticket details from: ${url}`);
    
    const response = await fetch(url);
    console.log(`🔍 Response status: ${response.status}`);
    
    if (!response.ok) {
      const errorText = await response.text();
      console.error(`🔍 API Error ${response.status}:`, errorText);
      throw new Error(`Ticket not found: ${response.status} - ${errorText}`);
    }
    
    const data = await response.json();
    console.log('🔍 Ticket details fetched successfully:', data);
    detailTicket.value = data;
    isModalVisible.value = true;
    console.log(`🔍 isModalVisible after: ${isModalVisible.value}`);
    console.log(`🔍 detailTicket.value:`, detailTicket.value);
  } catch (error) {
    console.error("🔍 Failed to fetch ticket details:", error);
    alert(`ไม่สามารถดึงข้อมูลรายละเอียดได้: ${error.message}`);
  }
}
function closeModal() {
  isModalVisible.value = false
  detailTicket.value = null
}
async function selectTicket(ticketId) {
  if (selectedTicketId.value === ticketId) {
    selectedTicketId.value = null;
    selectedTicketDetail.value = null;
  } else {
    selectedTicketId.value = ticketId;
    // ดึงข้อมูลรายละเอียดของบัตรชั่งที่เลือก
    try {
      const response = await fetch(`${activeApiUrl.value}/api/tickets/${ticketId}`);
      if (response.ok) {
        selectedTicketDetail.value = await response.json();
        console.log('Selected ticket detail:', selectedTicketDetail.value);
      }
    } catch (error) {
      console.error('Failed to fetch ticket detail:', error);
      selectedTicketDetail.value = null;
    }
  }
}
async function handleViewTicket(ticketId) {
  console.log(`กำลังจะเปลี่ยนไปดูบัตร: ${ticketId}`);
  // 1. ปิด Modal ปัจจุบัน
  closeModal();
  // 2. รอสักครู่เพื่อให้ UI หายไปก่อน
  await new Promise(resolve => setTimeout(resolve, 150)); 
  // 3. เปิดรายละเอียดของบัตรใบใหม่
  await showTicketDetails(ticketId);
}

function handleStartContinuousWeighing() {
  // Log ที่ 1: ตรวจสอบว่าฟังก์ชันถูกเรียกหรือไม่
  console.log("1. ฟังก์ชัน 'handleStartContinuousWeighing' เริ่มทำงาน");

  // ตรวจสอบ Guard Clause
  if (!selectedTicketObject.value) {
    console.error("2. [ERROR] ออกจากฟังก์ชันเพราะ 'selectedTicketObject' ไม่มีค่า (เป็น null)");
    return;
  }

  // Log ที่ 2: ดูข้อมูลของบัตรที่เลือก
  console.log("2. ข้อมูลของบัตรที่เลือก (selectedTicketObject):", JSON.parse(JSON.stringify(selectedTicketObject.value)));

  const previousTicket = selectedTicketObject.value;

  // Log ที่ 3: ตรวจสอบค่าที่จำเป็นก่อนนำไปใช้
  console.log("3. กำลังตรวจสอบ Property ที่จำเป็น:");
  console.log("   - WE_LICENSE:", previousTicket.WE_LICENSE);
  console.log("   - WE_VENDOR:", previousTicket.WE_VENDOR);
  console.log("   - WE_VENDOR_CD:", previousTicket.WE_VENDOR_CD);
  console.log("   - WE_WEIGHTOUT:", previousTicket.WE_WEIGHTOUT);
  console.log("   - WE_SEQ:", previousTicket.WE_SEQ); // เพิ่มการ log WE_SEQ

  // ตรวจสอบว่ามีค่าที่จำเป็นครบหรือไม่
  if (!previousTicket.WE_LICENSE || !previousTicket.WE_WEIGHTOUT) {
      console.error("4. [ERROR] ออกจากฟังก์ชันเพราะไม่มีข้อมูล 'ทะเบียนรถ' หรือ 'น้ำหนักชั่งออก'");
      alert("ไม่สามารถชั่งต่อเนื่องได้: ข้อมูลบัตรชั่งไม่สมบูรณ์");
      return;
  }

  // 1. เตรียมข้อมูลที่จะส่งต่อ
  const dataToPass = {
    CARLICENSE: previousTicket.WE_LICENSE,
    AR_NAME: previousTicket.WE_VENDOR,
    KUNNR: previousTicket.WE_VENDOR_CD,
    INITIAL_WEIGHT_IN: previousTicket.WE_WEIGHTOUT 
  };
  
  // Log ที่ 4: ดูข้อมูลที่จะถูกส่งต่อไปให้ Modal
  console.log("4. ข้อมูลที่จะถูกส่งต่อไปให้ Modal (continuousWeighingData):", dataToPass);
  continuousWeighingData.value = {
    CARLICENSE: previousTicket.WE_LICENSE,
    AR_NAME: previousTicket.WE_VENDOR,
    KUNNR: previousTicket.WE_VENDOR_CD,
    INITIAL_WEIGHT_IN: previousTicket.WE_WEIGHTOUT,
    PARENT_ID: previousTicket.WE_ID,
    WE_SEQ: previousTicket.WE_SEQ
  };
    
  // 2. เปิด CreateTicketModal
  // Log ที่ 5: ยืนยันว่ากำลังจะเปิด Modal
  console.log("5. กำลังจะตั้งค่า isCreateModalVisible เป็น true...");
  isCreateModalVisible.value = true;
}
async function handleCreateTicket(ticketData) {
  isCreatingTicket.value = true;
  try {
    const response = await fetch(`${activeApiUrl.value}/api/tickets/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(ticketData),
    });
    if (!response.ok) throw new Error('Server error!');
    alert('สร้างบัตรชั่งใหม่สำเร็จ!');
    isCreateModalVisible.value = false;
    await fetchOpenTickets(selectedDate.value);
  } catch (error) {
    console.error('Failed to create ticket:', error);
    alert('เกิดข้อผิดพลาดในการสร้างบัตรชั่ง');
  } finally {
    isCreatingTicket.value = false;
  }
}
async function handleWeighOut() {
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
    const response = await fetch(`${activeApiUrl.value}/api/tickets/${ticketIdToUpdate}/weigh-out`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ WE_WEIGHTOUT: weightOutValue }),
    });
    if (!response.ok) throw new Error('Server error during weigh-out!');
    
    // อัปเดตรายการบัตรชั่ง
    await Promise.all([ fetchOpenTickets(selectedDate.value), fetchCompletedTickets(selectedDate.value) ]);
    
    // เลือกบัตรชั่งที่อัปเดตแล้วโดยอัตโนมัติ
    selectedTicketId.value = ticketIdToUpdate;
    
    // ตรวจสอบว่าบัตรชั่งที่อัปเดตแล้วอยู่ในตารางไหน
    const isInOpenTickets = openTickets.value.some(ticket => ticket.WE_ID === ticketIdToUpdate);
    const isInCompletedTickets = completedTickets.value.some(ticket => ticket.WE_ID === ticketIdToUpdate);
    
    // สลับไปยัง tab ที่มีบัตรชั่งที่อัปเดตแล้ว
    if (isInOpenTickets) {
      activeTab.value = 'inProgress';
    } else if (isInCompletedTickets) {
      activeTab.value = 'completed';
    }
    
    // เลื่อนไปยังบัตรชั่งที่เลือก
    setTimeout(() => {
      const selectedElement = document.querySelector(`[data-ticket-id="${ticketIdToUpdate}"]`);
      if (selectedElement) {
        selectedElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }, 100);
    
    alert('บันทึกน้ำหนักชั่งออกสำเร็จ!');
    
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
  if (!confirm(`คุณต้องการยกเลิกบัตรชั่งเลขที่ ${selectedTicketId.value} ใช่หรือไม่?`)) {
    return;
  }
  isCancellingTicket.value = true;
  const ticketIdToCancel = selectedTicketId.value;
  try {
    const response = await fetch(`${activeApiUrl.value}/api/tickets/${ticketIdToCancel}/cancel`, {
      method: 'DELETE',
    });
    if (!response.ok) throw new Error('Server error during cancellation!');
    
    // อัปเดตรายการบัตรชั่ง
    await fetchOpenTickets(selectedDate.value);
    
    // เลือกบัตรชั่งที่ยกเลิกแล้วโดยอัตโนมัติ (ถ้ายังอยู่ในรายการ)
    selectedTicketId.value = ticketIdToCancel;
    
    // ตรวจสอบว่าบัตรชั่งที่ยกเลิกแล้วยังอยู่ในตารางหรือไม่
    const isStillInOpenTickets = openTickets.value.some(ticket => ticket.WE_ID === ticketIdToCancel);
    
    if (isStillInOpenTickets) {
      // สลับไปยัง tab ที่มีบัตรชั่งที่ยกเลิกแล้ว
      activeTab.value = 'inProgress';
      
      // เลื่อนไปยังบัตรชั่งที่เลือก
      setTimeout(() => {
        const selectedElement = document.querySelector(`[data-ticket-id="${ticketIdToCancel}"]`);
        if (selectedElement) {
          selectedElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
      }, 100);
    } else {
      // ถ้าบัตรชั่งหายไปจากรายการ ให้ล้างการเลือก
      selectedTicketId.value = null;
    }
    
    alert('ยกเลิกบัตรชั่งสำเร็จ!');
    
  } catch (error) {
    console.error('Failed to cancel ticket:', error);
    alert('เกิดข้อผิดพลาดในการยกเลิกบัตรชั่ง');
  } finally {
    isCancellingTicket.value = false;
  }
}

// --- ฟังก์ชันสำหรับพิมพ์รายงาน ---
async function handlePrintReport() {
  if (!selectedTicketId.value) {
    alert('กรุณาเลือกบัตรชั่งที่ต้องการพิมพ์รายงาน');
    return;
  }

  if (!printAction.value) {
    alert('กรุณาเลือกการดำเนินการ (Preview หรือ สั่งพิมพ์)');
    return;
  }

  isPrintingReport.value = true;
  try {
    // ใช้ข้อมูลรายละเอียดที่ดึงไว้แล้ว หรือดึงใหม่ถ้าไม่มี
    let ticketDetail = selectedTicketDetail.value;
    
    if (!ticketDetail) {
      // ดึงข้อมูลรายละเอียดของบัตรชั่งเพื่อตรวจสอบรายการสินค้า
      const response = await fetch(`${activeApiUrl.value}/api/tickets/${selectedTicketId.value}`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      ticketDetail = await response.json();
    }
    
    console.log('Ticket detail for report:', ticketDetail);
    
    // ตรวจสอบประเภทการชั่งจากรายการสินค้า
    const hasItems = ticketDetail.items && ticketDetail.items.length > 0;
    const reportType = hasItems ? 'a4' : 'a5'; // ชั่งรวมใช้ A4, ชั่งแยกใช้ A5
    
    console.log(`Items found: ${hasItems ? 'Yes' : 'No'}, Items count: ${ticketDetail.items ? ticketDetail.items.length : 0}`);
    
    if (printAction.value === 'preview') {
      // Preview - เปิดในแท็บใหม่
      const reportUrl = `https://reports.zubbsteel.com/zticket_${reportType}.php?id=${selectedTicketId.value}`;
      window.open(reportUrl, '_blank');
    } else if (printAction.value === 'print') {
      // สั่งพิมพ์ - Download ที่ Client และสั่งพิมพ์
      await printReportFromClient(selectedTicketId.value, reportType, hasItems);
    } else if (printAction.value === 'download') {
      // ดาวน์โหลด - Download ไฟล์ไปยังโฟลเดอร์ Downloads
      await downloadReportToClient(selectedTicketId.value, reportType, hasItems);
    }
    
  } catch (error) {
    console.error('Failed to handle report:', error);
    alert(`เกิดข้อผิดพลาดในการดำเนินการรายงาน: ${error.message}`);
  } finally {
    isPrintingReport.value = false;
  }
}

// ฟังก์ชันใหม่สำหรับ Download และสั่งพิมพ์ที่ Client
async function printReportFromClient(ticketId, reportType, hasItems) {
  try {
    // ทำความสะอาด ticketId (ลบช่องว่าง)
    const cleanTicketId = ticketId.trim();
    
    console.log(`Starting print process for ticket: ${cleanTicketId}, type: ${reportType}`);
    
    // วิธีที่ 1: ลองใช้ Client-side Printing (แนะนำ)
    console.log('Trying method 1: Client-side printing...');
    const clientSuccess = await printViaClient(cleanTicketId, reportType, hasItems);
    
    if (clientSuccess) {
      console.log('Client-side print successful!');
      return;
    }
    
    // วิธีที่ 2: ลองใช้ Backend Print Service (fallback)
    console.log('Client-side print failed, trying backend...');
    const backendSuccess = await printViaBackend(cleanTicketId, reportType, hasItems);
    
    if (backendSuccess) {
      console.log('Backend print successful!');
      return;
    }
    
    // วิธีที่ 3: Auto Download (fallback สุดท้าย)
    console.log('Backend print failed, trying auto download...');
    
    // ใช้ proxy endpoint แทนการเรียก URL โดยตรง
    const proxyUrl = `${activeApiUrl.value}/api/reports/${cleanTicketId}/download/${reportType}`;
    
    console.log(`Downloading report via proxy: ${proxyUrl}`);
    
    // Download ไฟล์ผ่าน proxy
    const response = await fetch(proxyUrl);
    if (!response.ok) {
      throw new Error(`ไม่สามารถดาวน์โหลดรายงานได้: ${response.status}`);
    }
    
    // แปลงเป็น blob
    const blob = await response.blob();
    
    // ตรวจสอบขนาดไฟล์
    console.log(`Downloaded file size: ${blob.size} bytes`);
    if (blob.size === 0) {
      throw new Error('ไฟล์ที่ดาวน์โหลดมีขนาด 0 bytes');
    }
    
    // สร้าง URL สำหรับ blob
    const blobUrl = URL.createObjectURL(blob);
    
    // สร้างชื่อไฟล์
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const filename = `report_${cleanTicketId}_${reportType}_${timestamp}.pdf`;
    
    console.log(`File downloaded successfully: ${filename}`);
    
    // ใช้ Auto Download
    console.log('Using auto download method...');
    const autoDownloadSuccess = await printViaAutoDownload(blob, filename);
    
    if (autoDownloadSuccess) {
      // ลบ blob URL
      setTimeout(() => {
        URL.revokeObjectURL(blobUrl);
        console.log('Blob URL cleaned up');
      }, 10000);
      return;
    }
    
    // Fallback: ลองวิธีอื่นๆ
    console.log('Auto download failed, trying other methods...');
    
    // วิธีที่ 4: ลองสั่งพิมพ์แบบ Silent
    console.log('Trying method 4: Silent print...');
    const silentPrintSuccess = await trySilentPrint(blobUrl, filename);
    
    if (silentPrintSuccess) {
      alert(`กำลังสั่งพิมพ์รายงาน${hasItems ? 'ชั่งรวม' : 'ชั่งแยก'}...`);
      setTimeout(() => {
        URL.revokeObjectURL(blobUrl);
        console.log('Blob URL cleaned up');
      }, 5000);
      return;
    }
    
    // วิธีที่ 5: ลองใช้ browser print API
    console.log('Trying method 5: Browser print API...');
    const browserAPISuccess = await printViaBrowserAPI(blob, filename);
    
    if (browserAPISuccess) {
      alert(`กำลังสั่งพิมพ์รายงาน${hasItems ? 'ชั่งรวม' : 'ชั่งแยก'}...`);
      setTimeout(() => {
        URL.revokeObjectURL(blobUrl);
        console.log('Blob URL cleaned up');
      }, 5000);
      return;
    }
    
    // วิธีที่ 6: ดาวน์โหลดไฟล์ธรรมดา
    console.log('Trying method 6: Normal download...');
    const downloadSuccess = await printViaDownload(blob, filename);
    
    if (downloadSuccess) {
      setTimeout(() => {
        URL.revokeObjectURL(blobUrl);
      }, 10000);
      return;
    }
    
    // วิธีที่ 7: เปิดในแท็บใหม่ (fallback สุดท้าย)
    console.log('Trying method 7: Open in new tab...');
    window.open(blobUrl, '_blank');
    alert('ไม่สามารถสั่งพิมพ์ได้ กรุณาพิมพ์จากหน้าต่างที่เปิดขึ้นมา');
    
    setTimeout(() => {
      URL.revokeObjectURL(blobUrl);
    }, 10000);
    
  } catch (error) {
    console.error('Download error:', error);
    throw new Error(`ไม่สามารถดาวน์โหลดรายงานได้: ${error.message}`);
  }
}

// ฟังก์ชันสำหรับ Download ไฟล์ไปยังโฟลเดอร์ Downloads
async function downloadReportToClient(ticketId, reportType, hasItems) {
  try {
    // ทำความสะอาด ticketId (ลบช่องว่าง)
    const cleanTicketId = ticketId.trim();
    
    // ใช้ proxy endpoint แทนการเรียก URL โดยตรง
    const proxyUrl = `${activeApiUrl.value}/api/reports/${cleanTicketId}/download/${reportType}`;
    
    console.log(`Downloading report via proxy: ${proxyUrl}`);
    
    // Download ไฟล์ผ่าน proxy
    const response = await fetch(proxyUrl);
    if (!response.ok) {
      throw new Error(`ไม่สามารถดาวน์โหลดรายงานได้: ${response.status}`);
    }
    
    // แปลงเป็น blob
    const blob = await response.blob();
    
    // ตรวจสอบขนาดไฟล์
    console.log(`Downloaded file size: ${blob.size} bytes`);
    if (blob.size === 0) {
      throw new Error('ไฟล์ที่ดาวน์โหลดมีขนาด 0 bytes');
    }
    
    // สร้างชื่อไฟล์
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const filename = `report_${cleanTicketId}_${reportType}_${timestamp}.pdf`;
    
    console.log(`File downloaded successfully: ${filename}`);
    
    // สร้าง link สำหรับ download
    const downloadLink = document.createElement('a');
    downloadLink.href = URL.createObjectURL(blob);
    downloadLink.download = filename;
    downloadLink.style.display = 'none';
    
    // เพิ่ม link เข้าไปใน DOM และคลิก
    document.body.appendChild(downloadLink);
    downloadLink.click();
    
    // ลบ link และ blob URL
    setTimeout(() => {
      document.body.removeChild(downloadLink);
      URL.revokeObjectURL(downloadLink.href);
      console.log('Download link cleaned up');
    }, 1000);
    
    alert(`ดาวน์โหลดรายงาน${hasItems ? 'ชั่งรวม' : 'ชั่งแยก'} สำเร็จ: ${filename}`);
    
  } catch (error) {
    console.error('Download error:', error);
    throw new Error(`ไม่สามารถดาวน์โหลดรายงานได้: ${error.message}`);
  }
}
async function handleTicketUpdate(eventData) {
  console.log('🔧 handleTicketUpdate called with eventData:', eventData);
  
  // ดึงค่ามาจาก eventData ที่ส่งมาใหม่
  const updatePayload = eventData.payload;
  const ticketId = eventData.ticketId;

  console.log('🔧 updatePayload:', updatePayload);
  console.log('🔧 ticketId:', ticketId);
  console.log('🔧 updatePayload.mainData:', updatePayload.mainData);

  // --- จุดตรวจสอบใหม่ ---
  if (!ticketId) {
    console.error("🔧 Update failed: No ticketId was provided.");
    alert("เกิดข้อผิดพลาด: ไม่พบ ID ของบัตรชั่ง");
    return;
  }
  
  console.log(`🔧 Starting update for ticket ID: ${ticketId}`);
  console.log(`🔧 activeApiUrl.value: ${activeApiUrl.value}`);
  
  isUpdatingTicket.value = true;
  let hasError = false;

  try {
    // --- ส่วนที่ 1: อัปเดตข้อมูลหลัก (ใช้ ticketId ที่รับมา) ---
    console.log("🔧 Sending main data update (PATCH):", updatePayload.mainData);
    console.log("🔧 Specifically checking WE_TRUCK_CHAR:", updatePayload.mainData.WE_TRUCK_CHAR);
    const mainUrl = `${activeApiUrl.value}/api/tickets/${ticketId}`;
    console.log("🔧 Main update URL:", mainUrl);
    
    const mainResponse = await fetch(mainUrl, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updatePayload.mainData),
    });

    console.log("🔧 Main response status:", mainResponse.status);

    if (!mainResponse.ok) {
      hasError = true;
      const errorText = await mainResponse.text();
      console.error('🔧 Failed to update main ticket data:', errorText);
      alert(`เกิดข้อผิดพลาดในการอัปเดตข้อมูลหลัก: ${mainResponse.status} - ${errorText}`);
    } else {
      console.log("🔧 Main data update successful");
      const responseData = await mainResponse.json();
      console.log("🔧 Response data:", responseData);
      console.log("🔧 Updated WE_TRUCK_CHAR in response:", responseData.WE_TRUCK_CHAR);
    }

    // --- ส่วนที่ 2: ถ้าไม่มี Error และมีรายการใหม่ให้แทนที่ ให้เรียก API "แทนที่" ---
    if (!hasError && updatePayload.newItems) {
      console.log("Sending new items to replace (PUT):", updatePayload.newItems);
      const itemsResponse = await fetch(`${activeApiUrl.value}/api/tickets/${ticketId}/items`, { // <-- ใช้ ticketId
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updatePayload.newItems),
      });

      if (!itemsResponse.ok) {
        hasError = true;
        console.error('Failed to replace ticket items:', await itemsResponse.text());
        alert('เกิดข้อผิดพลาดในการแทนที่รายการสินค้า');
      }
    }
    
    // --- ถ้าทุกอย่างสำเร็จ ---
    if (!hasError) {
      console.log("🔧 All updates successful!");
      alert('แก้ไขข้อมูลสำเร็จ!');
      console.log("🔧 About to call refreshTicketData...");
      await refreshTicketData(ticketId); // รีเฟรชข้อมูลทั้งหมด
      console.log("🔧 refreshTicketData completed");
    } else {
      console.log("🔧 Update failed due to errors");
    }
    
  } catch (error) {
    console.error('🔧 Error during ticket update process:', error);
    alert(`เกิดข้อผิดพลาดร้ายแรงในการแก้ไขข้อมูล: ${error.message}`);
  } finally {
    isUpdatingTicket.value = false;
    console.log("🔧 handleTicketUpdate completed");
  }
}
async function refreshTicketData(ticketId) {
  console.log("🔄 refreshTicketData called for ticketId:", ticketId);
  
  // อัปเดตข้อมูลรายการก่อน
  await Promise.all([
      fetchOpenTickets(selectedDate.value),
      fetchCompletedTickets(selectedDate.value)
  ]);
  
  // อัปเดตข้อมูลรายละเอียดของบัตรชั่งที่เลือก
  if (selectedTicketId.value === ticketId) {
    try {
      const response = await fetch(`${activeApiUrl.value}/api/tickets/${ticketId}`);
      if (response.ok) {
        selectedTicketDetail.value = await response.json();
        console.log("🔄 Updated selectedTicketDetail:", selectedTicketDetail.value);
      }
    } catch (error) {
      console.error('Failed to refresh ticket detail:', error);
    }
  }
  
  // อัปเดตข้อมูลใน modal โดยไม่ปิด modal
  try {
    const response = await fetch(`${activeApiUrl.value}/api/tickets/${ticketId}`);
    if (response.ok) {
      const updatedTicket = await response.json();
      console.log("🔄 Before updating detailTicket:", detailTicket.value);
      console.log("🔄 New ticket data from API:", updatedTicket);
      detailTicket.value = updatedTicket;
      console.log("🔄 After updating detailTicket:", detailTicket.value);
      console.log("🔄 Updated WE_TRUCK_CHAR:", detailTicket.value.WE_TRUCK_CHAR);
    }
  } catch (error) {
    console.error('Failed to refresh modal ticket data:', error);
  }
}

// --- Watcher & Lifecycle Hook ---
watch(selectedDate, async (newDate) => {
  apiError.value = null;
  selectedTicketId.value = null;
  await fetchOpenTickets(newDate);
  await fetchCompletedTickets(newDate);
});
onMounted(async () => {
  // --- เพิ่ม Event Listeners สำหรับ Online/Offline Status ---
  window.addEventListener('online', () => isOnline.value = true);
  window.addEventListener('offline', () => isOnline.value = false);

  connectWebSocket()
  fetchDataForDate(selectedDate.value)
})

// ฟังก์ชันใหม่สำหรับสั่งพิมพ์ผ่านการดาวน์โหลดไฟล์
async function printViaDownload(blob, filename) {
  return new Promise((resolve) => {
    try {
      console.log('Attempting print via download...');
      
      // สร้าง link สำหรับ download
      const downloadLink = document.createElement('a');
      downloadLink.href = URL.createObjectURL(blob);
      downloadLink.download = filename;
      downloadLink.style.display = 'none';
      
      // เพิ่ม link เข้าไปใน DOM และคลิก
      document.body.appendChild(downloadLink);
      downloadLink.click();
      
      // ลบ link และ blob URL
      setTimeout(() => {
        document.body.removeChild(downloadLink);
        URL.revokeObjectURL(downloadLink.href);
        console.log('Download link cleaned up');
      }, 1000);
      
      // แสดงข้อความให้ผู้ใช้ทราบ
      alert(`ไฟล์ ${filename} ถูกดาวน์โหลดแล้ว กรุณาเปิดไฟล์และสั่งพิมพ์จากโปรแกรม PDF viewer`);
      
      resolve(true);
      
    } catch (error) {
      console.error('Download print error:', error);
      resolve(false);
    }
  });
}

// ฟังก์ชันสำหรับลองสั่งพิมพ์แบบ Silent
async function trySilentPrint(blobUrl, filename) {
  return new Promise((resolve) => {
    try {
      console.log('Attempting silent print...');
      
      // วิธีที่ 1: ลองใช้ window.open แล้วสั่งพิมพ์
      const printWindow = window.open(blobUrl, '_blank', 'width=800,height=600,scrollbars=yes,resizable=yes');
      
      if (printWindow) {
        let printAttempted = false;
        
        // รอให้หน้าต่างโหลดเสร็จ
        printWindow.onload = function() {
          if (printAttempted) return;
          printAttempted = true;
          
          try {
            console.log('Print window loaded, waiting for PDF to load...');
            
            // รอให้ PDF โหลดเสร็จ
            setTimeout(() => {
              try {
                // ลองสั่งพิมพ์หลายวิธี
                if (printWindow.print) {
                  printWindow.print();
                  console.log('Print command sent successfully via window.open.print()');
                } else if (printWindow.document && printWindow.document.defaultView && printWindow.document.defaultView.print) {
                  printWindow.document.defaultView.print();
                  console.log('Print command sent via document.defaultView.print()');
                } else {
                  console.warn('No print method found in window');
                  resolve(false);
                  return;
                }
                
                resolve(true);
                
                // ปิดหน้าต่างหลังจากสั่งพิมพ์
                setTimeout(() => {
                  if (!printWindow.closed) {
                    printWindow.close();
                    console.log('Print window closed');
                  }
                }, 5000);
                
              } catch (printError) {
                console.error('Print error via window.open:', printError);
                if (!printWindow.closed) {
                  printWindow.close();
                }
                resolve(false);
              }
            }, 3000); // รอ 3 วินาทีให้ PDF โหลดเสร็จ
            
          } catch (error) {
            console.error('Window load error:', error);
            if (!printWindow.closed) {
              printWindow.close();
            }
            resolve(false);
          }
        };
        
        // ตั้ง timeout สำหรับการโหลด
        setTimeout(() => {
          if (!printAttempted) {
            console.warn('Print window load timeout, attempting print anyway...');
            printAttempted = true;
            
            try {
              // ลองสั่งพิมพ์แม้จะ timeout
              if (printWindow.print) {
                printWindow.print();
                console.log('Print command sent after timeout');
                resolve(true);
              } else {
                console.warn('No print method available after timeout');
                resolve(false);
              }
              
              setTimeout(() => {
                if (!printWindow.closed) {
                  printWindow.close();
                }
              }, 5000);
              
            } catch (error) {
              console.error('Print error after timeout:', error);
              if (!printWindow.closed) {
                printWindow.close();
              }
              resolve(false);
            }
          }
        }, 8000); // timeout 8 วินาที
        
      } else {
        // ถ้าไม่สามารถเปิดหน้าต่างใหม่ได้ (popup blocker)
        console.warn('Cannot open print window (popup blocker), trying iframe method...');
        
        // วิธีที่ 2: ใช้ iframe (fallback)
        const printFrame = document.createElement('iframe');
        printFrame.style.display = 'none';
        printFrame.style.width = '100%';
        printFrame.style.height = '100%';
        printFrame.src = blobUrl;
        
        // เพิ่ม iframe เข้าไปใน DOM
        document.body.appendChild(printFrame);
        
        let printAttempted = false;
        
        // รอให้ iframe โหลดเสร็จแล้วสั่งพิมพ์
        printFrame.onload = function() {
          if (printAttempted) return;
          printAttempted = true;
          
          try {
            console.log('Print frame loaded, waiting for PDF to load...');
            
            // รอสักครู่ให้ไฟล์โหลดเสร็จสมบูรณ์
            setTimeout(() => {
              try {
                // ลองสั่งพิมพ์หลายวิธี
                if (printFrame.contentWindow && printFrame.contentWindow.print) {
                  printFrame.contentWindow.print();
                  console.log('Print command sent successfully via iframe.contentWindow.print()');
                } else if (printFrame.contentWindow && printFrame.contentWindow.document && printFrame.contentWindow.document.defaultView && printFrame.contentWindow.document.defaultView.print) {
                  printFrame.contentWindow.document.defaultView.print();
                  console.log('Print command sent via iframe document.defaultView.print()');
                } else {
                  console.warn('No print method found in iframe');
                  resolve(false);
                  return;
                }
                
                resolve(true);
                
                // ลบ iframe หลังจากสั่งพิมพ์
                setTimeout(() => {
                  if (printFrame.parentNode) {
                    document.body.removeChild(printFrame);
                    console.log('Print frame removed');
                  }
                }, 5000);
                
              } catch (printError) {
                console.error('Print error via iframe:', printError);
                resolve(false);
                
                // ลบ iframe
                if (printFrame.parentNode) {
                  document.body.removeChild(printFrame);
                }
              }
            }, 2000); // รอ 2 วินาที
            
          } catch (error) {
            console.error('Frame load error:', error);
            resolve(false);
            
            // ลบ iframe
            if (printFrame.parentNode) {
              document.body.removeChild(printFrame);
            }
          }
        };
        
        // ตั้ง timeout สำหรับการโหลด
        setTimeout(() => {
          if (!printAttempted) {
            console.warn('Print frame load timeout');
            printAttempted = true;
            resolve(false);
            
            // ลบ iframe
            if (printFrame.parentNode) {
              document.body.removeChild(printFrame);
            }
          }
        }, 10000); // timeout 10 วินาที
      }
      
    } catch (error) {
      console.error('Silent print setup error:', error);
      resolve(false);
    }
  });
}

// ฟังก์ชันใหม่สำหรับสั่งพิมพ์ผ่าน browser print API
async function printViaBrowserAPI(blob, filename) {
  return new Promise((resolve) => {
    try {
      console.log('Attempting print via browser print API...');
      
      // สร้าง URL สำหรับ blob
      const blobUrl = URL.createObjectURL(blob);
      
      // สร้าง iframe สำหรับแสดง PDF
      const printFrame = document.createElement('iframe');
      printFrame.style.display = 'none';
      printFrame.style.width = '100%';
      printFrame.style.height = '100%';
      printFrame.src = blobUrl;
      
      // เพิ่ม iframe เข้าไปใน DOM
      document.body.appendChild(printFrame);
      
      let printAttempted = false;
      
      // รอให้ iframe โหลดเสร็จ
      printFrame.onload = function() {
        if (printAttempted) return;
        printAttempted = true;
        
        try {
          console.log('Print frame loaded for browser API, attempting print...');
          
          // รอให้ PDF โหลดเสร็จ
          setTimeout(() => {
            try {
              // ใช้ browser print API
              if (window.print) {
                window.print();
                console.log('Print command sent via browser print API');
                resolve(true);
              } else {
                console.warn('Browser print API not available');
                resolve(false);
              }
              
              // ลบ iframe และ blob URL
              setTimeout(() => {
                if (printFrame.parentNode) {
                  document.body.removeChild(printFrame);
                }
                URL.revokeObjectURL(blobUrl);
                console.log('Print frame and blob URL cleaned up');
              }, 3000);
              
            } catch (printError) {
              console.error('Print error via browser API:', printError);
              resolve(false);
              
              // ลบ iframe และ blob URL
              if (printFrame.parentNode) {
                document.body.removeChild(printFrame);
              }
              URL.revokeObjectURL(blobUrl);
            }
          }, 2000);
          
        } catch (error) {
          console.error('Frame load error for browser API:', error);
          resolve(false);
          
          // ลบ iframe และ blob URL
          if (printFrame.parentNode) {
            document.body.removeChild(printFrame);
          }
          URL.revokeObjectURL(blobUrl);
        }
      };
      
      // ตั้ง timeout
      setTimeout(() => {
        if (!printAttempted) {
          console.warn('Browser API print timeout');
          printAttempted = true;
          resolve(false);
          
          // ลบ iframe และ blob URL
          if (printFrame.parentNode) {
            document.body.removeChild(printFrame);
          }
          URL.revokeObjectURL(blobUrl);
        }
      }, 8000);
      
    } catch (error) {
      console.error('Browser API print setup error:', error);
      resolve(false);
    }
  });
}

// ฟังก์ชันใหม่สำหรับสั่งพิมพ์ผ่านการดาวน์โหลดและเปิดไฟล์อัตโนมัติ
async function printViaAutoDownload(blob, filename) {
  return new Promise((resolve) => {
    try {
      console.log('Attempting print via auto download...');
      
      // สร้าง link สำหรับ download
      const downloadLink = document.createElement('a');
      downloadLink.href = URL.createObjectURL(blob);
      downloadLink.download = filename;
      downloadLink.style.display = 'none';
      
      // เพิ่ม link เข้าไปใน DOM และคลิก
      document.body.appendChild(downloadLink);
      downloadLink.click();
      
      // ลบ link และ blob URL
      setTimeout(() => {
        document.body.removeChild(downloadLink);
        URL.revokeObjectURL(downloadLink.href);
        console.log('Download link cleaned up');
      }, 1000);
      
      // แสดงข้อความให้ผู้ใช้ทราบ
      alert(`ไฟล์ ${filename} ถูกดาวน์โหลดแล้ว\n\nระบบจะพยายามเปิดไฟล์และสั่งพิมพ์อัตโนมัติ\n\nหากไม่มีการสั่งพิมพ์ กรุณา:\n1. เปิดไฟล์จากโฟลเดอร์ Downloads\n2. กด Ctrl+P เพื่อสั่งพิมพ์\n3. เลือกเครื่องพิมพ์ที่ต้องการ`);
      
      // ลองเปิดไฟล์อัตโนมัติด้วยวิธีต่างๆ
      setTimeout(() => {
        try {
          // วิธีที่ 1: ลองเปิดด้วย blob URL
          console.log('Trying to open file with blob URL...');
          window.open(downloadLink.href, '_blank');
        } catch (error) {
          console.log('Cannot open with blob URL, trying other methods...');
          
          // วิธีที่ 2: ลองเปิดด้วย iframe
          try {
            const iframe = document.createElement('iframe');
            iframe.src = downloadLink.href;
            iframe.style.display = 'none';
            document.body.appendChild(iframe);
            
            setTimeout(() => {
              document.body.removeChild(iframe);
            }, 5000);
          } catch (error2) {
            console.log('Cannot open with iframe either');
          }
        }
      }, 2000);
      
      resolve(true);
      
    } catch (error) {
      console.error('Auto download print error:', error);
      resolve(false);
    }
  });
}

// ฟังก์ชันใหม่สำหรับสั่งพิมพ์ผ่าน iframe และ window.print()
async function printViaIframe(blob, filename) {
  return new Promise((resolve) => {
    try {
      console.log('Attempting print via iframe...');
      
      // สร้าง iframe
      const iframe = document.createElement('iframe');
      iframe.style.display = 'none';
      iframe.style.position = 'fixed';
      iframe.style.top = '-9999px';
      iframe.style.left = '-9999px';
      
      // เพิ่ม iframe เข้าไปใน DOM
      document.body.appendChild(iframe);
      
      // สร้าง blob URL
      const blobUrl = URL.createObjectURL(blob);
      
      // รอให้ iframe โหลดเสร็จแล้วสั่งพิมพ์
      iframe.onload = () => {
        try {
          console.log('Iframe loaded, attempting to print...');
          
          // รอสักครู่ให้ PDF โหลดเสร็จ
          setTimeout(() => {
            try {
              // ลองสั่งพิมพ์
              iframe.contentWindow.print();
              console.log('Print command sent via iframe');
              
              // ลบ iframe และ blob URL หลังจากสั่งพิมพ์
              setTimeout(() => {
                document.body.removeChild(iframe);
                URL.revokeObjectURL(blobUrl);
                console.log('Iframe and blob URL cleaned up');
              }, 10000);
              
              resolve(true);
            } catch (printError) {
              console.error('Print error:', printError);
              document.body.removeChild(iframe);
              URL.revokeObjectURL(blobUrl);
              resolve(false);
            }
          }, 2000);
          
        } catch (error) {
          console.error('Iframe print error:', error);
          document.body.removeChild(iframe);
          URL.revokeObjectURL(blobUrl);
          resolve(false);
        }
      };
      
      // ตั้งค่า src ของ iframe
      iframe.src = blobUrl;
      
      // Timeout ถ้า iframe ไม่โหลด
      setTimeout(() => {
        if (document.body.contains(iframe)) {
          document.body.removeChild(iframe);
          URL.revokeObjectURL(blobUrl);
          console.log('Iframe timeout, removing...');
          resolve(false);
        }
      }, 15000);
      
    } catch (error) {
      console.error('Iframe creation error:', error);
      resolve(false);
    }
  });
}

// ฟังก์ชันใหม่สำหรับสั่งพิมพ์ผ่าน Client-side
async function printViaClient(ticketId, reportType, hasItems) {
  try {
    console.log('Attempting print via client...');
    
    // ดาวน์โหลดไฟล์ผ่าน proxy
    const proxyUrl = `${activeApiUrl.value}/api/reports/${ticketId}/download/${reportType}`;
    console.log(`Downloading from: ${proxyUrl}`);
    
    const response = await fetch(proxyUrl);
    if (!response.ok) {
      throw new Error(`ไม่สามารถดาวน์โหลดได้: ${response.status}`);
    }
    
    const blob = await response.blob();
    console.log(`Downloaded file size: ${blob.size} bytes`);
    
    if (blob.size === 0) {
      throw new Error('ไฟล์ที่ดาวน์โหลดมีขนาด 0 bytes');
    }
    
    // สร้าง URL สำหรับ blob
    const blobUrl = URL.createObjectURL(blob);
    
    // สร้างชื่อไฟล์
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const filename = `report_${ticketId}_${reportType}_${timestamp}.pdf`;
    
    // วิธีที่ 1: ลองใช้ iframe printing (แนะนำ)
    console.log('Trying iframe printing...');
    const iframeSuccess = await printViaIframe(blob, filename);
    
    if (iframeSuccess) {
      alert(`สั่งพิมพ์รายงาน${hasItems ? 'ชั่งรวม' : 'ชั่งแยก'} สำเร็จ!\n\nTicket ID: ${ticketId}\nReport Type: ${reportType}`);
      
      // ลบ blob URL
      setTimeout(() => {
        URL.revokeObjectURL(blobUrl);
        console.log('Blob URL cleaned up');
      }, 10000);
      
      return true;
    }
    
    // วิธีที่ 2: ใช้ Auto Download (fallback)
    console.log('Iframe printing failed, trying auto download...');
    const success = await printViaAutoDownload(blob, filename);
    
    if (success) {
      alert(`สั่งพิมพ์รายงาน${hasItems ? 'ชั่งรวม' : 'ชั่งแยก'} สำเร็จ!\n\nTicket ID: ${ticketId}\nReport Type: ${reportType}`);
      
      // ลบ blob URL
      setTimeout(() => {
        URL.revokeObjectURL(blobUrl);
        console.log('Blob URL cleaned up');
      }, 10000);
      
      return true;
    } else {
      throw new Error('ไม่สามารถสั่งพิมพ์ได้');
    }
    
  } catch (error) {
    console.error('Client print error:', error);
    alert(`ไม่สามารถสั่งพิมพ์ได้: ${error.message}`);
    return false;
  }
}

// ฟังก์ชันใหม่สำหรับสั่งพิมพ์ผ่าน Backend Print Service (fallback)
async function printViaBackend(ticketId, reportType, hasItems) {
  try {
    console.log('Attempting print via backend...');
    
    const response = await fetch(`${activeApiUrl.value}/api/print/${ticketId}/${reportType}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });
    
    if (response.ok) {
      const result = await response.json();
      alert(`สั่งพิมพ์รายงาน${hasItems ? 'ชั่งรวม' : 'ชั่งแยก'} สำเร็จ!\n\nTicket ID: ${result.ticket_id}\nReport Type: ${result.report_type}`);
      return true;
    } else {
      const errorData = await response.json();
      throw new Error(errorData.detail || `ไม่สามารถสั่งพิมพ์ได้: ${response.status}`);
    }
    
  } catch (error) {
    console.error('Backend print error:', error);
    alert(`ไม่สามารถสั่งพิมพ์ได้: ${error.message}`);
    return false;
  }
}
</script>

<template>
  <div class="app-container">
    <main>
      <div class="left-panel card">
        <div class="weight-display-container">
          <div class="weight-display">
            <div class="weight-icon">⚖️</div>
            <span :style="{ fontSize: 'clamp(2.5rem, 10vw, 4.5rem)' }">{{ currentWeight.toLocaleString() }}</span>
            <div class="weight-unit">กิโลกรัม</div>
          </div>
          <div class="connection-status" :class="{
              'connected': wsStatus === 'Connected' && isOnline,
              'disconnected': wsStatus !== 'Connected' && isOnline,
              'offline': !isOnline
            }">
             <span class="status-indicator"></span>
            <span class="status-text">{{ isOnline ? wsStatus : 'Offline Mode' }}</span>
          </div>
        </div>

        <hr class="divider">
        
        <div class="create-ticket-panel">
          <button @click="openCreateTicketModal" class="create-ticket-button">
            <span class="button-icon">➕</span>
            สร้างบัตรชั่งใหม่
          </button>
        </div>

        <div class="action-panel">
          <div class="selected-ticket-info">
            <label>📋 บัตรที่เลือก:</label>
            <div v-if="selectedTicketObject" class="ticket-id-display">
              <span class="ticket-icon">🎫</span>
              {{ selectedTicketObject.WE_ID }} 
              <span class="license-text">({{ selectedTicketObject.WE_LICENSE }})</span>
            </div>
            <div v-else class="no-ticket-selected">
              <span class="no-selection-icon">⚠️</span>
              - ยังไม่ได้เลือก -
            </div>
          </div>

          <div v-if="selectedTicketObject" class="action-buttons-grid">
            <button 
              class="action-btn cancel-btn"
              @click="cancelTicket(selectedTicketId)"
              :disabled="!!selectedTicketObject.WE_CANCEL || !!selectedTicketObject.WE_WEIGHTOUT"
            >
              <span class="button-icon">❌</span>
              ยกเลิกบัตร
            </button>

            <template v-if="selectedTicketObject.WE_WEIGHTOUT">
               <button 
                class="action-btn continuous-btn"
                @click="openContinuousWeighingModal"
                :disabled="selectedTicketObject.WE_CONT === 'X'"
              >
                <span class="button-icon">🔄</span>
                ชั่งต่อเนื่อง
              </button>
            </template>
            <template v-else>
              <button 
                class="action-btn weigh-out-btn"
                @click="updateTicketWeighOut(selectedTicketId)"
                :disabled="!!selectedTicketObject.WE_WEIGHTOUT"
              >
                <span class="button-icon">📤</span>
                บันทึกน้ำหนักออก
              </button>
            </template>

            <div class="print-report-section">
                <button 
                  @click="printReport(selectedTicketId, 'preview')" 
                  class="action-btn report-preview"
                  :disabled="!selectedTicketObject.WE_WEIGHTOUT"
                >
                  ดูรายงาน
                </button>
                <button 
                  @click="printReport(selectedTicketId, 'print')" 
                  class="action-btn report-print"
                  :disabled="!selectedTicketObject.WE_WEIGHTOUT"
                >
                  พิมพ์รายงาน
                </button>
            </div>

          </div>
        </div>
      </div>

      <div class="right-panel card">
        <div class="date-filter-container">
          <label for="date-filter">📅 เลือกวันที่:</label>
          <input type="date" id="date-filter" v-model="selectedDate" @change="onDateChanged">
        </div>
        <div class="tabs">
          <button :class="{ active: activeTab === 'inProgress' }" @click="activeTab = 'inProgress'">
            <span class="tab-icon">⏳</span>
            กำลังดำเนินการ ({{ openTickets.length }})
          </button>
          <button :class="{ active: activeTab === 'completed' }" @click="activeTab = 'completed'">
            <span class="tab-icon">✅</span>
            เสร็จสิ้นแล้ว ({{ completedTickets.length }})
          </button>
        </div>
        
        <div class="table-instruction">
          <span class="instruction-icon">💡</span>
          คลิกที่แถวเพื่อเลือกบัตรชั่ง หรือคลิกไอคอน 🔍 เพื่อดู/แก้ไขรายละเอียด
        </div>

        <div v-if="apiError" class="error-message">
          <span class="error-icon">🚨</span>
          {{ apiError }}
        </div>

        <div class="table-container" v-else>
          <div v-show="activeTab === 'inProgress'">
            <table>
              <thead>
                <tr>
                  <th style="width: 50px;">ดู/แก้ไข</th>
                  <th>เลขที่บัตร</th>
                  <th>ทะเบียนรถ</th>
                  <th>ประเภทรายงาน</th>
                  <th>เวลาเข้า</th>
                  <th>น้ำหนักเข้า (กก.)</th>
                </tr>
              </thead>
              <tbody>
                <tr 
                  v-for="ticket in openTickets" 
                  :key="ticket.WE_ID" 
                  @click="selectTicket(ticket.WE_ID)" 
                  :class="{ 'clickable-row': true, 'active-row': selectedTicketId === ticket.WE_ID }"
                  :data-ticket-id="ticket.WE_ID"
                >
                  <td class="view-cell">
                    <button 
                      class="view-btn" 
                      @click.stop="showTicketDetails(ticket.WE_ID)"
                      title="ดู/แก้ไขรายละเอียด"
                    >
                      🔍
                    </button>
                  </td>
                  <td>{{ ticket.WE_ID }}</td>
                  <td>{{ ticket.WE_LICENSE }}</td>
                  <td>{{ getReportTypeText(ticket) }}</td>
                  <td>{{ formatTime(ticket.WE_TIMEIN) }}</td>
                  <td>{{ ticket.WE_WEIGHTIN.toLocaleString() }}</td>
                </tr>
                <tr v-if="!apiError && openTickets.length === 0">
                  <td colspan="6" class="empty-state">
                    <span class="empty-icon">📭</span>
                    ไม่พบรายการ
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <div v-show="activeTab === 'completed'">
            <table>
              <thead>
                <tr>
                  <th style="width: 50px;">ดู/แก้ไข</th>
                  <th>เลขที่บัตร</th>
                  <th>ทะเบียนรถ</th>
                  <th>ประเภทรายงาน</th>
                  <th>เวลาออก</th>
                  <th>น้ำหนักสุทธิ (กก.)</th>
                </tr>
              </thead>
              <tbody>
                <tr 
                  v-for="ticket in completedTickets" 
                  :key="ticket.WE_ID" 
                  @click="selectTicket(ticket.WE_ID)"
                  :class="{ 'clickable-row': true, 'active-row': selectedTicketId === ticket.WE_ID }"
                  :data-ticket-id="ticket.WE_ID"
                >
                  <td class="view-cell">
                    <button 
                      class="view-btn" 
                      @click.stop="showTicketDetails(ticket.WE_ID)"
                      title="ดู/แก้ไขรายละเอียด"
                    >
                      🔍
                    </button>
                  </td>
                  <td>{{ ticket.WE_ID }}</td>
                  <td>{{ ticket.WE_LICENSE }}</td>
                  <td>{{ getReportTypeText(ticket) }}</td>
                  <td>{{ formatTime(ticket.WE_TIMEOUT) }}</td>
                  <td>{{ ticket.WE_WEIGHTNET?.toLocaleString() || 'N/A' }}</td>
                </tr>
                <tr v-if="!apiError && completedTickets.length === 0">
                  <td colspan="6" class="empty-state">
                    <span class="empty-icon">📭</span>
                    ไม่พบรายการ
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </main>
    
    <TicketDetailModal 
      :ticket="detailTicket" 
      :visible="isModalVisible" 
      @close="closeDetailModal"
      @ticket-updated="handleUpdateTicket" 
    />
     <CreateTicketModal
      :isVisible="isCreateModalVisible"
      :initialWeight="initialWeightForNewTicket"
      :carQueue="carQueue"
      :branchPrefix="branchPrefix"
      :continuousData="continuousWeighingData"
      @close="closeCreateModal"
      @create-ticket="createTicket"
    />
    <OfflineDataModal
      :isVisible="isOfflineModalVisible"
      :apiUrl="API_BASE_URL"
      :offlineApiUrl="API_OFFLINE_URL"
      @close="isOfflineModalVisible = false"
      @sync-completed="refreshAllData"
    />
     <button v-if="!isOnline" @click="isOfflineModalVisible = true" class="offline-sync-button">
      📦 ดูข้อมูล Offline และ Sync
    </button>
  </div>
</template>

<style scoped>
/* =============================================== */
/* 1. CSS Variables & Global Styles              */
/* =============================================== */
:root {
    --primary-color: #2563eb;
    --primary-hover: #1d4ed8;
    --secondary-color: #64748b;
    --success-color: #059669;
    --danger-color: #dc2626;
    --info-color: #0891b2;
    --bg-color: #f8fafc;
    --text-color: #1e293b;
    --card-bg: #ffffff;
    --highlight-color: #dbeafe;
    --border-color: #e2e8f0;
    --shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
}

html, body, #app {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
    height: 100%;
    overflow: hidden;
    background-color: var(--bg-color);
    font-family: 'Tahoma', sans-serif;
    color: var(--text-color);
}
::-webkit-scrollbar { width: 8px; }
::-webkit-scrollbar-track { background: #f1f5f9; border-radius: 4px; }
::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: #94a3b8; }

/* =============================================== */
/* 2. Main Layout (โครงสร้างหลัก)                 */
/* =============================================== */
.app-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
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
  width: 380px; 
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
.card {
  background-color: var(--card-bg);
  padding: 1.5rem;
  border-radius: 12px;
  box-shadow: var(--shadow);
  border: 1px solid var(--border-color);
}
.divider {
  border: none;
  border-top: 1px solid var(--border-color);
  margin: 0.5rem 0;
}
.error-message {
  color: var(--danger-color);
  background-color: #fef2f2;
  border: 1px solid #fecaca;
  padding: 1rem;
  border-radius: 8px;
}

/* =============================================== */
/* 4. Left Panel Components                        */
/* =============================================== */
.weight-display-container {
  position: relative;
}
.weight-display {
  font-weight: bold;
  color: var(--primary-color);
  background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
  padding: 2rem;
  border-radius: 16px;
  text-align: center; 
  border: 1px solid #bae6fd;
}
.weight-unit { font-size: 1.2rem; margin-top: 0.5rem; }
.connection-status {
  position: absolute;
  top: 1rem;
  right: 1rem;
  padding: 0.5rem 1rem;
  border-radius: 20px;
  font-size: 0.8rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.status-indicator {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}
.connection-status.connected { color: var(--success-color); background-color: #f0fdf4; }
.connection-status.connected .status-indicator { background-color: var(--success-color); }
.connection-status.disconnected { color: #d97706; background-color: #fffbeb; }
.connection-status.disconnected .status-indicator { background-color: #d97706; }
.connection-status.offline { color: #4b5563; background-color: #f3f4f6; }
.connection-status.offline .status-indicator { background-color: #4b5563; }


.create-ticket-button {
  width: 100%;
  padding: 1rem;
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 1.1rem;
  font-weight: 600;
  cursor: pointer;
  background: linear-gradient(135deg, var(--primary-color) 0%, var(--primary-hover) 100%);
}
.action-panel { display: flex; flex-direction: column; gap: 1rem; }
.selected-ticket-info {
  background: #f8fafc;
  padding: 1rem;
  border-radius: 8px;
  border: 1px solid var(--border-color);
}
.ticket-id-display { font-weight: 600; font-size: 1.1rem; color: var(--primary-color); }
.no-ticket-selected { font-style: italic; color: var(--secondary-color); }
.action-buttons-grid { display: grid; grid-template-columns: 1fr; gap: 0.75rem; }

.action-btn {
  width: 100%;
  padding: 0.75rem 0.5rem;
  border: none;
  border-radius: 8px;
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
  color: white;
}
.action-btn:disabled { opacity: 0.6; cursor: not-allowed; }
.cancel-btn { background-color: var(--secondary-color); grid-column: 1 / -1; }
.weigh-out-btn { background-color: var(--success-color); grid-column: 1 / -1; }
.continuous-btn { background-color: #7c3aed; grid-column: 1 / -1; }
.print-report-section {
    grid-column: 1 / -1;
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.75rem;
}
.report-preview { background-color: #f0f0f0; color: #333; }
.report-print { background-color: #e0e0e0; color: #333; }

/* =============================================== */
/* 5. Right Panel Components                       */
/* =============================================== */
.date-filter-container {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 1rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
}
.tabs {
  display: flex;
  border-bottom: 1px solid var(--border-color);
  margin-bottom: 1rem;
  flex-shrink: 0;
}
.tabs button {
  padding: 0.75rem 1.25rem;
  border: none;
  background-color: transparent;
  cursor: pointer;
  border-bottom: 3px solid transparent;
}
.tabs button.active {
  border-bottom: 3px solid var(--primary-color);
  font-weight: 600;
  color: var(--primary-color);
}
.table-instruction {
  background-color: #f0f9ff;
  border: 1px solid #bae6fd;
  border-radius: 8px;
  padding: 0.75rem 1rem;
  margin-bottom: 1rem;
  font-size: 0.9rem;
  color: var(--info-color);
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-shrink: 0;
}
.instruction-icon {
  font-size: 1rem;
}
.table-container { flex-grow: 1; overflow-y: auto; min-height: 0; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 0.75rem; border-bottom: 1px solid var(--border-color); text-align: left; white-space: nowrap; }
th { background-color: #f8fafc; position: sticky; top: 0; }
.clickable-row { cursor: pointer; }
.clickable-row:hover { background-color: #f8fafc; }
.active-row { background: var(--highlight-color) !important; font-weight: 600; }
.empty-state { text-align: center; padding: 2rem; color: var(--secondary-color); }

.view-cell {
  text-align: center;
  padding: 0.5rem;
}
.view-btn {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 1.2rem;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  transition: all 0.2s ease;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
}
.view-btn:hover {
  background-color: var(--primary-color);
  color: white;
  transform: scale(1.1);
}
.view-btn:active {
  transform: scale(0.95);
}

.offline-sync-button {
  position: fixed;
  bottom: 20px;
  right: 20px;
  z-index: 1000;
  padding: 12px 20px;
  background-color: #ff9800;
  color: white;
  border: none;
  border-radius: 25px;
  cursor: pointer;
  font-size: 1rem;
  font-weight: bold;
  box-shadow: 0 4px 8px rgba(0,0,0,0.2);
}
</style>