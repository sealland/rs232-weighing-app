<script setup>
import { ref, onMounted, computed, watch } from 'vue'
import TicketDetailModal from './components/TicketDetailModal.vue'
import CreateTicketModal from './components/CreateTicketModal.vue'

const API_BASE_URL = 'http://192.168.132.7:8000';  // เปลี่ยนเป็น IP ของเครื่อง Dev
const WEBSOCKET_URL = 'ws://192.168.132.7:8765';   // เปลี่ยนเป็น IP ของเครื่อง Dev

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

// เพิ่ม state สำหรับการเลือกการดำเนินการ
const printAction = ref('preview') // 'preview', 'print', หรือ 'download'


// --- Computed Property ---
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

// --- API & WebSocket Config ---
// const API_BASE_URL = 'http://192.168.132.7:8000';
// const WEBSOCKET_URL = 'ws://localhost:8765';

// --- Functions: Data Fetching ---
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
    apiError.value = "ไม่สามารถดึงข้อมูลบัตรชั่ง 'เสร็จสิ้นแล้ว' ได้"
  }
}
async function fetchCarQueue() {
  try {
    const response = await fetch(`${API_BASE_URL}/api/car-queue/`);
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
  await fetchCarQueue();
  const weightValue = parseInt(currentWeight.value.replace(/,/g, ''), 10);
  if (isNaN(weightValue)) {
     alert('ค่าน้ำหนักไม่ถูกต้อง');
     return;
  }
  initialWeightForNewTicket.value = weightValue;
  isCreateModalVisible.value = true;
}

// เพิ่มฟังก์ชันใหม่สำหรับจัดการเมื่อสร้างบัตรชั่งใหม่สำเร็จ
async function handleTicketCreated(newTicket) {
  console.log('New ticket created:', newTicket);
  
  // อัปเดตรายการบัตรชั่งที่กำลังดำเนินการ
  await fetchOpenTickets(selectedDate.value);
  
  // อัปเดตรายการบัตรชั่งที่เสร็จสิ้นแล้ว
  await fetchCompletedTickets(selectedDate.value);
  
  // ปิด modal
  isCreateModalVisible.value = false;
  
  // เลือกบัตรชั่งที่สร้างใหม่โดยอัตโนมัติ
  selectedTicketId.value = newTicket.WE_ID;
  
  // ตรวจสอบว่าบัตรชั่งใหม่อยู่ในตารางไหน
  const isInOpenTickets = openTickets.value.some(ticket => ticket.WE_ID === newTicket.WE_ID);
  const isInCompletedTickets = completedTickets.value.some(ticket => ticket.WE_ID === newTicket.WE_ID);
  
  // สลับไปยัง tab ที่มีบัตรชั่งใหม่
  if (isInOpenTickets) {
    activeTab.value = 'inProgress';
  } else if (isInCompletedTickets) {
    activeTab.value = 'completed';
  }
  
  // แสดงข้อความสำเร็จ
  alert(`สร้างบัตรชั่งใหม่สำเร็จ!\nเลขที่บัตร: ${newTicket.WE_ID}`);
  
  // เลื่อนไปยังบัตรชั่งที่เลือก (optional)
  setTimeout(() => {
    const selectedElement = document.querySelector(`[data-ticket-id="${newTicket.WE_ID}"]`);
    if (selectedElement) {
      selectedElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, 100);
}

async function showTicketDetails(ticket_id) {
  selectTicket(ticket_id);
  try {
    const response = await fetch(`${API_BASE_URL}/api/tickets/${ticket_id}`);
    if (!response.ok) throw new Error(`Ticket not found`);
    detailTicket.value = await response.json();
    isModalVisible.value = true;
  } catch (error) {
    console.error("Failed to fetch ticket details:", error);
    alert("ไม่สามารถดึงข้อมูลรายละเอียดได้");
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
      const response = await fetch(`${API_BASE_URL}/api/tickets/${ticketId}`);
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
    const response = await fetch(`${API_BASE_URL}/api/tickets/`, {
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
    const response = await fetch(`${API_BASE_URL}/api/tickets/${ticketIdToUpdate}/weigh-out`, {
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
    const response = await fetch(`${API_BASE_URL}/api/tickets/${ticketIdToCancel}/cancel`, {
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
      const response = await fetch(`${API_BASE_URL}/api/tickets/${selectedTicketId.value}`);
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
    const proxyUrl = `${API_BASE_URL}/api/reports/${cleanTicketId}/download/${reportType}`;
    
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
    const proxyUrl = `${API_BASE_URL}/api/reports/${cleanTicketId}/download/${reportType}`;
    
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
  // ดึงค่ามาจาก eventData ที่ส่งมาใหม่
  const updatePayload = eventData.payload;
  const ticketId = eventData.ticketId;

  // --- จุดตรวจสอบใหม่ ---
  if (!ticketId) {
    console.error("Update failed: No ticketId was provided.");
    alert("เกิดข้อผิดพลาด: ไม่พบ ID ของบัตรชั่ง");
    return;
  }
  
  console.log(`--- [App.vue] Starting update for ticket ID: ${ticketId} ---`);
  
  isUpdatingTicket.value = true;
  let hasError = false;

  try {
    // --- ส่วนที่ 1: อัปเดตข้อมูลหลัก (ใช้ ticketId ที่รับมา) ---
    console.log("Sending main data update (PATCH):", updatePayload.mainData);
    const mainResponse = await fetch(`${API_BASE_URL}/api/tickets/${ticketId}`, { // <-- ใช้ ticketId
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updatePayload.mainData),
    });

    if (!mainResponse.ok) {
      hasError = true;
      console.error('Failed to update main ticket data:', await mainResponse.text());
      alert('เกิดข้อผิดพลาดในการอัปเดตข้อมูลหลัก');
    }

    // --- ส่วนที่ 2: ถ้าไม่มี Error และมีรายการใหม่ให้แทนที่ ให้เรียก API "แทนที่" ---
    if (!hasError && updatePayload.newItems) {
      console.log("Sending new items to replace (PUT):", updatePayload.newItems);
      const itemsResponse = await fetch(`${API_BASE_URL}/api/tickets/${ticketId}/items`, { // <-- ใช้ ticketId
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
      alert('แก้ไขข้อมูลสำเร็จ!');
      await refreshTicketData(ticketId); // รีเฟรชข้อมูลทั้งหมด
    }
    
  } catch (error) {
    console.error('Error during ticket update process:', error);
    alert('เกิดข้อผิดพลาดร้ายแรงในการแก้ไขข้อมูล');
  } finally {
    isUpdatingTicket.value = false;
  }
}
async function refreshTicketData(ticketId) {
  closeModal(); 
  await new Promise(resolve => setTimeout(resolve, 100));
  await Promise.all([
      fetchOpenTickets(selectedDate.value),
      fetchCompletedTickets(selectedDate.value)
  ]);
  
  // อัปเดตข้อมูลรายละเอียดของบัตรชั่งที่เลือก
  if (selectedTicketId.value === ticketId) {
    try {
      const response = await fetch(`${API_BASE_URL}/api/tickets/${ticketId}`);
      if (response.ok) {
        selectedTicketDetail.value = await response.json();
      }
    } catch (error) {
      console.error('Failed to refresh ticket detail:', error);
    }
  }
  
  await showTicketDetails(ticketId);
}

// --- Watcher & Lifecycle Hook ---
watch(selectedDate, async (newDate) => {
  apiError.value = null;
  selectedTicketId.value = null;
  await fetchOpenTickets(newDate);
  await fetchCompletedTickets(newDate);
});
onMounted(async () => {
  await fetchOpenTickets(selectedDate.value);
  await fetchCompletedTickets(selectedDate.value);
  connectWebSocket();
});

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
    const proxyUrl = `${API_BASE_URL}/api/reports/${ticketId}/download/${reportType}`;
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
    
    const response = await fetch(`${API_BASE_URL}/api/print/${ticketId}/${reportType}`, {
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
        <!-- ส่วนแสดงน้ำหนัก Real-time -->
        <div class="weight-display-container">
          <div class="weight-display">
            <div class="weight-icon">⚖️</div>
            <span :style="{ fontSize: 'clamp(2.5rem, 10vw, 4.5rem)' }">{{ currentWeight }}</span>
            <div class="weight-unit">กิโลกรัม</div>
          </div>
          <div class="connection-status" :class="wsStatus.toLowerCase()">
            <span class="status-icon">🔗</span>
            <span class="status-text">{{ wsStatus }}</span>
          </div>
        </div>

        <!-- เส้นแบ่ง -->
        <hr class="divider">
        
        <div class="create-ticket-panel">
          <button @click="openCreateTicketModal" class="create-ticket-button">
            <span class="button-icon">➕</span>
            สร้างบัตรชั่งใหม่
          </button>
        </div>

        <!-- ========================================================== -->
        <!-- ส่วน Action Panel (ปรับปรุงใหม่ทั้งหมด) -->
        <!-- ========================================================== -->
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

          <!-- แสดงปุ่มก็ต่อเมื่อมีการเลือกบัตรแล้ว -->
          <div v-if="selectedTicketObject" class="action-buttons-grid">
            
            <!-- ปุ่มที่แสดงเสมอ -->
            <button class="action-btn detail-btn" @click="showTicketDetails(selectedTicketId)">
              <span class="button-icon">🔍</span>
              ดูรายละเอียด
            </button>
            <button 
              class="action-btn cancel-btn"
              @click="handleCancelTicket"
              :disabled="isCancellingTicket"
            >
              <span class="button-icon">❌</span>
              {{ isCancellingTicket ? 'กำลังยกเลิก...' : 'ยกเลิกบัตรชั่ง' }}
            </button>

            <!-- V V V V V V V V V V V V V V V V V V V V V V V V V V V V -->
            <!-- ปุ่มที่แสดงตามเงื่อนไข -->
            <template v-if="selectedTicketObject.WE_WEIGHTOUT">
              <!-- กรณี: ชั่งออกไปแล้ว -->
              <button 
                class="action-btn continuous-btn"
                @click="handleStartContinuousWeighing"
              >
                <span class="button-icon">🔄</span>
                ชั่งต่อเนื่อง
              </button>
            </template>
            <template v-else>
              <!-- กรณี: ยังไม่ได้ชั่งออก -->
              <button 
                class="action-btn weigh-out-btn"
                @click="handleWeighOut"
                :disabled="isUpdatingTicket"
              >
                <span class="button-icon">📤</span>
                {{ isUpdatingTicket ? 'กำลังบันทึก...' : 'บันทึกน้ำหนักชั่งออก' }}
              </button>
            </template>
            <!-- ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ -->

            <!-- ส่วนพิมพ์รายงาน (แสดงเสมอเมื่อมีบัตรที่เลือก) -->
            <div class="print-report-section">
              <!-- หัวข้อส่วนพิมพ์รายงาน -->
              <div class="print-section-header">
                <span class="print-icon">📄</span>
                <span class="report-type-indicator" v-if="selectedTicketDetail">
                  ({{ getReportTypeText(selectedTicketDetail) }})
                </span>
              </div>
              
              <!-- ตัวเลือกการดำเนินการ -->
              <div class="print-options">
                <label class="print-option" :class="{ 'selected': printAction === 'preview' }">
                  <input 
                    type="radio" 
                    v-model="printAction" 
                    value="preview" 
                    name="printAction"
                  >
                  <div class="option-content">
                    <span class="option-icon">🔍</span>
                    <span class="option-text">Preview</span>
                  </div>
                </label>
                
                <label class="print-option" :class="{ 'selected': printAction === 'print' }">
                  <input 
                    type="radio" 
                    v-model="printAction" 
                    value="print" 
                    name="printAction"
                  >
                  <div class="option-content">
                    <span class="option-icon">🖨️</span>
                    <span class="option-text">พิมพ์</span>
                  </div>
                </label>
                
                <label class="print-option" :class="{ 'selected': printAction === 'download' }">
                  <input 
                    type="radio" 
                    v-model="printAction" 
                    value="download" 
                    name="printAction"
                  >
                  <div class="option-content">
                    <span class="option-icon">💾</span>
                    <span class="option-text">ดาวน์โหลด</span>
                  </div>
                </label>
              </div>
              
              <!-- ปุ่มดำเนินการ -->
              <button 
                class="action-btn print-btn"
                @click="handlePrintReport"
                :disabled="isPrintingReport || !printAction"
              >
                <span class="button-icon">
                  {{ isPrintingReport ? '⏳' : (printAction === 'preview' ? '👁️' : printAction === 'print' ? '🖨️' : '💾') }}
                </span>
                {{ isPrintingReport ? 'กำลังดำเนินการ...' : (printAction === 'preview' ? 'ดูตัวอย่าง' : printAction === 'print' ? 'สั่งพิมพ์' : 'ดาวน์โหลด') }}
              </button>
            </div>

          </div>
        </div>
        <!-- ========================================================== -->
      </div>

      <div class="right-panel card">
        <!-- Tabs สำหรับสลับมุมมอง -->
        <div class="date-filter-container">
          <label for="date-filter">📅 เลือกวันที่:</label>
          <input type="date" id="date-filter" v-model="selectedDate">
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

        <!-- แสดงข้อความ Error ถ้ามี -->
        <div v-if="apiError" class="error-message">
          <span class="error-icon">🚨</span>
          {{ apiError }}
        </div>

        <!-- ส่วนแสดงตาราง -->
        <div class="table-container" v-else>
          <!-- ตารางสำหรับบัตรกำลังดำเนินการ -->
          <div v-show="activeTab === 'inProgress'">
            <table>
              <thead>
                <tr>
                  <th>🎫 เลขที่บัตร</th>
                  <th>🚗 ทะเบียนรถ</th>
                  <th>👤 ชื่อลูกค้า</th>
                  <th>⏰ เวลาชั่งเข้า</th>
                  <th>⚖️ น้ำหนักชั่งเข้า (กก.)</th>
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
                  <td>
                    <button class="detail-btn" @click.stop="showTicketDetails(ticket.WE_ID)">
                      <span class="detail-icon">🔍</span>
                    </button>
                    {{ ticket.WE_ID }}
                  </td>
                  <td>{{ ticket.WE_LICENSE }}</td>
                  <td>{{ ticket.WE_VENDOR || '-' }}</td>
                  <td>{{ new Date(ticket.WE_TIMEIN).toLocaleString('th-TH') }}</td>
                  <td>{{ ticket.WE_WEIGHTIN.toLocaleString('en-US') }}</td>
                </tr>
                <tr v-if="!apiError && openTickets.length === 0">
                  <td colspan="5" class="empty-state">
                    <span class="empty-icon">📭</span>
                    ไม่พบรายการ
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- ตารางสำหรับบัตรที่เสร็จแล้ว -->
          <div v-show="activeTab === 'completed'">
            <table>
              <thead>
                <tr>
                  <th>🎫 เลขที่บัตร</th>
                  <th>🚗 ทะเบียนรถ</th>
                  <th>👤 ชื่อลูกค้า</th>
                  <th>⏰ เวลาชั่งออก</th>
                  <th>⚖️ น้ำหนักสุทธิ (กก.)</th>
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
                  <td>
                    <button class="detail-btn" @click.stop="showTicketDetails(ticket.WE_ID)">
                      <span class="detail-icon">🔍</span>
                    </button>
                    {{ ticket.WE_ID }}
                  </td>
                  <td>{{ ticket.WE_LICENSE }}</td>
                  <td>{{ ticket.WE_VENDOR || '-' }}</td>
                  <td>{{ new Date(ticket.WE_TIMEOUT).toLocaleString('th-TH') }}</td>
                  <td>{{ ticket.WE_WEIGHTNET?.toLocaleString('en-US') || '0' }}</td>
                </tr>
                <tr v-if="!apiError && completedTickets.length === 0">
                  <td colspan="5" class="empty-state">
                    <span class="empty-icon">📭</span>
                    ไม่พบรายการของวันนี้
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </main>
    
    <!-- Modal Component สำหรับแสดงรายละเอียด -->
    <TicketDetailModal 
      :ticket="detailTicket"
      :visible="isModalVisible"
      @close="closeModal"
      @weigh-out="handleWeighOut"
      @ticket-updated="handleTicketUpdate"
      @view-ticket="handleViewTicket"
    />
    <!-- *** เพิ่ม Prop ใหม่ 'continuousData' เข้าไป *** -->
    <CreateTicketModal
    :visible="isCreateModalVisible"
    :initial-weight-in="initialWeightForNewTicket"
    :car-queue="carQueue"
    :continuous-data-from-prev-ticket="continuousWeighingData"
    @close="isCreateModalVisible = false"
    @ticket-created="handleTicketCreated"
    />
  </div>
</template>

<style scoped>
/* =============================================== */
/* 1. CSS Variables & Global Styles              */
/* =============================================== */
:root {
    --primary-color: #2563eb; /* สีน้ำเงินเข้ม */
    --primary-hover: #1d4ed8;
    --secondary-color: #64748b;
    --success-color: #059669; /* สีเขียว */
    --success-hover: #047857;
    --warning-color: #d97706; /* สีส้ม */
    --warning-hover: #b45309;
    --danger-color: #dc2626; /* สีแดง */
    --danger-hover: #b91c1c;
    --info-color: #0891b2; /* สีฟ้า */
    --info-hover: #0e7490;
    --bg-color: #f8fafc;
    --text-color: #1e293b;
    --card-bg: #ffffff;
    --error-color: #dc2626;
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
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    color: var(--text-color);
}

/* Global button styles */
button {
  transition: all 0.2s ease-in-out;
}

button:focus {
  outline: none;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}

/* Scrollbar styling */
::-webkit-scrollbar {
  width: 8px;
}

::-webkit-scrollbar-track {
  background: #f1f5f9;
  border-radius: 4px;
}

::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 4px;
}

::-webkit-scrollbar-thumb:hover {
  background: #94a3b8;
}

/* =============================================== */
/* 2. Main Layout (โครงสร้างหลัก)                 */
/* =============================================== */
.app-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
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

/* =============================================== */
/* 3. Reusable Components                          */
/* =============================================== */
.card {
  background-color: var(--card-bg);
  padding: 1.5rem;
  border-radius: 12px;
  box-shadow: var(--shadow);
  border: 1px solid var(--border-color);
}

.divider {
  border: none;
  border-top: 2px solid var(--border-color);
  margin: 0.5rem 0;
}

.error-message {
  color: var(--error-color);
  background-color: #fef2f2;
  border: 1px solid #fecaca;
  padding: 1rem;
  border-radius: 8px;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-weight: 500;
}

.error-icon {
  font-size: 1.2rem;
}

/* =============================================== */
/* 4. Left Panel Components                        */
/* =============================================== */

.weight-display-container {
  position: relative;
}

.weight-display {
  font-size: 12rem;
  font-weight: bold;
  color: var(--primary-color);
  background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
  padding: 2rem;
  border-radius: 16px;
  text-align: center; 
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  overflow: hidden;
  line-height: 1;
  border: 2px solid #bae6fd;
  position: relative;
}

.weight-icon {
  font-size: 2rem;
  margin-bottom: 0.5rem;
  opacity: 0.8;
}

.weight-unit {
  font-size: 1.2rem;
  color: var(--secondary-color);
  margin-top: 0.5rem;
  font-weight: 500;
}

.connection-status {
  position: absolute;
  top: 1rem;
  right: 1rem;
  padding: 0.5rem 1rem;
  border-radius: 20px;
  font-size: 0.8rem;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 0.3rem;
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(10px);
}

.connection-status.connected {
  color: var(--success-color);
  background-color: #f0fdf4;
}

.connection-status.connecting,
.connection-status.disconnected {
  color: var(--warning-color);
  background-color: #fffbeb;
}

.connection-status.connection-error {
  color: var(--danger-color);
  background-color: #fef2f2;
}

.status-icon {
  font-size: 0.9rem;
}

.action-panel {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.selected-ticket-info {
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  padding: 1rem;
  border-radius: 8px;
  border: 1px solid var(--border-color);
}

.selected-ticket-info label {
  font-weight: 600;
  display: block;
  font-size: 0.9rem;
  color: var(--secondary-color);
  margin-bottom: 0.5rem;
}

.ticket-id-display {
  font-weight: 600;
  font-size: 1.1rem;
  color: var(--primary-color);
  background-color: #eff6ff;
  padding: 0.8rem;
  border-radius: 8px;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  border: 1px solid #bfdbfe;
}

.ticket-icon {
  font-size: 1.2rem;
}

.license-text {
  color: var(--secondary-color);
  font-size: 0.9rem;
}

.no-ticket-selected {
  font-style: italic;
  color: var(--secondary-color);
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.8rem;
  background-color: #f8fafc;
  border-radius: 8px;
  border: 1px dashed var(--border-color);
}

.no-selection-icon {
  font-size: 1.1rem;
}

/* ======================================== */
/*  Styles for the New Action Panel         */
/* ======================================== */

.action-buttons-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
  margin-bottom: 0.5rem;
}

.action-btn {
  width: 100%;
  padding: 0.75rem 0.5rem;
  border: none;
  border-radius: 8px;
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease-in-out;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.action-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.15);
}

.action-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  transform: none;
}

.button-icon {
  font-size: 1rem;
}

/* Detail Button (Blue) */
.action-btn.detail-btn {
  background: linear-gradient(135deg, var(--info-color) 0%, var(--info-hover) 100%);
}

.action-btn.detail-btn:hover:not(:disabled) {
  background: linear-gradient(135deg, var(--info-hover) 0%, #0c4a6e 100%);
}

/* Cancel Button (Gray) */
.action-btn.cancel-btn {
  background: linear-gradient(135deg, var(--secondary-color) 0%, #475569 100%);
}

.action-btn.cancel-btn:hover:not(:disabled) {
  background: linear-gradient(135deg, #475569 0%, #334155 100%);
}

/* Weigh-out Button (Green) */
.action-btn.weigh-out-btn {
  background: linear-gradient(135deg, var(--success-color) 0%, var(--success-hover) 100%);
  grid-column: 1 / -1;
}

.action-btn.weigh-out-btn:hover:not(:disabled) {
  background: linear-gradient(135deg, var(--success-hover) 0%, #065f46 100%);
}

/* Continuous Weighing Button (Purple) */
.action-btn.continuous-btn {
  background: linear-gradient(135deg, #7c3aed 0%, #6d28d9 100%);
  grid-column: 1 / -1;
}

.action-btn.continuous-btn:hover:not(:disabled) {
  background: linear-gradient(135deg, #6d28d9 0%, #5b21b6 100%);
}

.create-ticket-button {
  width: 100%;
  padding: 1rem;
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 1.1rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease-in-out;
  background: linear-gradient(135deg, var(--primary-color) 0%, var(--primary-hover) 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  box-shadow: var(--shadow);
}

.create-ticket-button:hover {
  background: linear-gradient(135deg, var(--primary-hover) 0%, #1e40af 100%);
  transform: translateY(-1px);
  box-shadow: 0 6px 12px rgba(37, 99, 235, 0.3);
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
  border-bottom: 2px solid var(--border-color);
  flex-shrink: 0;
}

.date-filter-container label {
  font-weight: 600;
  color: var(--text-color);
}

.date-filter-container input[type="date"] {
  padding: 0.5rem;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  font-size: 1rem;
  background-color: white;
  transition: border-color 0.2s;
}

.date-filter-container input[type="date"]:focus {
  outline: none;
  border-color: var(--primary-color);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}

.tabs {
  display: flex;
  border-bottom: 2px solid var(--border-color);
  margin-bottom: 1rem;
  flex-shrink: 0;
}

.tabs button {
  padding: 1rem 1.5rem;
  border: none;
  background-color: transparent;
  cursor: pointer;
  font-size: 1rem;
  color: var(--secondary-color);
  position: relative;
  top: 2px;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  transition: all 0.2s ease-in-out;
  border-radius: 8px 8px 0 0;
}

.tabs button:hover {
  background-color: #f1f5f9;
  color: var(--primary-color);
}

.tabs button.active {
  border-bottom: 3px solid var(--primary-color);
  font-weight: 600;
  color: var(--primary-color);
  background-color: #eff6ff;
}

.tab-icon {
  font-size: 1.1rem;
}

/* --- Table Styles --- */
.table-container {
  flex-grow: 1;
  overflow-y: auto;
  min-height: 0;
  border-radius: 8px;
  border: 1px solid var(--border-color);
  background-color: white;
}

table {
  width: 100%;
  border-collapse: collapse;
}

th, td {
  padding: 1rem;
  border-bottom: 1px solid var(--border-color);
  text-align: left;
  white-space: nowrap;
}

th {
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  position: sticky;
  top: 0;
  font-weight: 600;
  color: var(--text-color);
  border-bottom: 2px solid var(--border-color);
}

.clickable-row {
  cursor: pointer;
  transition: all 0.2s ease-in-out;
}

.clickable-row:hover {
  background-color: #f8fafc;
  transform: translateX(2px);
}

.active-row {
  background: linear-gradient(135deg, var(--highlight-color) 0%, #bfdbfe 100%) !important;
  font-weight: 600;
  border-left: 4px solid var(--primary-color);
}

.detail-btn {
  margin-right: 0.5rem;
  padding: 0.3rem 0.6rem;
  font-size: 0.8rem;
  cursor: pointer;
  background: linear-gradient(135deg, var(--info-color) 0%, var(--info-hover) 100%);
  color: white;
  border: none;
  border-radius: 4px;
  transition: all 0.2s ease-in-out;
}

.detail-btn:hover {
  background: linear-gradient(135deg, var(--info-hover) 0%, #0c4a6e 100%);
  transform: scale(1.05);
}

.detail-icon {
  font-size: 0.8rem;
}

.empty-state {
  text-align: center;
  padding: 2rem;
  color: var(--secondary-color);
  font-style: italic;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
}

.empty-icon {
  font-size: 1.5rem;
}

/* Responsive Design */
@media (max-width: 1200px) {
  .left-panel {
    width: 320px;
  }
  
  .weight-display {
    font-size: 4rem;
    padding: 1.5rem;
  }
}

@media (max-width: 768px) {
  main {
    flex-direction: column;
    gap: 1rem;
    padding: 1rem;
  }
  
  .left-panel {
    width: 100%;
  }
  
  .action-buttons-grid {
    grid-template-columns: 1fr;
  }
  
  .weight-display {
    font-size: 3rem;
    padding: 1rem;
  }
}

/* เพิ่ม CSS สำหรับ highlight บรรทัดที่เลือก */
.selected-row {
  background-color: var(--highlight-color) !important;
  border-left: 4px solid var(--primary-color);
}

.ticket-row {
  cursor: pointer;
  transition: background-color 0.2s ease;
}

.ticket-row:hover {
  background-color: #f1f5f9;
}

/* Print Report Section - ปรับปรุงใหม่ */
.print-report-section {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  padding: 0.8rem;
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  border-radius: 10px;
  border: 1px solid var(--border-color);
  margin-top: 0.5rem;
}

.print-section-header {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding-bottom: 0.4rem;
  border-bottom: 1px solid var(--border-color);
}

.print-icon {
  font-size: 1rem;
}

.print-title {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--text-color);
}

.report-type-indicator {
  font-size: 0.75rem;
  color: var(--primary-color);
  font-weight: 500;
  margin-left: 0.3rem;
}

.print-options {
  display: flex;
  gap: 0.3rem;
  width: 100%;
  flex-wrap: wrap;
}

.print-option {
  flex: 1;
  min-width: 80px;
  display: flex;
  align-items: center;
  cursor: pointer;
  padding: 0.4rem;
  border-radius: 6px;
  background: white;
  border: 1px solid var(--border-color);
  transition: all 0.2s ease-in-out;
  position: relative;
  overflow: hidden;
}

.print-option:hover {
  border-color: var(--primary-color);
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(37, 99, 235, 0.15);
}

.print-option.selected {
  border-color: var(--primary-color);
  background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
  box-shadow: 0 2px 8px rgba(37, 99, 235, 0.2);
}

.print-option input[type="radio"] {
  position: absolute;
  opacity: 0;
  cursor: pointer;
}

.option-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.15rem;
  width: 100%;
  text-align: center;
}

.option-icon {
  font-size: 1rem;
  margin-bottom: 0.15rem;
}

.option-text {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-color);
}

.print-option.selected .option-text {
  color: var(--primary-color);
}

/* ปุ่มดำเนินการ */
.print-btn {
  background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
  border: none;
  padding: 0.6rem 0.8rem;
  border-radius: 6px;
  font-size: 0.85rem;
  font-weight: 600;
  color: white;
  cursor: pointer;
  transition: all 0.2s ease-in-out;
  box-shadow: 0 2px 4px rgba(245, 158, 11, 0.3);
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.4rem;
}

.print-btn:hover:not(:disabled) {
  background: linear-gradient(135deg, #d97706 0%, #b45309 100%);
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(245, 158, 11, 0.4);
}

.print-btn:disabled {
  background: linear-gradient(135deg, #9ca3af 0%, #6b7280 100%);
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

/* Responsive Design สำหรับส่วนพิมพ์รายงาน */
@media (max-width: 768px) {
  .print-options {
    flex-direction: column;
    gap: 0.3rem;
  }
  
  .print-option {
    padding: 0.6rem;
  }
  
  .option-content {
    flex-direction: row;
    justify-content: flex-start;
    text-align: left;
    gap: 0.5rem;
  }
  
  .option-icon {
    margin-bottom: 0;
  }
}
</style>