<script setup>
import { ref, watch, computed } from 'vue';

// --- Props & Emits ---
const props = defineProps({
  visible: { type: Boolean, default: false },
  initialWeightIn: { type: Number, default: 0 },
  carQueue: { type: Array, default: () => [] } // รับ Array ของคิวรถ
});
const emit = defineEmits(['close', 'save']);

// --- State for the form ---
const selectedQueueSeq = ref(''); // เก็บ SEQ ของคิวที่ถูกเลือก

// --- State ใหม่สำหรับ "ชั่งแยก" ---
const separateWeighingPlanId = ref(''); // VBELN ที่จะค้นหา
const separateWeighingItems = ref([]); // รายการสินค้าที่ค้นหาเจอ
const searchLoading = ref(false);
const searchError = ref(null);
// ------------------------------------

// --- Computed Property ---
// หา object ของคิวที่ถูกเลือกจาก SEQ
const selectedQueueObject = computed(() => {
  if (!selectedQueueSeq.value) return null;
  return props.carQueue.find(q => q.SEQ === selectedQueueSeq.value);
});



// --- Watcher to reset form when modal opens ---
watch(() => props.visible, (isVisible) => {
  if (isVisible) {
    selectedQueueSeq.value = ''; // Reset dropdown
  }
});

// --- Function to handle form submission ---
function handleSave() {
  if (!selectedQueueObject.value) {
    alert('กรุณาเลือกคิวรถ');
    return;
  }
  const dataToSave = {
    WE_LICENSE: selectedQueueObject.value.CARLICENSE,
    WE_VENDOR: selectedQueueObject.value.AR_NAME,
    WE_VENDOR_CD: selectedQueueObject.value.KUNNR, // <-- ส่ง KUNNR เป็น WE_VENDOR_CD
    WE_WEIGHTIN: props.initialWeightIn,
    // Field อื่นๆ จะเป็น null โดยอัตโนมัติ
  };
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
        <!-- ส่วนที่ 1: เลือกจากคิวรถ -->
        <div class="form-group">
          <label for="car-queue-select">เลือกเลขที่คิว</label>
          <select id="car-queue-select" v-model="selectedQueueSeq" required>
            <option disabled value="">-- กรุณาเลือกคิวรถ --</option>
            <option v-for="queue in carQueue" :key="queue.SEQ" :value="queue.SEQ">
              คิว {{ queue.SEQ }} - {{ queue.CARLICENSE }} ({{ queue.AR_NAME }})
            </option>
          </select>
        </div>

        <!-- แสดงข้อมูลที่ดึงมาอัตโนมัติ -->
        <div v-if="selectedQueueObject" class="auto-filled-data">
          <div class="form-group">
            <label>ทะเบียนรถ</label>
            <div class="data-display">{{ selectedQueueObject.CARLICENSE }}</div>
          </div>
          <div class="form-group">
            <label>ชื่อลูกค้า</label>
            <div class="data-display">{{ selectedQueueObject.AR_NAME }}</div>
          </div>
        </div>
        
        <hr class="divider">

        <!-- ส่วนที่ 2: กรณีชั่งแยก (จะทำในขั้นถัดไป) -->
        <div class="form-group">
            <label>ชื่อสินค้า (กรณีชั่งแยก)</label>
            <input type="text" placeholder="(จะพัฒนาในขั้นต่อไป)">
        </div>

        <div class="form-group">
          <label>น้ำหนักชั่งเข้า</label>
          <div class="weight-preview">{{ initialWeightIn.toLocaleString('en-US') }} กก.</div>
        </div>

        <div class="modal-footer">
          <button type="button" @click="emit('close')" class="cancel-button">ยกเลิก</button>
          <button type="submit" class="save-button">บันทึก</button>
        </div>
      </form>
    </div>
  </div>
</template>

<style scoped>
/* Base Modal Styles (can be shared with TicketDetailModal) */
.modal-overlay {
  position: fixed; top: 0; left: 0; right: 0; bottom: 0;
  background-color: rgba(0, 0, 0, 0.6);
  display: flex; justify-content: center; align-items: center; z-index: 1000;
}
.modal-content {
  background-color: white; padding: 1.5rem; border-radius: 8px;
  width: 90%; max-width: 500px; box-shadow: 0 5px 15px rgba(0,0,0,0.3);
}
.modal-header {
  display: flex; justify-content: space-between; align-items: center;
  border-bottom: 1px solid #eee; padding-bottom: 1rem; margin-bottom: 1.5rem;
}
.modal-header h3 { margin: 0; }
.close-button {
  background: none; border: none; font-size: 2rem;
  cursor: pointer; color: #888;
}

/* Form Styles */
.form-group { margin-bottom: 1.2rem; }
.form-group label {
  display: block; font-weight: bold; margin-bottom: 0.5rem;
}
.form-group input {
  width: 100%; padding: 0.8rem; border: 1px solid #ddd;
  border-radius: 4px; font-size: 1rem; box-sizing: border-box;
}
.weight-preview {
  font-size: 1.5rem; font-weight: bold; color: var(--primary-color);
  background-color: #f0f2f5; padding: 0.8rem; border-radius: 4px;
  text-align: right;
}

/* Footer & Buttons */
.modal-footer {
  margin-top: 1.5rem; display: flex;
  gap: 0.5rem; justify-content: flex-end;
}
.modal-footer button {
  padding: 0.8rem 1.5rem; border: none; border-radius: 4px;
  font-size: 1rem; font-weight: bold; cursor: pointer;
}
.cancel-button { background-color: #757575; color: white; }
.save-button { background-color: var(--primary-color); color: white; }
select {
  width: 100%; padding: 0.8rem; border: 1px solid #ddd;
  border-radius: 4px; font-size: 1rem; box-sizing: border-box;
  background-color: white;
}
.auto-filled-data {
  margin-top: 1rem;
}
.data-display {
  padding: 0.8rem;
  background-color: #f0f2f5;
  border-radius: 4px;
  font-weight: bold;
}
.divider {
  border: none;
  border-top: 1px solid #eee;
  margin: 1.5rem 0;
}
</style>