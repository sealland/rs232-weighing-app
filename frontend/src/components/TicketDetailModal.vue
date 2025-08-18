<script setup>
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
const emit = defineEmits(['close']);


</script>

<template>
    <div v-if="visible" class="modal-overlay" @click.self="emit('close')">
      <div class="modal-content">
        <div class="modal-header">
          <h3>รายละเอียดบัตรชั่ง: {{ ticket?.WE_ID }}</h3>
          <button class="close-button" @click="emit('close')">&times;</button>
        </div>
  
        <div class="modal-body" v-if="ticket">
          <!-- ข้อมูลหลักของบัตร (รวมข้อมูลลูกค้า) -->
          <div class="detail-grid">
            <div><strong>ทะเบียนรถ:</strong> {{ ticket.WE_LICENSE }}</div>
            <!-- เพิ่มข้อมูลลูกค้า -->
            <div class="customer-info"><strong>ลูกค้า:</strong> {{ ticket.WE_VENDOR_CD }} - {{ ticket.WE_VENDOR }}</div>
            
            <div><strong>เวลาชั่งเข้า:</strong> {{ new Date(ticket.WE_TIMEIN).toLocaleString('th-TH') }}</div>
            <div><strong>เวลาชั่งออก:</strong> {{ ticket.WE_TIMEOUT ? new Date(ticket.WE_TIMEOUT).toLocaleString('th-TH') : '-' }}</div>
            <div><strong>น้ำหนักชั่งเข้า:</strong> {{ ticket.WE_WEIGHTIN?.toLocaleString('en-US') }} กก.</div>
            <div><strong>น้ำหนักชั่งออก:</strong> {{ ticket.WE_WEIGHTOUT?.toLocaleString('en-US') || '0' }} กก.</div>
            <div class="net-weight">
            <strong>น้ำหนักสุทธิ:</strong> {{ ticket.WE_WEIGHTNET?.toLocaleString('en-US') || '0' }} กก.
            </div>
            <div><strong>ผู้ใช้งาน:</strong> {{ ticket.WE_USER || '-' }}</div>
          </div>
  
          <!-- รายการสินค้า (แสดงผลตามเงื่อนไข) -->
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
                <tr>
                  <td>{{ ticket.WE_DIREF }}</td>
                  <td>{{ ticket.WE_MAT_CD }}</td>
                  <td>{{ ticket.WE_MAT }}</td>
                  <td>{{ ticket.WE_QTY }}</td>
                  <td>{{ ticket.WE_UOM }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
        <div v-else class="loading">
          กำลังโหลดข้อมูล...
        </div>
      </div>
    </div>
  </template>

<style scoped>
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
  padding: 2rem;
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
}
.detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 1rem;
  margin-bottom: 2rem;
}
.detail-grid div {
  background-color: #f9f9f9;
  padding: 0.8rem;
  border-radius: 4px;
}
.net-weight {
  font-size: 1.1rem;
  font-weight: bold;
  background-color: #eef7f3 !important;
  color: var(--primary-color);
}
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
.loading {
  text-align: center;
  padding: 3rem;
  color: #888;
}
.detail-grid {
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); /* ปรับขนาดให้กว้างขึ้นเล็กน้อย */
}
.customer-info {
  /* ทำให้ข้อมูลลูกค้าเด่นขึ้น และกินพื้นที่เต็มแถวถ้าเป็นไปได้ */
  grid-column: 1 / -1; 
  font-weight: bold;
}
</style>