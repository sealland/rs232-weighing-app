<!-- frontend/src/components/CreateTicketModal.vue -->
<script setup>
import { ref, watch, computed } from 'vue';

const props = defineProps({
  visible: { type: Boolean, default: false },
  initialWeightIn: { type: Number, default: 0 },
  carQueue: { type: Array, default: () => [] }
});
const emit = defineEmits(['close', 'save']);

// --- State Management ---
const selectedQueueSeq = ref('');
const weighingType = ref('combined');
const planIdToSearch = ref('');
const searchResults = ref([]);
const selectedCombinedItems = ref([]);
const finalCombinedItems = ref([]); // "ตะกร้า"
const selectedSeparateItem = ref(null);
const searchLoading = ref(false);
const searchError = ref(null);

const selectedQueueObject = computed(() => {
  if (!selectedQueueSeq.value) return null;
  return props.carQueue.find(q => q.SEQ === selectedQueueSeq.value);
});

watch(() => props.visible, (isVisible) => {
  if (isVisible) {
    selectedQueueSeq.value = '';
    weighingType.value = 'combined';
    planIdToSearch.value = '';
    searchResults.value = [];
    selectedCombinedItems.value = [];
    finalCombinedItems.value = [];
    selectedSeparateItem.value = null;
    searchError.value = null;
  }
});

watch(weighingType, () => {
  planIdToSearch.value = '';
  searchResults.value = [];
  selectedSeparateItem.value = null;
  selectedCombinedItems.value = [];
  searchError.value = null;
});

async function handleSearchPlan() {
  if (!planIdToSearch.value.trim()) return;
  searchLoading.value = true;
  searchError.value = null;
  searchResults.value = [];
  const API_BASE_URL = 'http://localhost:8000';
  try {
    const response = await fetch(`${API_BASE_URL}/api/shipment-plans/${planIdToSearch.value.trim()}`);
    if (!response.ok) throw new Error('ไม่พบข้อมูลแผนการจัดส่ง');
    const data = await response.json();
    if (data.length === 0) {
      searchError.value = `ไม่พบข้อมูลสำหรับเลขที่เอกสาร: ${planIdToSearch.value}`;
    } else {
      searchResults.value = data.map(item => ({
        ...item,
        editable_qty: item.LFIMG // <-- ใช้ LFIMG
      }));
    }
  } catch (error) {
    searchError.value = error.message;
  } finally {
    searchLoading.value = false;
  }
}

function addSelectedToFinalList() {
  for (const item of selectedCombinedItems.value) {
    if (!finalCombinedItems.value.some(finalItem => finalItem.VBELN === item.VBELN && finalItem.POSNR === item.POSNR)) {
      // ตอนเพิ่มลงตะกร้า ให้เอา editable_qty ติดไปด้วย
      finalCombinedItems.value.push(item); 
    }
  }
  searchResults.value = [];
  selectedCombinedItems.value = [];
  planIdToSearch.value = '';
}

function removeFromFinalList(itemToRemove) {
  finalCombinedItems.value = finalCombinedItems.value.filter(item =>
    !(item.VBELN === itemToRemove.VBELN && item.POSNR === itemToRemove.POSNR)
  );
}

function handleSave() {
  if (!selectedQueueObject.value) {
    alert('กรุณาเลือกคิวรถ');
    return;
  }
  
  let dataToSave = {
    WE_LICENSE: selectedQueueObject.value.CARLICENSE,
    WE_VENDOR: selectedQueueObject.value.AR_NAME,
    WE_VENDOR_CD: selectedQueueObject.value.KUNNR,
    WE_WEIGHTIN: props.initialWeightIn,
  };

  if (weighingType.value === 'separate' && selectedSeparateItem.value) {
    dataToSave.WE_DIREF = selectedSeparateItem.value.VBELN;
    dataToSave.WE_MAT_CD = selectedSeparateItem.value.MATNR;
    dataToSave.WE_MAT = selectedSeparateItem.value.ARKTX;
  } else if (weighingType.value === 'combined' && finalCombinedItems.value.length > 0) {
    dataToSave.items = finalCombinedItems.value.map(item => ({
      VBELN: item.VBELN,
      POSNR: item.POSNR,
      WE_MAT_CD: item.MATNR,
      WE_MAT: item.ARKTX,
      WE_QTY: item.editable_qty, // <-- ใช้จำนวนที่แก้ไขได้
      WE_UOM: item.VRKME
    }));
  }
  
  emit('save', dataToSave);
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
        <!-- Part 1: Car Queue Selection -->
        <div class="form-group">
          <label for="car-queue-select">เลือกเลขที่คิว</label>
          <select id="car-queue-select" v-model="selectedQueueSeq" required>
            <option disabled value="">-- กรุณาเลือกคิวรถ --</option>
            <option v-for="queue in carQueue" :key="queue.SEQ" :value="queue.SEQ">
              คิว {{ queue.SEQ }} - {{ queue.CARLICENSE }} ({{ queue.AR_NAME }})
            </option>
          </select>
        </div>
        <div v-if="selectedQueueObject" class="auto-filled-data">
          <div class="data-display"><strong>ทะเบียน:</strong> {{ selectedQueueObject.CARLICENSE }}</div>
          <div class="data-display"><strong>ลูกค้า:</strong> {{ selectedQueueObject.AR_NAME }}</div>
        </div>
        
        <hr class="divider">

        <!-- Part 2: Weighing Type Selection -->
        <div class="form-group weighing-type-selector">
          <label>ประเภทการชั่ง</label>
          <div>
            <label><input type="radio" value="combined" v-model="weighingType"> ชั่งรวม</label>
            <label><input type="radio" value="separate" v-model="weighingType"> ชั่งแยก</label>
          </div>
        </div>

        <!-- Part 3: Dynamic Forms -->
        <!-- Form for SEPARATE weighing -->
        <div v-if="weighingType === 'separate'" class="shipment-plan-section">
          <div class="form-group">
            <label>กรณีชั่งแยก (ค้นหาเลขที่เอกสาร)</label>
            <div class="search-form-inline">
              <input type="text" v-model="planIdToSearch" placeholder="กรอกเลขที่เอกสาร..." @keyup.enter="handleSearchPlan" maxlength="10">
              <button type="button" @click="handleSearchPlan" :disabled="searchLoading" class="search-button">{{ searchLoading ? '...' : 'ค้นหา' }}</button>
            </div>
          </div>
          <div v-if="searchError" class="search-error">{{ searchError }}</div>
          <div v-if="searchResults.length > 0" class="form-group mt-1">
            <label for="item-select">เลือกรายการสินค้า</label>
            <select id="item-select" v-model="selectedSeparateItem">
              <option :value="null" disabled>-- กรุณาเลือกรายการ --</option>
              <option v-for="item in searchResults" :key="item.POSNR" :value="item">{{ item.POSNR }} - {{ item.ARKTX }}</option>
            </select>
          </div>
        </div>

        <!-- Form for COMBINED weighing -->
        <div v-if="weighingType === 'combined'" class="shipment-plan-section">
          <div class="form-group">
            <label>กรณีชั่งรวม (ค้นหาและเพิ่มได้หลายเอกสาร)</label>
            <div class="search-form-inline">
              <input type="text" v-model="planIdToSearch" placeholder="กรอกเลขที่เอกสาร..." @keyup.enter="handleSearchPlan" maxlength="10">
              <button type="button" @click="handleSearchPlan" :disabled="searchLoading" class="search-button">{{ searchLoading ? '...' : 'ค้นหา' }}</button>
            </div>
          </div>
          <div v-if="searchError" class="search-error">{{ searchError }}</div>
          
          <div v-if="searchResults.length > 0">
            <div class="search-results-container">
              <table>
                <thead>
                  <tr>
                    <th><input type="checkbox" disabled></th>
                    <th>สินค้า</th>
                    <th style="width: 100px;">จำนวน</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in searchResults" :key="item.POSNR">
                    <td><input type="checkbox" :value="item" v-model="selectedCombinedItems"></td>
                    <td>{{ item.POSNR }} - {{ item.ARKTX }}</td>
                    <td>
                      <input type="number" v-model="item.editable_qty" class="qty-input">
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <button type="button" @click="addSelectedToFinalList" :disabled="selectedCombinedItems.length === 0" class="add-to-list-button">
              + เพิ่มรายการที่เลือกลงตะกร้า
            </button>
          </div>

          <div class="final-list-container">
            <label>รายการทั้งหมดที่จะบันทึก ({{ finalCombinedItems.length }} รายการ)</label>
            <div v-if="finalCombinedItems.length === 0" class="empty-list">-- ยังไม่มีรายการ --</div>
            <ul v-else>
              <li v-for="item in finalCombinedItems" :key="`${item.VBELN}-${item.POSNR}`">
                <span>{{ item.VBELN }}/{{ item.POSNR }} - {{ item.ARKTX }}</span>
                <strong class="item-qty">{{ item.editable_qty?.toLocaleString('en-US') }} {{ item.VRKME }}</strong>
                <button type="button" @click="removeFromFinalList(item)" class="remove-btn">&times;</button>
              </li>
            </ul>
          </div>
        </div>

        <hr class="divider">

        <!-- Part 4: Weight and Actions -->
        <div class="form-group">
          <label>น้ำหนักชั่งเข้า</label>
          <div class="weight-preview">{{ initialWeightIn.toLocaleString('en-US') }} กก.</div>
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
</style>