<script setup>
import { ref, watch } from 'vue';
// กำหนด props ที่ Component นี้จะรับเข้ามา
// 'ticket' คือ object ข้อมูลบัตรชั่ง
// 'visible' คือ boolean สำหรับควบคุมการแสดงผล
const props = defineProps({
  ticket: {
    type: Object,
    default: null
  },
  visible: {
    type: Boolean,
    default: false
  }
});

// กำหนด event ที่ Component นี้จะส่งกลับไปหาแม่
// 'close' คือ event ที่จะถูกส่งออกไปเมื่อผู้ใช้กดปิด
const emit = defineEmits(['close', 'weigh-out', 'update-ticket']);

// --- State Management (ปรับปรุงใหม่ทั้งหมด) ---
const isEditing = ref(false);

// editableTicket จะถูกสร้างขึ้นมาใหม่ทุกครั้งที่เข้าโหมดแก้ไข
const editableLicense = ref(''); 

// ---- watcher -----
watch(() => props.ticket, () => {
  isEditing.value = false;
});

//funciton

function startEditing() {
  // เมื่อเริ่มแก้ไข ให้ copy ทะเบียนรถปัจจุบันมาเก็บไว้
  editableLicense.value = props.ticket.WE_LICENSE;
  isEditing.value = true;
}

function handleSaveChanges() {
  // สร้าง object ข้อมูลที่แก้ไขแล้วเพื่อส่งกลับ
  const updatedData = {
    ...props.ticket, // เอาข้อมูลเดิมทั้งหมดมา
    WE_LICENSE: editableLicense.value // เอาทะเบียนรถที่แก้ไขใหม่ทับเข้าไป
  };
  emit('ticket-updated', updatedData);
  // isEditing จะถูก reset โดย watcher เมื่อข้อมูลอัปเดต
}

function cancelEdit() {
  // แค่ปิดโหมดแก้ไข ไม่ต้องทำอะไรกับข้อมูล
  isEditing.value = false;
}
</script>

<template>
  <div v-if="visible" class="modal-overlay" @click.self="emit('close')">
    <div class="modal-content">
      <div class="modal-header">
        <h3>รายละเอียดบัตรชั่ง: {{ ticket?.WE_ID }}</h3>
        <button class="close-button" @click="emit('close')">&times;</button>
      </div>

      <div class="modal-body" v-if="ticket">
        <!-- ข้อมูลหลักของบัตร -->
        <div class="detail-grid">
          <div>
            <strong>ทะเบียนรถ:</strong>
            <!-- แสดง input เมื่ออยู่ในโหมดแก้ไข -->
            <input v-if="isEditing" type="text" v-model="editableLicense" class="edit-input">
            <!-- แสดงข้อความปกติ -->
            <span v-else>{{ ticket.WE_LICENSE }}</span>
          </div>
          <div class="customer-info"><strong>ลูกค้า:</strong> {{ ticket.WE_VENDOR_CD }} - {{ ticket.WE_VENDOR }}</div>
          
          <div><strong>เวลาชั่งเข้า:</strong> {{ new Date(ticket.WE_TIMEIN).toLocaleString('th-TH') }}</div>
          <div><strong>เวลาชั่งออก:</strong> {{ ticket.WE_TIMEOUT ? new Date(ticket.WE_TIMEOUT).toLocaleString('th-TH') : '-' }}</div>
          <div><strong>น้ำหนักชั่งเข้า:</strong> {{ ticket.WE_WEIGHTIN?.toLocaleString('en-US') }} กก.</div>
          <div><strong>น้ำหนักชั่งออก:</strong> {{ ticket.WE_WEIGHTOUT?.toLocaleString('en-US') || '0' }} กก.</div>
          <div class="net-weight"><strong>น้ำหนักสุทธิ:</strong> {{ ticket.WE_WEIGHTNET?.toLocaleString('en-US') || '0' }} กก.</div>
          <div><strong>ผู้ใช้งาน:</strong> {{ ticket.WE_USER || '-' }}</div>
        </div>

        <!-- รายการสินค้า -->
        <h4>รายการสินค้า</h4>
        <div class="items-table-container">
          <!-- กรณีที่ 1: ชั่งรวม (มีข้อมูลใน ticket.items) -->
          <table v-if="ticket.items && ticket.items.length > 0">
            <thead>
              <tr>
                <th>เลขที่เอกสาร</th>
                <th>ลำดับ</th>
                <th>รหัสสินค้า</th>
                <th>ชื่อสินค้า</th>
                <th>จำนวน</th>
                <th>หน่วยนับ</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(item, index) in ticket.items" :key="index">
                <td>{{ item.VBELN }}</td>
                <td>{{ item.POSNR }}</td>
                <td>{{ item.WE_MAT_CD }}</td>
                <td>{{ item.WE_MAT }}</td>
                <td>{{ item.WE_QTY }}</td>
                <td>{{ item.WE_UOM }}</td>
              </tr>
            </tbody>
          </table>
          
          <!-- กรณีที่ 2: ชั่งแยก (ไม่มีข้อมูลใน ticket.items) -->
          <table v-else>
             <thead>
              <tr>
                <th>เลขที่เอกสาร</th>
                <th>รหัสสินค้า</th>
                <th>ชื่อสินค้า</th>
                <th>จำนวน</th>
                <th>หน่วยนับ</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="ticket.WE_ID">
                <td>{{ ticket.WE_DIREF }}</td>
                <td>{{ ticket.WE_MAT_CD }}</td>
                <td>{{ ticket.WE_MAT }}</td>
                <td>{{ ticket.WE_QTY }}</td>
                <td>{{ ticket.WE_UOM }}</td>
              </tr>
               <tr v-else>
                 <td colspan="5">ไม่พบรายการสินค้า</td>
               </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div v-else class="loading">
        กำลังโหลดข้อมูล...
      </div>

      <!-- Footer ของ Modal -->
      <div class="modal-footer" v-if="ticket">
        <!-- ปุ่มชั่งออก จะแสดงเมื่อยังไม่ชั่งออก และไม่ได้อยู่ในโหมดแก้ไข -->
        <button 
          v-if="!ticket.WE_WEIGHTOUT && !isEditing" 
          class="weigh-out-button"
          @click="emit('weigh-out')"
        >
          บันทึกน้ำหนักชั่งออก
        </button>

        <!-- ส่วนของปุ่มแก้ไข (แก้ไขให้ถูกต้อง) -->
        <div class="edit-actions">
          <!-- โหมดปกติ: แสดงปุ่ม "แก้ไข" -->
          <button v-if="!isEditing" @click="startEditing" class="edit-button">แก้ไขข้อมูล</button>
          
          <!-- โหมดแก้ไข: แสดงปุ่ม "ยกเลิก" และ "บันทึกการแก้ไข" -->
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
</style>