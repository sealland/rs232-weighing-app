# ตัวอย่างการใช้งาน Feature "บันทึกเลขคิว"

## ภาพรวม
Feature นี้จะบันทึกเลขคิว (WE_SEQ) ลงในฐานข้อมูลเมื่อผู้ใช้สร้างบัตรชั่งใหม่ โดยเลขคิวจะถูกดึงมาจากการเลือกคิวรถในหน้า Modal

## การทำงานของระบบ

### 1. การเลือกคิวรถ
```vue
<!-- ใน CreateTicketModal.vue -->
<select id="car-queue-select" v-model="selectedQueueSeq" :disabled="continuousDataFromPrevTicket" required>
  <option disabled value="">-- กรุณาเลือกคิวรถ --</option>
  <option v-for="queue in carQueue" :key="queue.SEQ" :value="queue.SEQ">
    คิว {{ queue.SEQ }} - {{ queue.CARLICENSE }} ({{ queue.AR_NAME }})
  </option>
</select>
```

### 2. การส่งข้อมูลไปยัง Backend
```javascript
// ใน CreateTicketModal.vue - handleSave function
let mainDataPayload = {
  WE_LICENSE: sourceData.CARLICENSE,
  WE_VENDOR: sourceData.AR_NAME,
  WE_VENDOR_CD: sourceData.KUNNR,
  WE_WEIGHTIN: finalWeightIn.value,
  // --- เพิ่มการส่งเลขคิว ---
  WE_SEQ: props.continuousDataFromPrevTicket ? 
    props.continuousDataFromPrevTicket.WE_SEQ : 
    selectedQueueObject.value?.SEQ
};
```

### 3. การบันทึกในฐานข้อมูล
```python
# ใน crud.py - create_ticket function
db_ticket = models.WeightTicket(
    WE_ID=new_ticket_id,
    WE_LICENSE=ticket.WE_LICENSE,
    WE_WEIGHTIN=ticket.WE_WEIGHTIN,
    # ... ข้อมูลอื่นๆ ...
    # --- เพิ่มการบันทึกเลขคิว ---
    WE_SEQ=ticket.WE_SEQ  # บันทึกเลขคิวจากข้อมูลที่ส่งมา
)
```

## ตัวอย่างข้อมูลที่บันทึก

### ข้อมูลคิวรถ (จากตาราง CarVisit)
```json
{
  "SEQ": "001",
  "CARLICENSE": "กข-1234",
  "AR_NAME": "บริษัท ตัวอย่าง จำกัด",
  "KUNNR": "CUST001"
}
```

### ข้อมูลบัตรชั่งที่สร้าง (ในตาราง TBL_WEIGHT)
```json
{
  "WE_ID": "Z11225001",
  "WE_LICENSE": "กข-1234",
  "WE_VENDOR": "บริษัท ตัวอย่าง จำกัด",
  "WE_VENDOR_CD": "CUST001",
  "WE_WEIGHTIN": 15000.5,
  "WE_SEQ": "001",  // ← เลขคิวที่บันทึกใหม่
  "WE_DATE": "2024-12-25",
  "WE_TIMEIN": "2024-12-25T10:30:00"
}
```

## การทดสอบ

### 1. ทดสอบการสร้างบัตรชั่งปกติ
1. เปิดหน้า Modal สร้างบัตรชั่งใหม่
2. เลือกคิวรถจาก dropdown
3. ตรวจสอบว่าเลขคิวถูกแสดงในส่วนข้อมูลรถ
4. บันทึกบัตรชั่ง
5. ตรวจสอบในฐานข้อมูลว่า WE_SEQ ถูกบันทึกถูกต้อง

### 2. ทดสอบการสร้างบัตรชั่งต่อเนื่อง
1. สร้างบัตรชั่งแรก (จะมีเลขคิว)
2. สร้างบัตรชั่งต่อเนื่องจากบัตรแรก
3. ตรวจสอบว่าเลขคิวจากบัตรแรกถูกส่งต่อไปยังบัตรต่อเนื่อง

## API Endpoints ที่เกี่ยวข้อง

### สร้างบัตรชั่งใหม่
```
POST /api/tickets/
Content-Type: application/json

{
  "WE_LICENSE": "กข-1234",
  "WE_VENDOR": "บริษัท ตัวอย่าง จำกัด",
  "WE_VENDOR_CD": "CUST001",
  "WE_WEIGHTIN": 15000.5,
  "WE_SEQ": "001"
}
```

### ดึงข้อมูลคิวรถ
```
GET /api/car-queue/
```

## หมายเหตุสำคัญ

1. **ฟิลด์ WE_SEQ เป็น nullable** - หมายความว่าบัตรชั่งอาจไม่มีเลขคิวได้ (กรณีสร้างแบบไม่ผ่านคิว)
2. **การตรวจสอบข้อมูล** - ระบบจะตรวจสอบว่าเลขคิวที่ส่งมาสอดคล้องกับข้อมูลรถที่เลือก
3. **การแสดงผล** - เลขคิวจะถูกแสดงในส่วนข้อมูลรถในหน้า Modal
4. **การส่งต่อข้อมูล** - ในกรณีชั่งต่อเนื่อง เลขคิวจะถูกส่งต่อจากบัตรแม่ไปยังบัตรลูก
