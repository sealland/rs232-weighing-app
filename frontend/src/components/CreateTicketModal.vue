// frontend/src/components/CreateTicketModal.vue
<script setup>
import { ref, watch, computed } from 'vue';

// --- Props & Emits ---
const props = defineProps({
  visible: { type: Boolean, default: false },
  initialWeightIn: { type: Number, default: 0 },
  carQueue: { type: Array, default: () => [] },
  continuousDataFromPrevTicket: { type: Object, default: null } 
});
const emit = defineEmits(['close', 'save']);

// --- State Management (Refactored for Simplicity) ---
const selectedQueueSeq = ref('');
const autoFilledData = ref(null);
const finalWeightIn = ref(0);

// State for Searching
const planIdToSearch = ref('');
const searchLoading = ref(false);
const searchError = ref(null);
const searchResults = ref([]); // Stores items from API with 'selected' property

// State for the "Shopping Cart"
const finalCombinedItems = ref([]); // The one and only list for items to be saved

// State for Car Queue
const carQueueData = ref([]);
const carQueueLoading = ref(false);
const carQueueError = ref(null);

// --- Functions for Car Queue Management ---
async function fetchCarQueue() {
  carQueueLoading.value = true;
  carQueueError.value = null;
  const API_BASE_URL = 'http://192.168.132.7:8000';

  try {
    const response = await fetch(`${API_BASE_URL}/api/car-queue/`);
    
    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`ไม่สามารถดึงข้อมูลคิวรถได้ (${response.status}): ${errorText}`);
    }
    
    const data = await response.json();
    carQueueData.value = data;
    
  } catch (error) {
    if (error.message.includes('Failed to fetch')) {
      carQueueError.value = "ไม่สามารถเชื่อมต่อกับเซิร์ฟเวอร์ได้ กรุณาตรวจสอบว่า Backend กำลังรันอยู่";
    } else {
      carQueueError.value = error.message;
    }
    console.error("Error fetching car queue:", error);
    carQueueData.value = [];
  } finally {
    carQueueLoading.value = false;
  }
}

// --- Computed Properties ---
// แก้ไข selectedQueueObject ให้ใช้ carQueueData แทน props.carQueue
const selectedQueueObject = computed(() => {
  if (!selectedQueueSeq.value) return null;
  // ใช้ carQueueData ถ้ามี ไม่งั้นใช้ props.carQueue
  const queueData = carQueueData.value.length > 0 ? carQueueData.value : props.carQueue;
  return queueData.find(q => q.SEQ === selectedQueueSeq.value);
});

// *** NEW & IMPORTANT *** This computed property enables/disables the 'Add to Cart' button
const hasSelectedSearchResults = computed(() => {
  // Checks if there is AT LEAST ONE item in searchResults where 'selected' is true
  return searchResults.value.some(item => item.selected);
});


// --- Watchers ---
// Watcher to reset the modal state when it becomes visible
watch(() => props.visible, async (isVisible) => {
  if (!isVisible) return;
  
  console.log('Modal opened with initialWeightIn:', props.initialWeightIn);
  
  // Reset state
  autoFilledData.value = {
    CARLICENSE: '',
    AR_NAME: '',
    KUNNR: '',
    INITIAL_WEIGHT_IN: null,
    PARENT_ID: '',
    WE_SEQ: ''
  };
  
  selectedQueueSeq.value = '';
  // แก้ไขตรงนี้ - ใช้ค่าจาก props.initialWeightIn
  finalWeightIn.value = props.initialWeightIn || 0;
  console.log('finalWeightIn set to:', finalWeightIn.value);
  finalCombinedItems.value = [];
  
  // Fetch car queue data
  await fetchCarQueue();
  
  // Handle continuous weighing data
  if (props.continuousDataFromPrevTicket) {
    autoFilledData.value = {
      CARLICENSE: props.continuousDataFromPrevTicket.CARLICENSE || '',
      AR_NAME: props.continuousDataFromPrevTicket.AR_NAME || '',
      KUNNR: props.continuousDataFromPrevTicket.KUNNR || '',
      INITIAL_WEIGHT_IN: props.continuousDataFromPrevTicket.INITIAL_WEIGHT_IN || null,
      PARENT_ID: props.continuousDataFromPrevTicket.PARENT_ID || '',
      WE_SEQ: props.continuousDataFromPrevTicket.WE_SEQ || ''
    };
    
    // Set initial value for queue dropdown
    selectedQueueSeq.value = props.continuousDataFromPrevTicket.WE_SEQ || '';
    
    // ตั้งค่าน้ำหนักจาก continuous weighing data
    if (props.continuousDataFromPrevTicket.INITIAL_WEIGHT_IN) {
      finalWeightIn.value = props.continuousDataFromPrevTicket.INITIAL_WEIGHT_IN;
    }
  }
});

// เพิ่ม watcher ใหม่สำหรับ initialWeightIn
watch(() => props.initialWeightIn, (newWeight) => {
  if (newWeight && newWeight > 0) {
    finalWeightIn.value = newWeight;
  }
}, { immediate: true });


// --- Functions for Item Management ---

async function handleSearchPlan() {
  if (!planIdToSearch.value.trim()) return;
  searchLoading.value = true;
  searchError.value = null;
  searchResults.value = [];
  const API_BASE_URL = 'http://192.168.132.7:8000';

  try {
    const response = await fetch(`${API_BASE_URL}/api/shipment-plans/${planIdToSearch.value.trim()}`);
    if (!response.ok) throw new Error('ไม่พบข้อมูลแผนการจัดส่ง');
    
    const data = await response.json();
    if (data.length === 0) {
      searchError.value = `ไม่พบข้อมูลสำหรับเลขที่เอกสาร: ${planIdToSearch.value}`;
    } else {
      // Correctly prepares data for v-model by adding 'selected' and 'editable_qty'
      searchResults.value = data.map(item => ({ 
        ...item, 
        selected: false,
        editable_qty: item.LFIMG
      }));
    }
  } catch (error) {
    searchError.value = error.message;
  } finally {
    searchLoading.value = false;
  }
}

// *** NEW *** Function for the "Select All" checkbox
function toggleSelectAllResults(event) {
  const isChecked = event.target.checked;
  searchResults.value.forEach(item => item.selected = isChecked);
}

function addSelectedToCart() {
  const selectedItems = searchResults.value.filter(item => item.selected);

  for (const item of selectedItems) {
    const isDuplicate = finalCombinedItems.value.some(
      cartItem => cartItem.VBELN === item.VBELN && cartItem.POSNR === item.POSNR
    );
    if (!isDuplicate) {
      finalCombinedItems.value.push(item);
    }
  }

  // --- จุดแก้ไข ---
  // แทนที่จะล้างทั้งหมด เราจะกรองรายการที่ถูกเลือกแล้วออกไป
  searchResults.value = searchResults.value.filter(item => !item.selected);

  // ถ้าไม่มีรายการเหลือในผลการค้นหาแล้ว ก็ให้ล้าง planIdToSearch ไปเลย
  if (searchResults.value.length === 0) {
      planIdToSearch.value = '';
  }
}

// *** NEW *** Function to remove an item from the cart by its index
function removeFromCart(index) {
  finalCombinedItems.value.splice(index, 1);
}


// --- Main Save Function ---
async function handleSave() {
  try {
    console.log('=== Starting handleSave ===');
    
    // ตรวจสอบข้อมูลที่จำเป็น
    if (!selectedQueueSeq.value) {
      alert('กรุณาเลือกคิวรถ');
      return;
    }
    
    if (!finalWeightIn.value || finalWeightIn.value <= 0) {
      alert('กรุณาตรวจสอบน้ำหนักชั่งเข้า');
      return;
    }
    
    console.log('Selected queue seq:', selectedQueueSeq.value);
    console.log('Final weight in:', finalWeightIn.value);
    
    // หาข้อมูลคิวรถที่เลือก
    const selectedQueueObject = carQueueData.value.find(q => q.SEQ === selectedQueueSeq.value);
    
    if (!selectedQueueObject) {
      alert('ไม่พบข้อมูลคิวรถที่เลือก');
      return;
    }
    
    console.log('Selected queue object:', selectedQueueObject);
    
    // ใช้ข้อมูลจากคิวรถที่เลือก หรือจาก continuous weighing data
    const sourceData = props.continuousDataFromPrevTicket || {
      CARLICENSE: selectedQueueObject.CARLICENSE,
      AR_NAME: selectedQueueObject.AR_NAME,
      KUNNR: selectedQueueObject.KUNNR || '',
      PARENT_ID: null,
      WE_SEQ: selectedQueueObject.SEQ
    };
    
    console.log('Source data:', sourceData);
    
    const ticketData = {
      WE_LICENSE: sourceData.CARLICENSE,
      WE_WEIGHTIN: parseFloat(finalWeightIn.value), // แปลงเป็น float
      WE_VENDOR: sourceData.AR_NAME,
      WE_VENDOR_CD: sourceData.KUNNR,
      WE_SEQ: selectedQueueObject.SEQ,
      parent_id: sourceData.PARENT_ID || null,
      // ส่งรายการสินค้าเป็น undefined ถ้าไม่มี (ไม่บังคับ)
      items: finalCombinedItems.value.length > 0 ? finalCombinedItems.value.map(item => ({
        VBELN: item.VBELN,
        POSNR: item.POSNR,
        WE_MAT_CD: item.WE_MAT_CD || null,
        WE_MAT: item.WE_MAT || null,
        WE_QTY: parseFloat(item.WE_QTY) || null,
        WE_UOM: item.WE_UOM || null
      })) : undefined
    };
    
    console.log('Sending ticket data:', JSON.stringify(ticketData, null, 2));
    
    const response = await fetch('http://192.168.132.7:8000/api/tickets/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(ticketData)
    });
    
    console.log('Response status:', response.status);
    console.log('Response ok:', response.ok);
    
    if (!response.ok) {
      const errorText = await response.text();
      console.error('Error response:', errorText);
      throw new Error(`เกิดข้อผิดพลาดในการสร้างบัตรชั่ง: ${errorText}`);
    }
    
    const newTicket = await response.json();
    console.log('New ticket created:', newTicket);
    
    alert('บันทึกบัตรชั่งใหม่สำเร็จ!');
    emit('ticket-created', newTicket);
    emit('close');
    
  } catch (error) {
    console.error('Error creating ticket:', error);
    alert(`เกิดข้อผิดพลาด: ${error.message}`);
  }
}

</script>
<template>
  <div v-if="visible" class="modal-overlay" @click.self="emit('close')">
    <div class="modal-content">
      <div class="modal-header">
        <h3>สร้างบัตรชั่งใหม่</h3>
        <button class="close-button" @click="emit('close')">&times;</button>
      </div>

      <form @submit.prevent="handleSave" class="modal-body">
        <!-- Part 1: Car Queue -->
        <div class="form-group">
          <label for="car-queue-select">เลือกเลขที่คิว</label>
          <select id="car-queue-select" v-model="selectedQueueSeq" required>
            <option disabled value="">-- กรุณาเลือกคิวรถ --</option>
            <option v-for="queue in carQueueData" :key="queue.SEQ" :value="queue.SEQ">
              คิว {{ queue.SEQ }} - {{ queue.CARLICENSE }} ({{ queue.AR_NAME }})
            </option>
          </select>
          <div v-if="carQueueLoading" class="loading-message">กำลังโหลดข้อมูลคิวรถ...</div>
          <div v-if="carQueueError" class="error-message">เกิดข้อผิดพลาด: {{ carQueueError }}</div>
        </div>

        <!-- แสดงข้อมูลรถ -->
        <div v-if="selectedQueueObject || autoFilledData" class="auto-filled-data">
          <div class="data-display"><strong>ทะเบียน:</strong> {{ (selectedQueueObject || autoFilledData)?.CARLICENSE }}</div>
          <div class="data-display"><strong>ลูกค้า:</strong> {{ (selectedQueueObject || autoFilledData)?.AR_NAME }}</div>
        </div>

        <hr class="divider">

        <!-- ==================================================================== -->
        <!-- Part 2: UI สำหรับค้นหาและจัดการรายการสินค้า (ชุดใหม่ทั้งหมด) -->
        <!-- ==================================================================== -->
        <div class="shipment-plan-section">

          <!-- ส่วนควบคุมการค้นหา -->
          <div class="form-group">
            <label>ค้นหาและเพิ่มรายการจากเอกสาร (ไม่บังคับ)</label>
            <div class="search-form-inline">
              <input type="text" v-model="planIdToSearch" placeholder="กรอกเลขที่เอกสาร..." @keyup.enter="handleSearchPlan" maxlength="10">
              <button type="button" @click="handleSearchPlan" :disabled="searchLoading" class="search-button">{{ searchLoading ? '...' : 'ค้นหา' }}</button>
            </div>
          </div>
          <div v-if="searchError" class="search-error">{{ searchError }}</div>

          <!-- ส่วนแสดงผลการค้นหา (ถ้ามี) -->
          <div v-if="searchResults.length > 0" class="search-results-wrapper mt-2">
            <div class="search-results-container">
              <table>
                <thead>
                  <tr>
                    <th><input type="checkbox" @change="toggleSelectAllResults($event)"></th>
                    <th>สินค้า</th>
                    <th>จำนวนตั้งต้น</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in searchResults" :key="item.POSNR">
                    <td><input type="checkbox" v-model="item.selected"></td>
                    <td>{{ item.POSNR }} - {{ item.ARKTX }}</td>
                    <td>{{ item.LFIMG?.toLocaleString('en-US') }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <button type="button" @click="addSelectedToCart" :disabled="!hasSelectedSearchResults" class="add-to-list-button">
              + เพิ่มรายการที่เลือกลงตะกร้า
            </button>
          </div>

          <hr class="divider">

          <!-- ส่วนตะกร้าสินค้า (Final List) -->
          <div class="final-list-container">
            <label>รายการสินค้าในบัตรชั่ง (ไม่บังคับ)</label>
            <div v-if="finalCombinedItems.length === 0" class="empty-list">
              -- ยังไม่มีรายการ -- <br>
              <small>(หากไม่เพิ่มรายการ จะเป็นการสร้างบัตรชั่งแบบ 'รอลงรายการ')</small>
            </div>
            <div v-else class="items-table-container">
              <table>
                <thead>
                  <tr>
                    <th>สินค้า</th>
                    <th style="width: 120px;">จำนวน</th>
                    <th>หน่วย</th>
                    <th style="width: 50px;"></th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(item, index) in finalCombinedItems" :key="`${item.VBELN}-${item.POSNR}`">
                    <td>{{ item.ARKTX }}</td>
                    <td>
                      <input 
                        type="number" 
                        v-model.number="item.editable_qty"
                        class="qty-input"
                        min="0"
                      >
                    </td>
                    <td>{{ item.VRKME }}</td>
                    <td class="action-cell">
                      <button type="button" @click="removeFromCart(index)" class="remove-btn">&times;</button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <hr class="divider">

        <!-- Part 3: Weight and Actions (คงเดิม) -->
        <div class="form-group">
          <label>น้ำหนักชั่งเข้า</label>
          <div class="weight-preview">{{ (finalWeightIn || 0).toLocaleString('en-US') }} กก.</div>
        </div>
        <div class="modal-footer">
          <button type="button" @click="emit('close')" class="cancel-button">ยกเลิก</button>
          <button type="submit" class="save-button">บันทึกการสร้างบัตร</button>
        </div>
      </form>
    </div>
  </div>
</template>
<style scoped>
/* Base Modal Styles */
.modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background-color: rgba(0, 0, 0, 0.6); display: flex; justify-content: center; align-items: center; z-index: 1000; }
.modal-content { background-color: white; padding: 1.5rem; border-radius: 8px; width: 90%; max-width: 600px; box-shadow: 0 5px 15px rgba(0,0,0,0.3); max-height: 90vh; display: flex; flex-direction: column; }
.modal-header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #eee; padding-bottom: 1rem; margin-bottom: 1rem; }
.modal-header h3 { margin: 0; }
.close-button { background: none; border: none; font-size: 2rem; cursor: pointer; color: #888; }
.modal-body { overflow-y: auto; }
.modal-footer { margin-top: 1.5rem; display: flex; gap: 0.5rem; justify-content: flex-end; }
.modal-footer button { padding: 0.8rem 1.5rem; border: none; border-radius: 4px; font-size: 1rem; font-weight: bold; cursor: pointer; }
.cancel-button { background-color: #757575; color: white; }
.save-button { background-color: var(--primary-color); color: white; }
.divider { border: none; border-top: 1px solid #eee; margin: 1.5rem 0; }
.form-group { margin-bottom: 1.2rem; }
.form-group label { display: block; font-weight: bold; margin-bottom: 0.5rem; }
.form-group input[type="text"], .form-group select { width: 100%; padding: 0.8rem; border: 1px solid #ddd; border-radius: 4px; font-size: 1rem; box-sizing: border-box; background-color: white; }
.auto-filled-data { display: flex; gap: 1rem; margin-top: 1rem; }
.data-display { flex: 1; padding: 0.8rem; background-color: #f0f2f5; border-radius: 4px; font-weight: bold; }
.weight-preview { font-size: 1.5rem; font-weight: bold; color: var(--primary-color); background-color: #f0f2f5; padding: 0.8rem; border-radius: 4px; text-align: right; }
.weighing-type-selector div { display: flex; gap: 1.5rem; }
.weighing-type-selector label { display: flex; align-items: center; gap: 0.5rem; font-weight: normal; }
.shipment-plan-section .search-form-inline { display: flex; align-items: center; gap: 0.5rem; }
.shipment-plan-section .search-form-inline input { flex-grow: 1; }
.shipment-plan-section .search-form-inline button { flex-shrink: 0; padding: 0.8rem 1rem; color: white; background-color: var(--primary-color); border:none; border-radius: 4px; cursor: pointer; }
.shipment-plan-section .search-form-inline button:disabled { background-color: #ccc; }
.search-error { margin-top: 0.5rem; color: var(--error-color); font-size: 0.9rem; }
.mt-1 { margin-top: 1rem; }
.search-results-container { max-height: 200px; overflow-y: auto; border: 1px solid #ddd; border-radius: 4px; margin-top: 1rem; }
.search-results-container table { width: 100%; }
.search-results-container th, .search-results-container td { padding: 0.5rem; font-size: 0.9rem; border-bottom: 1px solid #eee; text-align: left; vertical-align: middle; }
.add-to-list-button { margin-top: 0.5rem; width: 100%; padding: 0.6rem; font-size: 0.9rem; background-color: var(--secondary-color); color: white; border: none; border-radius: 4px; cursor: pointer; }
.add-to-list-button:disabled { background-color: #ccc; }
.final-list-container { margin-top: 1rem; }
.final-list-container label { font-weight: bold; }
.final-list-container .empty-list { color: #888; font-style: italic; padding: 1rem; background-color: #f9f9f9; text-align: center; border-radius: 4px; margin-top: 0.5rem; }
.final-list-container ul { list-style: none; padding: 0; margin-top: 0.5rem; max-height: 150px; overflow-y: auto; border: 1px solid #ddd; border-radius: 4px; }
.final-list-container li { display: flex; justify-content: space-between; align-items: center; padding: 0.5rem; border-bottom: 1px solid #eee; font-size: 0.9rem;gap: 0.5rem; }
.final-list-container li:last-child { border-bottom: none; }
.remove-btn { background: none; border: none; color: var(--danger-color); font-size: 1.5rem; cursor: pointer; line-height: 1; }
.qty-input {
  width: 80px; /* จำกัดความกว้าง */
  padding: 0.4rem;
  text-align: right;
  border: 1px solid #ccc;
  border-radius: 4px;
}
.final-list-container li span {
  flex-grow: 1; /* ให้ชื่อสินค้ายืด */
}
.item-qty {
  flex-shrink: 0; /* ไม่ให้จำนวนหด */
  margin-left: auto; /* ดันไปทางขวา */
}

/* --- เพิ่ม CSS สำหรับการแสดงเลขคิวที่คัดลอก --- */
.copied-queue-display {
  margin-top: 0.5rem;
}

.copied-queue-info {
  padding: 0.8rem;
  background-color: #e3f2fd;
  border: 1px solid #2196f3;
  border-radius: 4px;
  color: #1976d2;
  font-weight: bold;
}

.copied-queue-info small {
  display: block;
  margin-top: 0.2rem;
  font-weight: normal;
  color: #666;
}

/* เพิ่มในส่วน <style> */
.loading-message {
  color: #666;
  font-style: italic;
  margin-top: 0.5rem;
}

.error-message {
  color: #dc3545;
  font-weight: bold;
  margin-top: 0.5rem;
}
</style>