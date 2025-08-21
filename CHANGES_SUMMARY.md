# สรุปการเปลี่ยนแปลง - Feature "บันทึกเลขคิว"

## ไฟล์ที่แก้ไข

### 1. backend/models.py
**การเปลี่ยนแปลง:**
- เพิ่มฟิลด์ `WE_SEQ` ในตาราง `TBL_WEIGHT`
- ฟิลด์เป็น `String` และ `nullable=True`

**บรรทัดที่แก้ไข:**
```python
# --- เพิ่มฟิลด์ WE_SEQ สำหรับเก็บเลขคิว ---
WE_SEQ = Column(String, nullable=True)  # เลขคิวจากตาราง CarVisit
```

### 2. backend/schemas.py
**การเปลี่ยนแปลง:**
- เพิ่ม `WE_SEQ` ใน `WeightTicketCreate` schema
- เพิ่ม `WE_SEQ` ใน `WeightTicket` schema สำหรับการอ่านข้อมูล

**บรรทัดที่แก้ไข:**
```python
# ใน WeightTicketCreate
WE_SEQ: Optional[str] = None  # เลขคิวจากตาราง CarVisit

# ใน WeightTicket
WE_SEQ: Optional[str] = None  # เลขคิวจากตาราง CarVisit
```

### 3. backend/crud.py
**การเปลี่ยนแปลง:**
- แก้ไขฟังก์ชัน `create_ticket` เพื่อบันทึก `WE_SEQ` ลงฐานข้อมูล
- เพิ่มคอมเม้นอธิบายการเปลี่ยนแปลง

**บรรทัดที่แก้ไข:**
```python
# --- เพิ่มการบันทึกเลขคิว ---
WE_SEQ=ticket.WE_SEQ  # บันทึกเลขคิวจากข้อมูลที่ส่งมา
```

### 4. frontend/src/components/CreateTicketModal.vue
**การเปลี่ยนแปลง:**
- แก้ไขฟังก์ชัน `handleSave` เพื่อส่ง `WE_SEQ` ไปยัง backend
- เพิ่มการดึงเลขคิวจาก `selectedQueueObject.value?.SEQ`

**บรรทัดที่แก้ไข:**
```javascript
// --- เพิ่มการส่งเลขคิว ---
WE_SEQ: props.continuousDataFromPrevTicket ? 
  props.continuousDataFromPrevTicket.WE_SEQ : 
  selectedQueueObject.value?.SEQ
```

## การทำงานของระบบ

### Flow การบันทึกเลขคิว:
1. **ผู้ใช้เลือกคิวรถ** ใน dropdown ของ Modal
2. **Frontend ดึงเลขคิว** จาก `selectedQueueObject.value?.SEQ`
3. **ส่งข้อมูลไปยัง Backend** ผ่าน API `/api/tickets/`
4. **Backend บันทึกลงฐานข้อมูล** ในฟิลด์ `WE_SEQ` ของตาราง `TBL_WEIGHT`

### กรณีพิเศษ:
- **การชั่งต่อเนื่อง**: เลขคิวจะถูกส่งต่อจากบัตรแม่ไปยังบัตรลูก
- **การสร้างบัตรปกติ**: เลขคิวจะถูกดึงจากการเลือกคิวรถ

## การทดสอบ

### ทดสอบการสร้างบัตรชั่งปกติ:
```bash
# 1. เปิดหน้า Modal สร้างบัตรชั่งใหม่
# 2. เลือกคิวรถจาก dropdown
# 3. บันทึกบัตรชั่ง
# 4. ตรวจสอบในฐานข้อมูลว่า WE_SEQ ถูกบันทึก
```

### ทดสอบการสร้างบัตรชั่งต่อเนื่อง:
```bash
# 1. สร้างบัตรชั่งแรก (มีเลขคิว)
# 2. สร้างบัตรชั่งต่อเนื่อง
# 3. ตรวจสอบว่าเลขคิวถูกส่งต่อ
```

## ข้อควรระวัง

1. **Migration ฐานข้อมูล**: ต้องเพิ่มคอลัมน์ `WE_SEQ` ในตาราง `TBL_WEIGHT`
2. **การตรวจสอบข้อมูล**: ระบบจะตรวจสอบว่าเลขคิวสอดคล้องกับข้อมูลรถ
3. **Backward Compatibility**: ฟิลด์เป็น nullable จึงไม่กระทบกับข้อมูลเก่า

## API ที่เกี่ยวข้อง

- `POST /api/tickets/` - สร้างบัตรชั่งใหม่ (รองรับ WE_SEQ)
- `GET /api/car-queue/` - ดึงข้อมูลคิวรถ
- `GET /api/tickets/{ticket_id}` - ดึงข้อมูลบัตรชั่ง (แสดง WE_SEQ)

## ผลลัพธ์ที่คาดหวัง

หลังจากแก้ไขแล้ว ระบบจะสามารถ:
- บันทึกเลขคิวลงในฐานข้อมูลเมื่อสร้างบัตรชั่งใหม่
- แสดงเลขคิวในข้อมูลบัตรชั่ง
- ส่งต่อเลขคิวในกรณีชั่งต่อเนื่อง
- รองรับการสร้างบัตรชั่งแบบไม่มีเลขคิว (nullable)
