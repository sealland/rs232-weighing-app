# ตัวอย่างการใช้งาน Feature "คัดลอกเลขคิวเมื่อกดชั่งต่อเนื่อง"

## ภาพรวม
Feature นี้จะคัดลอกเลขคิวจากบัตรชั่งหลักไปยังบัตรชั่งต่อเนื่อง และอัปเดตฟิลด์ WE_CONT ในบัตรชั่งหลักด้วย ID ของบัตรชั่งต่อเนื่อง

## การทำงานของระบบ

### 1. การแสดงผลในหน้า Modal
```vue
<!-- กรณีชั่งต่อเนื่อง - แสดงเลขคิวที่คัดลอก -->
<div v-if="continuousDataFromPrevTicket" class="copied-queue-display">
  <div class="copied-queue-info">
    <strong>เลขคิวที่คัดลอก:</strong> {{ autoFilledData?.WE_SEQ }}
    <small>(คัดลอกจากบัตรชั่งหลัก)</small>
  </div>
</div>

<!-- กรณีสร้างบัตรใหม่ปกติ - แสดง dropdown เลือกคิว -->
<select v-if="!continuousDataFromPrevTicket">
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
    props.continuousDataFromPrevTicket.WE_SEQ :  // คัดลอกจากบัตรแม่
    selectedQueueObject.value?.SEQ               // เลือกจาก dropdown
};

// ส่ง parent_id สำหรับการอัปเดต WE_CONT
const finalPayload = {
  ...mainDataPayload,
  items: itemsPayload,
  parent_id: props.continuousDataFromPrevTicket ? props.continuousDataFromPrevTicket.PARENT_ID : null
};
```

### 3. การบันทึกในฐานข้อมูล
```python
# ใน crud.py - create_ticket function
# 1. สร้างบัตรชั่งต่อเนื่อง
db_ticket = models.WeightTicket(
    WE_ID=new_ticket_id,
    WE_LICENSE=ticket.WE_LICENSE,
    WE_WEIGHTIN=ticket.WE_WEIGHTIN,
    # ... ข้อมูลอื่นๆ ...
    WE_SEQ=ticket.WE_SEQ  # บันทึกเลขคิวที่คัดลอกมา
)

# 2. อัปเดตบัตรชั่งหลัก
if ticket.parent_id:
    parent_ticket = db.query(models.WeightTicket).filter(
        models.WeightTicket.WE_ID == ticket.parent_id
    ).first()
    
    if parent_ticket:
        # อัปเดต field WE_CONT ของบัตรแม่ ด้วย ID ของบัตรใหม่
        parent_ticket.WE_CONT = new_ticket_id
        db.commit()
```

## ตัวอย่างข้อมูลที่บันทึก

### บัตรชั่งหลัก (Original Ticket)
```json
{
  "WE_ID": "Z11225001",
  "WE_LICENSE": "กข-1234",
  "WE_VENDOR": "บริษัท ตัวอย่าง จำกัด",
  "WE_VENDOR_CD": "CUST001",
  "WE_WEIGHTIN": 15000.5,
  "WE_SEQ": "001",
  "WE_CONT": null,  // ยังไม่มีบัตรต่อเนื่อง
  "WE_DATE": "2024-12-25",
  "WE_TIMEIN": "2024-12-25T10:30:00"
}
```

### บัตรชั่งต่อเนื่อง (Continuous Ticket)
```json
{
  "WE_ID": "Z11225002",
  "WE_LICENSE": "กข-1234",
  "WE_VENDOR": "บริษัท ตัวอย่าง จำกัด",
  "WE_VENDOR_CD": "CUST001",
  "WE_WEIGHTIN": 12000.0,
  "WE_SEQ": "001",  // ← คัดลอกจากบัตรหลัก
  "WE_DATE": "2024-12-25",
  "WE_TIMEIN": "2024-12-25T11:00:00"
}
```

### บัตรชั่งหลักหลังอัปเดต
```json
{
  "WE_ID": "Z11225001",
  "WE_LICENSE": "กข-1234",
  "WE_VENDOR": "บริษัท ตัวอย่าง จำกัด",
  "WE_VENDOR_CD": "CUST001",
  "WE_WEIGHTIN": 15000.5,
  "WE_SEQ": "001",
  "WE_CONT": "Z11225002",  // ← อัปเดตด้วย ID บัตรต่อเนื่อง
  "WE_DATE": "2024-12-25",
  "WE_TIMEIN": "2024-12-25T10:30:00"
}
```

## การทดสอบ

### 1. ทดสอบการสร้างบัตรชั่งต่อเนื่อง
1. สร้างบัตรชั่งแรก (มีเลขคิว "001")
2. กดปุ่ม "ชั่งต่อเนื่อง" จากบัตรแรก
3. ตรวจสอบว่าเลขคิว "001" ถูกแสดงในส่วน "เลขคิวที่คัดลอก"
4. บันทึกบัตรชั่งต่อเนื่อง
5. ตรวจสอบในฐานข้อมูล:
   - บัตรต่อเนื่องมี WE_SEQ = "001"
   - บัตรหลักมี WE_CONT = ID ของบัตรต่อเนื่อง

### 2. ทดสอบการแสดงผล UI
1. เปิด Modal ชั่งต่อเนื่อง
2. ตรวจสอบว่า dropdown เลือกคิวถูกซ่อน
3. ตรวจสอบว่าแสดงเลขคิวที่คัดลอกในกล่องสีน้ำเงิน
4. ตรวจสอบว่าแสดงข้อความ "(คัดลอกจากบัตรชั่งหลัก)"

### 3. ทดสอบการส่งข้อมูล
```bash
# ตรวจสอบ API Request
POST /api/tickets/
{
  "WE_LICENSE": "กข-1234",
  "WE_VENDOR": "บริษัท ตัวอย่าง จำกัด",
  "WE_VENDOR_CD": "CUST001",
  "WE_WEIGHTIN": 12000.0,
  "WE_SEQ": "001",  // ← คัดลอกจากบัตรหลัก
  "parent_id": "Z11225001"  // ← ID บัตรหลัก
}
```

## API Endpoints ที่เกี่ยวข้อง

### สร้างบัตรชั่งต่อเนื่อง
```
POST /api/tickets/
Content-Type: application/json

{
  "WE_LICENSE": "กข-1234",
  "WE_VENDOR": "บริษัท ตัวอย่าง จำกัด",
  "WE_VENDOR_CD": "CUST001",
  "WE_WEIGHTIN": 12000.0,
  "WE_SEQ": "001",
  "parent_id": "Z11225001"
}
```

### ดึงข้อมูลบัตรชั่ง
```
GET /api/tickets/{ticket_id}
```

## หมายเหตุสำคัญ

1. **การคัดลอกเลขคิว**: เลขคิวจะถูกคัดลอกจากบัตรหลักไปยังบัตรต่อเนื่องโดยอัตโนมัติ
2. **การอัปเดต WE_CONT**: บัตรหลักจะถูกอัปเดตด้วย ID ของบัตรต่อเนื่อง
3. **การแสดงผล**: UI จะแสดงเลขคิวที่คัดลอกในกล่องสีน้ำเงิน
4. **การตรวจสอบ**: ระบบจะตรวจสอบว่า parent_id มีอยู่จริงก่อนอัปเดต
5. **Error Handling**: หากการอัปเดตบัตรหลักล้มเหลว บัตรต่อเนื่องจะยังคงถูกสร้างสำเร็จ

## Flow การทำงาน

```
1. ผู้ใช้กด "ชั่งต่อเนื่อง" จากบัตรหลัก
   ↓
2. Modal เปิดขึ้นพร้อมข้อมูลที่คัดลอกมา
   ↓
3. แสดงเลขคิวที่คัดลอกในกล่องสีน้ำเงิน
   ↓
4. ผู้ใช้กรอกข้อมูลและบันทึก
   ↓
5. สร้างบัตรชั่งต่อเนื่องพร้อม WE_SEQ ที่คัดลอก
   ↓
6. อัปเดต WE_CONT ในบัตรหลักด้วย ID บัตรต่อเนื่อง
   ↓
7. เสร็จสิ้น
```
