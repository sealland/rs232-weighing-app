<script setup>
import { ref, watch, computed } from 'vue';

const props = defineProps({
  ticket: { type: Object, default: null },
  visible: { type: Boolean, default: false }
});
const emit = defineEmits(['close', 'weigh-out', 'ticket-updated', 'view-ticket']);

// --- State Management for Edit Mode ---
const isEditing = ref(false);
const editableData = ref({});
// --- เพิ่ม State สำหรับน้ำหนักก่อนหักและน้ำหนักที่หัก ---
const editableWeightBeforeDeduction = ref(0);
const editableWeightDeduction = ref(0);

// State for "แก้ไข/เพิ่มรายการสินค้า"
const planIdToSearch = ref('');
const searchResults = ref([]);
const newItemsToReplace = ref([]);
const searchLoading = ref(false);
const searchError = ref(null);
// --- เพิ่ม Computed Property ใหม่ ---
const hasSelectedSearchResults = computed(() => {
  // ตรวจสอบว่าใน searchResults มี item ไหนที่มี selected: true บ้างหรือไม่
  return searchResults.value.some(item => item.selected);
});
// ---------------------------------

// --- Watcher ---
watch(() => props.visible, (isVisible) => {
  if (isVisible) {
    isEditing.value = false;
    planIdToSearch.value = '';
    searchResults.value = [];
    newItemsToReplace.value = [];
    searchError.value = null;
  }
});

// เพิ่ม watcher สำหรับอัปเดตข้อมูลเมื่อ ticket เปลี่ยน
watch(() => props.ticket, (newTicket, oldTicket) => {
  console.log("🔄 Ticket watcher triggered");
  console.log("🔄 Old ticket:", oldTicket);
  console.log("🔄 New ticket:", newTicket);
  console.log("🔄 isEditing.value:", isEditing.value);
  
  if (newTicket) {
    console.log("🔄 Ticket data updated in modal:", newTicket);
    console.log("🔄 New WE_TRUCK_CHAR:", newTicket.WE_TRUCK_CHAR);
    
    // อัปเดต editableData ถ้ากำลังอยู่ในโหมดแก้ไข
    if (isEditing.value) {
      console.log("🔄 Updating editableData because isEditing is true");
      editableData.value = {
        WE_LICENSE: newTicket.WE_LICENSE,
        WE_VENDOR: newTicket.WE_VENDOR,
        WE_QTY: newTicket.WE_QTY,
        WE_DRIVER: newTicket.WE_DRIVER,
        WE_TRUCK_CHAR: newTicket.WE_TRUCK_CHAR,
      };
      console.log("🔄 Updated editableData:", editableData.value);
    } else {
      console.log("🔄 Not updating editableData because isEditing is false");
    }
  }
}, { deep: true });

// --- Functions ---
// --- เพิ่มฟังก์ชันใหม่ ---
function toggleSelectAllResults(event) {
  const isChecked = event.target.checked;
  searchResults.value.forEach(item => item.selected = isChecked);
}
// --------------------
// --- ฟังก์ชัน `addSelectedToNewItems` (ยังคงถูกต้อง) ---
function addSelectedToNewItems() {
  const selected = searchResults.value.filter(item => item.selected);
  for (const item of selected) {
    if (!newItemsToReplace.value.some(newItem => newItem.VBELN === item.VBELN && newItem.POSNR === item.POSNR)) {
      // ตอนเพิ่มลงตะกร้า จะมี editable_qty ติดไปด้วยโดยอัตโนมัติ
      newItemsToReplace.value.push(item);
    }
  }
  searchResults.value = [];
  planIdToSearch.value = '';
}

function startEditing() {
  // 1. ตรวจสอบก่อนว่ามี ticket data จริงๆ
  if (!props.ticket) return;

  console.log('🔧 startEditing called with ticket:', props.ticket);
  console.log('🔧 Original WE_TRUCK_CHAR:', props.ticket.WE_TRUCK_CHAR);

  // 2. Copy ข้อมูลหลัก - เพิ่มข้อมูลคนขับและประเภทรถ
  editableData.value = {
    WE_LICENSE: props.ticket.WE_LICENSE,
    WE_VENDOR: props.ticket.WE_VENDOR,
    WE_QTY: props.ticket.WE_QTY,
    // --- เพิ่มข้อมูลคนขับและประเภทรถ ---
    WE_DRIVER: props.ticket.WE_DRIVER,
    WE_TRUCK_CHAR: props.ticket.WE_TRUCK_CHAR,
  };
  
  console.log('🔧 editableData.value after setting:', editableData.value);
  
  // --- ตั้งค่าน้ำหนักก่อนหักและน้ำหนักที่หัก ---
  editableWeightBeforeDeduction.value = props.ticket.WE_WEIGHTTOT || 0;
  editableWeightDeduction.value = props.ticket.WE_WEIGHTMINUS || 0;
  
  // 3. Copy รายการสินค้า (ถ้ามี) ไปใส่ตะกร้า พร้อมสร้าง editable_qty
  if (props.ticket.items && Array.isArray(props.ticket.items)) {
    newItemsToReplace.value = props.ticket.items.map(item => ({
        ...item, 
        // สร้าง key ที่สอดคล้องกับผลการค้นหา
        MATNR: item.WE_MAT_CD, 
        ARKTX: item.WE_MAT,
        LFIMG: item.WE_QTY,
        VRKME: item.WE_UOM,
        // --- จุดแก้ไขที่สำคัญที่สุด ---
        // สร้าง property 'editable_qty' โดยใช้ค่าจาก WE_QTY เดิม
        editable_qty: item.WE_QTY 
    }));
  } else {
    newItemsToReplace.value = [];
  }
  
  // 4. ตั้งค่า isEditing เป็น true เป็นสิ่งสุดท้าย
  isEditing.value = true;
}
function cancelEdit() {
  isEditing.value = false;
}

function updateItemQty(index, event) {
  // 1. ดึงค่าตัวเลขจาก input
  const newQty = parseInt(event.target.value, 10);
  
  // 2. ตรวจสอบว่าเป็นตัวเลขที่ถูกต้องหรือไม่
  if (!isNaN(newQty) && newItemsToReplace.value[index]) {
    // 3. อัปเดตค่าใน Array โดยตรง
    newItemsToReplace.value[index].editable_qty = newQty;
  }
}
function removeFromNewItems(index) {
  newItemsToReplace.value.splice(index, 1);
}

function handleSaveChanges() {
  if (!props.ticket) {
    console.error("handleSaveChanges failed: props.ticket is null");
    return;
  }

  // 2. ตรวจสอบสถานะว่าเป็น "ชั่งรวม" หรือไม่
  const isNowCombined = newItemsToReplace.value.length > 0;

  // 3. รวบรวมข้อมูลหลัก (mainData) - เพิ่มข้อมูลคนขับและประเภทรถ
  const mainDataPayload = {
    WE_LICENSE: editableData.value.WE_LICENSE,
    WE_VENDOR: editableData.value.WE_VENDOR,
    WE_QTY: isNowCombined ? null : editableData.value.WE_QTY,
    WE_DIREF: isNowCombined ? 'ชั่งรวม' : (props.ticket.items.length === 0 ? props.ticket.WE_DIREF : 'ชั่งแยก'),
    WE_MAT_CD: isNowCombined ? 'ชั่งรวม' : (props.ticket.items.length === 0 ? props.ticket.WE_MAT_CD : null),
    WE_MAT: isNowCombined ? 'ชั่งรวม' : (props.ticket.items.length === 0 ? props.ticket.WE_MAT : 'สินค้าชั่งแยก'),
    // --- เพิ่มข้อมูลคนขับและประเภทรถ ---
    WE_DRIVER: editableData.value.WE_DRIVER,
    WE_TRUCK_CHAR: editableData.value.WE_TRUCK_CHAR,
    // --- เพิ่มข้อมูลน้ำหนักก่อนหักและน้ำหนักที่หัก ---
    WE_WEIGHTTOT: editableWeightBeforeDeduction.value,
    WE_WEIGHTMINUS: editableWeightDeduction.value,
  };
  
  // 4. คำนวณและอัปเดตน้ำหนักสุทธิ
  const netWeight = editableWeightBeforeDeduction.value - editableWeightDeduction.value;
  mainDataPayload.WE_WEIGHTNET = netWeight;

  // 4. รวบรวมรายการสินค้าใหม่ (newItems)
  const newItemsPayload = isNowCombined
    ? newItemsToReplace.value.map(item => ({
        VBELN: item.VBELN,
        POSNR: item.POSNR,
        WE_MAT_CD: item.MATNR,
        WE_MAT: item.ARKTX,
        WE_QTY: item.editable_qty,
        WE_UOM: item.VRKME
      }))
    : null;

  // 5. สร้าง object สุดท้าย
  const finalPayload = {
    mainData: mainDataPayload,
    newItems: newItemsPayload,
  };

  const objectToEmit = { 
    payload: finalPayload, 
    ticketId: props.ticket.WE_ID.trim() // <-- ลบช่องว่างท้าย
  };
 // ========================== DEBUG HERE ==========================
 console.log('--- [Modal] ตรวจสอบข้อมูลก่อน Emit ---');
  console.log('1. Checking props.ticket:', JSON.parse(JSON.stringify(props.ticket)));
  console.log('2. Checking props.ticket.WE_ID:', props.ticket.WE_ID);
  console.log('3. Checking editableData.value:', JSON.parse(JSON.stringify(editableData.value)));
  console.log('4. Checking mainDataPayload:', JSON.parse(JSON.stringify(mainDataPayload)));
  console.log('5. Final object to emit:', JSON.parse(JSON.stringify(objectToEmit)));
  // ================================================================

  // ส่ง object ที่เตรียมไว้
  console.log("🔧 About to emit ticket-updated event with:", objectToEmit);
  emit('ticket-updated', objectToEmit);
  console.log("🔧 Event emitted successfully");
  
  console.log("🔧 Setting isEditing to false");
  isEditing.value = false;
  console.log("🔧 isEditing.value after setting to false:", isEditing.value);
}

async function handleAddSelectedItems() {
  if (selectedPlanItems.value.length === 0 || !props.ticket) return;

  const ticketId = props.ticket.WE_ID;
  
  // 1. แปลงข้อมูลจากผลการค้นหา (ShipmentPlanItem)
  // ให้เป็นรูปแบบที่ API ต้องการ (WeightTicketItemCreate)
  const itemsToCreate = selectedPlanItems.value.map(item => ({
    VBELN: item.VBELN,
    POSNR: item.POSNR,
    WE_MAT_CD: item.MATNR, // สังเกต: field name ไม่เหมือนกัน
    WE_MAT: item.ARKTX,    // สังเกต: field name ไม่เหมือนกัน
    WE_QTY: item.NTGEW,    // สังเกต: field name ไม่เหมือนกัน
    WE_UOM: item.VRKME     // สังเกต: field name ไม่เหมือนกัน
  }));

  // (เผื่อ Debug) แสดงข้อมูลที่จะส่งไป API
  console.log("Sending to API:", itemsToCreate);

  try {
    const response = await fetch(`${API_BASE_URL}/api/tickets/${ticketId}/items`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(itemsToCreate),
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || 'เกิดข้อผิดพลาดในการบันทึกรายการ');
    }

    alert('เพิ่มรายการสินค้าสำเร็จ!');
    
    // 2. ส่ง event กลับไปให้ App.vue เพื่อโหลดข้อมูลใหม่
    emit('ticket-updated');

  } catch (error) {
    console.error('Failed to add items:', error);
    alert(error.message);
  }
}

async function handleSearchPlan() {
  if (!planIdToSearch.value.trim()) {
    return;
  }

  searchLoading.value = true;
  searchError.value = null;
  searchResults.value = [];
  const API_BASE_URL = 'http://192.168.132.7:8000';

  try {
    const response = await fetch(`${API_BASE_URL}/api/shipment-plans/${planIdToSearch.value.trim()}`);
    if (!response.ok) {
      throw new Error('ไม่พบข้อมูลแผนการจัดส่ง');
    }
    
    const data = await response.json();
    if (data.length === 0) {
      searchError.value = `ไม่พบข้อมูลสำหรับเลขที่เอกสาร: ${planIdToSearch.value}`;
    } else {
      // เพิ่ม property 'selected' สำหรับ Checkbox
      searchResults.value = data.map(item => ({ 
        ...item, 
        selected: false,
        editable_qty: item.LFIMG // ใช้ LFIMG เป็นค่าเริ่มต้น
      }));
    }
  } catch (error) {
    searchError.value = error.message;
  } finally {
    searchLoading.value = false;
  }
}

// --- เพิ่มฟังก์ชันสำหรับคำนวณน้ำหนัก ---
function calculateWeightBeforeDeduction() {
  if (!props.ticket) return '-';
  
  // ถ้ามีข้อมูล WE_WEIGHTTOT ในฐานข้อมูล ให้ใช้ข้อมูลนั้น
  if (props.ticket.WE_WEIGHTTOT !== null && props.ticket.WE_WEIGHTTOT !== undefined) {
    return props.ticket.WE_WEIGHTTOT.toLocaleString('en-US') + ' กก.';
  }
  
  // ถ้าไม่มี ให้คำนวณจากน้ำหนักเข้า - น้ำหนักออก
  const weightIn = props.ticket.WE_WEIGHTIN || 0;
  const weightOut = props.ticket.WE_WEIGHTOUT || 0;
  const weightBeforeDeduction = weightIn - weightOut;
  
  if (weightBeforeDeduction > 0) {
    return weightBeforeDeduction.toLocaleString('en-US') + ' กก.';
  } else {
    return '-';
  }
}

function calculateNetWeight() {
  if (!props.ticket) return '-';
  
  // คำนวณน้ำหนักก่อนหัก
  const weightIn = props.ticket.WE_WEIGHTIN || 0;
  const weightOut = props.ticket.WE_WEIGHTOUT || 0;
  const weightBeforeDeduction = weightIn - weightOut;
  
  // คำนวณน้ำหนักสุทธิ
  const weightDeduction = props.ticket.WE_WEIGHTMINUS || 0;
  const netWeight = weightBeforeDeduction - weightDeduction;
  
  if (netWeight > 0) {
    return netWeight.toLocaleString('en-US') + ' กก.';
  } else {
    return '-';
  }
}

function displayNetWeight() {
  if (!props.ticket) return '-';
  
  // ถ้ามีข้อมูล WE_WEIGHTNET ในฐานข้อมูล ให้ใช้ข้อมูลนั้น
  if (props.ticket.WE_WEIGHTNET !== null && props.ticket.WE_WEIGHTNET !== undefined && props.ticket.WE_WEIGHTNET > 0) {
    return props.ticket.WE_WEIGHTNET.toLocaleString('en-US') + ' กก.';
  }
  
  // ถ้าไม่มี ให้คำนวณจากน้ำหนักก่อนหัก - น้ำหนักที่หัก
  return calculateNetWeight();
}
</script>

<template>
  <div v-if="visible" class="modal-overlay" @click.self="emit('close')">
    <div class="modal-content">
      <!-- ==================== HEADER ==================== -->
      <div class="modal-header">
        <h3>รายละเอียดบัตรชั่ง: {{ ticket?.WE_ID }}</h3>
        <button class="close-button" @click="emit('close')">&times;</button>
      </div>

      <!-- ==================== BODY ==================== -->
      <div class="modal-body" v-if="ticket">
        <!-- Part 1: Main Details -->
        <div class="detail-grid">
          <div>
            <strong>ทะเบียนรถ:</strong>
            <input v-if="isEditing" type="text" v-model="editableData.WE_LICENSE" class="edit-input">
            <span v-else>{{ ticket.WE_LICENSE }}</span>
          </div>
          <div>
            <strong>คนขับ:</strong>
            <input v-if="isEditing" type="text" v-model="editableData.WE_DRIVER" class="edit-input" placeholder="ชื่อคนขับ">
            <span v-else>{{ ticket.WE_DRIVER || 'ไม่ระบุ' }}</span>
          </div>
          <div>
            <strong>ประเภทรถ:</strong>
            <input v-if="isEditing" type="text" v-model="editableData.WE_TRUCK_CHAR" class="edit-input" placeholder="ประเภทรถ">
            <span v-else>{{ ticket.WE_TRUCK_CHAR || 'ไม่ระบุ' }}</span>
          </div>
          <div class="customer-info">
            <strong>ลูกค้า:</strong>
             <input v-if="isEditing" type="text" v-model="editableData.WE_VENDOR" class="edit-input">
            <span v-else>{{ ticket.WE_VENDOR_CD }} - {{ ticket.WE_VENDOR }}</span>
          </div>
          <div><strong>เวลาชั่งเข้า:</strong> {{ new Date(ticket.WE_TIMEIN).toLocaleString('th-TH') }}</div>
          <div><strong>เวลาชั่งออก:</strong> {{ ticket.WE_TIMEOUT ? new Date(ticket.WE_TIMEOUT).toLocaleString('th-TH') : '-' }}</div>
          <div>
            <strong>น้ำหนักก่อนหัก:</strong>
            <input v-if="isEditing" type="number" v-model.number="editableWeightBeforeDeduction" step="0.01" min="0" class="edit-input">
            <span v-else>{{ calculateWeightBeforeDeduction() }}</span>
            <small v-if="!isEditing" class="field-description">น้ำหนักสุทธิก่อนทำการหักน้ำหนัก (น้ำหนักเข้า - น้ำหนักออก)</small>
          </div>
          <div>
            <strong>น้ำหนักที่หัก:</strong>
            <input v-if="isEditing" type="number" v-model.number="editableWeightDeduction" step="0.01" min="0" class="edit-input">
            <span v-else>{{ ticket.WE_WEIGHTMINUS ? ticket.WE_WEIGHTMINUS.toLocaleString('en-US') + ' กก.' : '-' }}</span>
            <small v-if="!isEditing" class="field-description">น้ำหนักที่หักออกจากระบบ</small>
          </div>
          <div class="net-weight">
            <strong>น้ำหนักสุทธิ:</strong>
            <span>{{ displayNetWeight() }}</span>
            <small v-if="!isEditing" class="field-description">น้ำหนักสุทธิสุดท้าย (น้ำหนักก่อนหัก - น้ำหนักที่หัก)</small>
          </div>
          <div v-if="isEditing" class="net-weight">
            <strong>น้ำหนักสุทธิ (คำนวณ):</strong>
            <span>{{ ((editableWeightBeforeDeduction || 0) - (editableWeightDeduction || 0)).toLocaleString('en-US') }} กก.</span>
            <small class="field-description">น้ำหนักสุทธิที่คำนวณจากข้อมูลที่แก้ไข</small>
          </div>
        </div>
        
        <div v-if="ticket.WE_PARENT">
          <strong>บัตรชั่งก่อนหน้า:</strong>
          <a href="#" @click.prevent="emit('view-ticket', ticket.WE_PARENT)" class="ticket-link">
            {{ ticket.WE_PARENT }}
          </a>
        </div>

        <div v-if="ticket.WE_CONT">
          <strong>บัตรชั่งต่อเนื่อง:</strong>
          <a href="#" @click.prevent="emit('view-ticket', ticket.WE_CONT)" class="ticket-link">
            {{ ticket.WE_CONT }}
          </a>
        </div>
        <hr class="divider">

        <!-- Part 2: Items Area (โครงสร้างใหม่) -->

        <!-- ===== Header ของรายการสินค้า (รวมหัวข้อและช่องค้นหา) ===== -->
        <div class="items-header">
          <h4>รายการสินค้า</h4>
          <!-- ช่องค้นหาจะปรากฏที่นี่ (ด้านขวา) เฉพาะตอน Edit Mode -->
          <div v-if="isEditing" class="search-form-inline">
            <input type="text" v-model="planIdToSearch" placeholder="กรอกเลขที่เอกสารเพื่อค้นหา..." @keyup.enter="handleSearchPlan">
            <button type="button" @click="handleSearchPlan" :disabled="searchLoading" class="search-button">ค้นหา</button>
          </div>
        </div>

        <!-- ===== ส่วนแสดงผลการค้นหา (จะปรากฏใต้ Header เฉพาะตอน Edit Mode) ===== -->
        <div v-if="isEditing" class="search-results-area">
            <div v-if="searchError" class="search-error">{{ searchError }}</div>
            <div v-if="searchResults.length > 0" class="search-results-wrapper">
              <div class="search-results-container">
                <table>
                  <thead>
                    <tr>
                      <th><input type="checkbox" @change="toggleSelectAllResults($event)"></th>
                      <th>สินค้า</th>
                      <th>จำนวน</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="item in searchResults" :key="item.POSNR">
                      <td><input type="checkbox" v-model="item.selected"></td>
                      <td>{{ item.POSNR }} - {{ item.ARKTX }}</td>
                      <td>{{ item.LFIMG }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <button type="button" @click="addSelectedToNewItems" :disabled="!hasSelectedSearchResults" class="add-to-list-button">
                + เพิ่มรายการที่เลือก
              </button>
            </div>
        </div>

        <!-- ===== ตารางรายการสินค้า (เหมือนเดิม) ===== -->
        <div class="items-table-container">
          <table>
            <thead>
            <tr>
              <!-- กำหนดความกว้างให้พอดีกับข้อมูล -->
              <th style="width: 160px;">เอกสาร/ลำดับ</th> 
              
              <!-- ไม่ต้องกำหนดความกว้าง เพื่อให้ขยายเต็มที่ -->
              <th>สินค้า</th> 
              
              <!-- ลดขนาดลงให้พอดีกับหลักหมื่น -->
              <th style="width: 120px;">จำนวน</th> 
              
              <!-- กำหนดความกว้างให้พอดีกับหน่วยสั้นๆ -->
              <th style="width: 80px;">หน่วย</th> 
              
              <!-- ปุ่มลบ ขนาดเท่าเดิม -->
              <th v-if="isEditing" style="width: 50px;"></th> 
            </tr>
          </thead>
            <!-- โหมดแสดงผล (View Mode) -->
            <tbody v-if="!isEditing">
              <tr v-if="!ticket.items || ticket.items.length === 0">
                <td>{{ ticket.WE_DIREF }}</td>
                <td>{{ ticket.WE_MAT_CD }} - {{ ticket.WE_MAT }}</td>
                <td>{{ ticket.WE_QTY?.toLocaleString('en-US') }}</td>
                <td>{{ ticket.WE_UOM }}</td>
              </tr>
              <tr v-else v-for="item in ticket.items" :key="`${item.VBELN}-${item.POSNR}`">
                <td>{{ item.VBELN }}/{{ item.POSNR }}</td>
                <td>{{ item.WE_MAT_CD }} - {{ item.WE_MAT }}</td>
                <td>{{ item.WE_QTY?.toLocaleString('en-US') }}</td>
                <td>{{ item.WE_UOM }}</td>
              </tr>
            </tbody>
            <!-- โหมดแก้ไข (Edit Mode) -->
            <tbody v-else>
              <tr v-if="newItemsToReplace.length === 0">
                <td colspan="5" class="empty-list">
                  -- ยังไม่มีรายการ -- <br>
                  <small>(กรุณาค้นหาและเพิ่มรายการจากด้านบน)</small>
                </td>
              </tr>
              <tr v-else v-for="(item, index) in newItemsToReplace" :key="`${item.VBELN}-${item.POSNR}`">
                <td>{{ item.VBELN }}/{{ item.POSNR }}</td>
                <td>{{ item.MATNR }} - {{ item.ARKTX }}</td>
                <td>
                  <input type="number" v-model.number="item.editable_qty" class="qty-input">
                </td>
                <td>{{ item.VRKME }}</td>
                <td class="action-cell">
                  <button type="button" @click="removeFromNewItems(index)" class="remove-btn">&times;</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      
      <!-- Loading State -->
      <div v-else class="loading">กำลังโหลดข้อมูล...</div>

      <!-- ==================== FOOTER ==================== -->
      <div class="modal-footer" v-if="ticket">
        <!-- ... (ส่วน Footer เหมือนเดิม) ... -->
        <div class="edit-actions">
          <button v-if="!isEditing" @click="startEditing" class="edit-button">แก้ไขข้อมูล</button>
          <template v-else>
            <button @click="cancelEdit" class="cancel-edit-button">ยกเลิก</button>
            <button @click="handleSaveChanges" class="save-button">บันทึกการแก้ไข</button>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* =============================================== */
/* Modal Layout & Base                             */
/* =============================================== */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.6);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}
.modal-content {
  background-color: white;
  padding: 1.5rem;
  border-radius: 8px;
  width: 90%;
  max-width: 800px;
  box-shadow: 0 5px 15px rgba(0,0,0,0.3);
  max-height: 90vh;
  display: flex;
  flex-direction: column;
}
.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid #eee;
  padding-bottom: 1rem;
  margin-bottom: 1rem;
  flex-shrink: 0;
}
.modal-header h3 {
  margin: 0;
}
.close-button {
  background: none;
  border: none;
  font-size: 2rem;
  cursor: pointer;
  color: #888;
}
.modal-body {
  overflow-y: auto;
  flex-grow: 1;
}
.loading {
  text-align: center;
  padding: 3rem;
  color: #888;
}
.final-list-container .items-table-container {
  max-height: 250px;
  overflow-y: auto;
  border: 1px solid #ddd;
  border-radius: 4px;
}
.action-cell {
  text-align: center;
  width: 50px;
}
.qty-input {
  width: 100%; /* ให้ input เต็มความกว้างของ td */
  padding: 0.4rem;
  text-align: right;
  border: 1px solid #ccc;
  border-radius: 4px;
  box-sizing: border-box; /* สำคัญ */
}

/* =============================================== */
/* Modal Content Details                           */
/* =============================================== */
.detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 1rem;
  margin-bottom: 2rem;
}
.detail-grid div {
  background-color: #f9f9f9;
  padding: 0.8rem;
  border-radius: 4px;
}
.customer-info {
  grid-column: 1 / -1; 
  font-weight: bold;
}
.net-weight {
  font-size: 1.1rem;
  font-weight: bold;
  background-color: #eef7f3 !important;
  color: var(--primary-color);
  padding: 0.8rem;
  border-radius: 4px;
  border: 1px solid #c3e6c3;
}
.edit-input {
  width: 100%;
  padding: 0.5rem;
  font-size: 1rem;
  border: 1px solid #ccc;
  border-radius: 4px;
  box-sizing: border-box;
}

/* --- Items Table --- */
.items-table-container {
  max-height: 300px;
  overflow-y: auto;
  border: 1px solid #ddd;
  border-radius: 4px;
}
table {
  width: 100%;
  border-collapse: collapse;
}
th, td {
  padding: 0.8rem;
  text-align: left;
  border-bottom: 1px solid #eee;
}
th {
  background-color: #f9fafb;
  position: sticky;
  top: 0;
}

/* =============================================== */
/* Modal Footer & Buttons (แก้ไขทั้งหมดที่นี่)    */
/* =============================================== */
.modal-footer {
  border-top: 1px solid #eee;
  padding-top: 1rem;
  margin-top: 1rem;
  display: flex;
  align-items: center;
  flex-shrink: 0;
  gap: 0.5rem;
}

.edit-actions {
  display: flex;
  gap: 0.5rem;
  margin-left: auto; /* ดันกลุ่มปุ่มนี้ไปชิดขวาสุด */
}

/* Base style สำหรับปุ่มใน footer ทุกปุ่ม */
.modal-footer button {
  padding: 0.8rem 1.5rem;
  border: none;
  border-radius: 4px;
  font-size: 1rem;
  font-weight: bold;
  cursor: pointer;
  transition: background-color 0.2s;
  color: white; /* <-- กำหนดสีตัวอักษรเป็นขาวเป็นค่าเริ่มต้น */
}

/* สีพื้นหลังของแต่ละปุ่ม (ระบุให้ชัดเจน) */
.weigh-out-button { 
  background-color: var(--danger-color); 
}
.weigh-out-button:hover { 
  background-color: var(--danger-hover-color); 
}

.edit-button { 
  background-color: #ffc107; 
  color: black; /* <-- ปุ่มนี้ตัวอักษรสีดำ */
}

.edit-button { 
  background-color: #ffc107; 
  color: black; /* <-- ปุ่มนี้ตัวอักษรสีดำ */
}

.save-button { 
  background-color: #28a745; /* เขียวชัด */
}
.save-button:hover {
  background-color: #218838; /* เขียวเข้มเมื่อชี้ */
}

.cancel-edit-button { 
  background-color: #757575; 
}

.add-items-footer {
  padding: 1rem;
  background-color: #f9fafb;
  border-top: 1px solid #ddd;
}
.add-items-button {
  width: 100%;
  padding: 0.8rem;
  color: white;
  background-color: var(--primary-color);
  border: none;
  border-radius: 4px;
  font-size: 1rem;
  font-weight: bold;
  cursor: pointer;
  transition: background-color 0.2s;
}
.add-items-button:hover:not(:disabled) {
  background-color: #36a474;
}
.add-items-button:disabled {
  background-color: #ccc;
  cursor: not-allowed;
}
/* =============================================== */
/* Modal Shipment Plan Section                     */
/* =============================================== */
.shipment-plan-section {
  margin-top: 2rem;
  padding-top: 1.5rem;
  border-top: 2px solid #eee;
}
.shipment-plan-section h4 {
  margin-top: 0;
}
.search-form {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1rem;
}
.search-form input {
  flex-grow: 1;
  padding: 0.8rem; /* <-- ปรับขนาดให้เท่า input อื่นๆ */
  font-size: 1rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  box-sizing: border-box; /* <-- เพิ่ม box-sizing */
}

/* --- Style ของปุ่มค้นหา (แบบเดียวกับปุ่มชั่งออก) --- */
button.search-button {
  /* นำ Style พื้นฐานของปุ่มใหญ่มาใช้ */
  padding: 0.8rem 1.5rem;
  color: white;
  border: none;
  border-radius: 4px;
  font-size: 1rem;
  font-weight: bold;
  cursor: pointer;
  transition: background-color 0.2s;

  /* กำหนดสีพื้นหลัง */
  background-color: var(--primary-color, #42b883); 
}
button.search-button:hover:not(:disabled) {
  background-color: #36a474;
}
button.search-button:disabled {
  background-color: #218838;
  cursor: not-allowed;
}
/* ------------------------------------------- */

.search-error {
  color: var(--error-color);
  background-color: #ffcdd2;
  padding: 0.8rem;
  border-radius: 4px;
}
.search-results-container {
  max-height: 250px;
  overflow-y: auto;
  border: 1px solid #ddd;
  border-radius: 4px;
}
/* =============================================== */
/* Modal Edit Items Section                        */
/* =============================================== */
.edit-items-section {
  margin-top: 1.5rem;
  /* จัด Layout ด้วย CSS Grid */
  display: grid;
  grid-template-columns: 1fr 1fr; /* แบ่งเป็น 2 คอลัมน์เท่าๆ กัน */
  gap: 1.5rem;
  align-items: start; /* จัดให้ส่วนบนของแต่ละคอลัมน์ตรงกัน */
}
.edit-items-section .divider {
  grid-column: 1 / -1; /* ทำให้เส้นคั่นยาวเต็มความกว้าง */
  margin: 0;
}

.final-list-container, .add-items-container {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.final-list-container label, .add-items-container label {
  font-weight: bold;
  font-size: 1rem;
}

.empty-list {
  color: #888;
  font-style: italic;
  padding: 1rem;
  background-color: #f9f9f9;
  text-align: center;
  border-radius: 4px;
  border: 1px dashed #ddd;
}
.empty-list small {
  font-size: 0.8rem;
}

.final-list-container ul {
  list-style: none;
  padding: 0;
  margin: 0;
  max-height: 250px;
  overflow-y: auto;
  border: 1px solid #ddd;
  border-radius: 4px;
}
.final-list-container li {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.5rem 0.8rem;
  border-bottom: 1px solid #eee;
  font-size: 0.9rem;
}
.final-list-container li:last-child {
  border-bottom: none;
}
.remove-btn {
  background: none;
  border: none;
  color: var(--danger-color);
  font-size: 1.5rem;
  cursor: pointer;
  line-height: 1;
  padding: 0 0.5rem;
}

.search-form-inline {
  display: flex;
  gap: 0.5rem;
}
.search-form-inline input {
  flex-grow: 1;
  /* เพิ่ม Style พื้นฐานให้ครบ */
  padding: 0.8rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 1rem;
  box-sizing: border-box;
}
.search-form-inline button {
  flex-shrink: 0;
  /* เพิ่ม Style ของปุ่มให้ครบ */
  padding: 0.8rem 1rem;
  border: none;
  border-radius: 4px;
  background-color: var(--primary-color);
  color: white;
  cursor: pointer;
  transition: background-color 0.2s;
}
.search-form-inline button:disabled {
  background-color: #ccc;
  cursor: not-allowed;
}
.search-results-wrapper {
  border: 1px solid #ddd;
  border-radius: 4px;
  overflow: hidden; /* ซ่อนมุมของ table */
}
.search-results-container {
  max-height: 200px;
  overflow-y: auto;
}
.add-to-list-button {
  width: 100%;
  padding: 0.6rem;
  font-size: 0.9rem;
  background-color: var(--secondary-color);
  color: white;
  border: none;
  cursor: pointer;
  border-top: 1px solid #ddd;
}
.add-to-list-button:disabled {
  background-color: #ccc;
}

/* ทำให้ตารางผลการค้นหามี scroll ของตัวเองได้ */
.search-results-container {
  max-height: 250px;
  overflow-y: auto;
  margin-bottom: 1rem;
}

.items-header {
  display: flex;
  justify-content: space-between; /* ดัน H4 ไปซ้ายสุด และ search ไปขวาสุด */
  align-items: center;            /* จัดให้อยู่กึ่งกลางแนวตั้ง */
  margin-bottom: 0.75rem;         /* ระยะห่างก่อนถึงส่วนผลการค้นหา หรือตาราง */
}

.items-header h4 {
  margin: 0; /* ลบ margin เดิมของ h4 เพื่อให้ align-items ทำงานได้สวยงาม */
}

/* --- CSS สำหรับพื้นที่แสดงผลการค้นหา (ใหม่) --- */
.search-results-area {
    margin-bottom: 1.5rem; /* ระยะห่างก่อนถึงตารางหลัก */
}

/* ทำให้ placeholder ใน input ค้นหามีขนาดเล็กลงและสีจางลง */
.search-form-inline input::placeholder {
  font-size: 0.9em;
  color: #9ca3af;
}

/* จัดสไตล์ให้ wrapper ของผลการค้นหา */
.search-results-wrapper {
  margin-top: 0.75rem; /* ลดระยะห่างด้านบนลงเล็กน้อย */
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 1rem;
  background-color: #f9fafb;
}

/* ทำให้ placeholder ใน input ค้นหามีขนาดเล็กลงและสีจางลง */
.search-form-inline input::placeholder {
  font-size: 0.9em;
  color: #9ca3af;
}

/* จัดสไตล์ให้ wrapper ของผลการค้นหา */
.search-results-wrapper {
  margin-top: 1rem;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 1rem;
  background-color: #f9fafb;
}

/* ทำให้ตารางผลการค้นหามี scroll ของตัวเอง */
.search-results-container {
  max-height: 200px; /* ลดความสูงลงเล็กน้อย */
  overflow-y: auto;
  margin-bottom: 1rem;
}

/* ปรับปุ่ม 'เพิ่มรายการ' ให้ดูดีขึ้น */
.add-to-list-button {
  width: 100%;
  padding: 0.6rem;
  font-weight: 600;
  /* ... สามารถเพิ่มสไตล์อื่นๆ ได้ตามต้องการ ... */
}

.divider {
  border: 0;
  height: 1px;
  background-color: #e5e7eb;
  margin: 1.5rem 0;
}

.field-description {
  display: block;
  margin-top: 0.25rem;
  font-size: 0.8rem;
  color: #6c757d;
  font-style: italic;
}
</style>