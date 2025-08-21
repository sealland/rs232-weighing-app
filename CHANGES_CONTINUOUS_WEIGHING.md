# สรุปการเปลี่ยนแปลง - Feature "คัดลอกเลขคิวเมื่อกดชั่งต่อเนื่อง"

## ไฟล์ที่แก้ไข

### 1. backend/models.py
**การเปลี่ยนแปลง:**
- เพิ่มฟิลด์ `WE_CONT` ในตาราง `TBL_WEIGHT` สำหรับเก็บ ID ของบัตรชั่งต่อเนื่อง

**บรรทัดที่แก้ไข:**
```python
# --- เพิ่มฟิลด์ WE_CONT สำหรับเก็บ ID บัตรลูก (ชั่งต่อเนื่อง) ---
WE_CONT = Column(String, nullable=True)  # ID ของบัตรชั่งต่อเนื่อง
```

### 2. backend/schemas.py
**การเปลี่ยนแปลง:**
- เพิ่ม `WE_CONT` ใน `WeightTicket` schema สำหรับการอ่านข้อมูล

**บรรทัดที่แก้ไข:**
```python
# --- เพิ่ม WE_CONT สำหรับการอ่านข้อมูล ---
WE_CONT: Optional[str] = None  # ID ของบัตรชั่งต่อเนื่อง
```

### 3. backend/crud.py
**การเปลี่ยนแปลง:**
- ปรับปรุงฟังก์ชัน `create_ticket` เพื่ออัปเดต `WE_CONT` ในบัตรชั่งหลัก
- เพิ่มคอมเม้นและ error handling ที่ชัดเจน

**บรรทัดที่แก้ไข:**
```python
# --- จุดสำคัญ: อัปเดตบัตรแม่เมื่อเป็นการชั่งต่อเนื่อง ---
if ticket.parent_id:
    try:
        # ค้นหาบัตรแม่จาก parent_id
        parent_ticket = db.query(models.WeightTicket).filter(
            models.WeightTicket.WE_ID == ticket.parent_id
        ).first()

        if parent_ticket:
            # อัปเดต field WE_CONT ของบัตรแม่ ด้วย ID ของบัตรใหม่ (ชั่งต่อเนื่อง)
            parent_ticket.WE_CONT = new_ticket_id
            db.commit()
            db.refresh(parent_ticket)
            print(f"✅ Successfully updated parent ticket {ticket.parent_id} with child ID {new_ticket_id}")
            print(f"   - Parent WE_CONT field updated to: {new_ticket_id}")
        else:
            print(f"⚠️  Warning: Parent ticket with ID {ticket.parent_id} not found.")
            print(f"   - Cannot update WE_CONT field for parent ticket")

    except Exception as e:
        print(f"❌ Error updating parent ticket: {e}")
        # ไม่ rollback เพราะบัตรใหม่ถูกสร้างสำเร็จแล้ว
        # เราไม่ต้องการให้การสร้างบัตรใหม่ล้มเหลวเพราะการอัปเดตบัตรแม่มีปัญหา
```

### 4. frontend/src/components/CreateTicketModal.vue
**การเปลี่ยนแปลง:**
- ปรับปรุง UI สำหรับแสดงเลขคิวที่คัดลอกในกรณีชั่งต่อเนื่อง
- เพิ่ม CSS สำหรับการแสดงผลเลขคิวที่คัดลอก

**บรรทัดที่แก้ไข:**
```vue
<!-- แสดง dropdown สำหรับเลือกคิวรถ (เฉพาะกรณีสร้างบัตรใหม่ปกติ) -->
<select id="car-queue-select" v-model="selectedQueueSeq" :disabled="continuousDataFromPrevTicket" required v-if="!continuousDataFromPrevTicket">
  <option disabled value="">-- กรุณาเลือกคิวรถ --</option>
  <option v-for="queue in carQueue" :key="queue.SEQ" :value="queue.SEQ">
    คิว {{ queue.SEQ }} - {{ queue.CARLICENSE }} ({{ queue.AR_NAME }})
  </option>
</select>

<!-- แสดงเลขคิวที่คัดลอกมา (กรณีชั่งต่อเนื่อง) -->
<div v-if="continuousDataFromPrevTicket" class="copied-queue-display">
  <div class="copied-queue-info">
    <strong>เลขคิวที่คัดลอก:</strong> {{ autoFilledData?.WE_SEQ }}
    <small>(คัดลอกจากบัตรชั่งหลัก)</small>
  </div>
</div>
```

**CSS ที่เพิ่ม:**
```css
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
```

## การทำงานของระบบ

### Flow การคัดลอกเลขคิว:
1. **ผู้ใช้กด "ชั่งต่อเนื่อง"** จากบัตรชั่งหลัก
2. **Modal เปิดขึ้น** พร้อมข้อมูลที่คัดลอกมา (รวมเลขคิว)
3. **แสดงเลขคิวที่คัดลอก** ในกล่องสีน้ำเงินแทน dropdown
4. **ผู้ใช้บันทึกบัตรชั่งต่อเนื่อง**
5. **สร้างบัตรชั่งต่อเนื่อง** พร้อม WE_SEQ ที่คัดลอกมา
6. **อัปเดต WE_CONT** ในบัตรชั่งหลักด้วย ID ของบัตรชั่งต่อเนื่อง

### การส่งข้อมูล:
```javascript
// กรณีชั่งต่อเนื่อง
WE_SEQ: props.continuousDataFromPrevTicket ? 
  props.continuousDataFromPrevTicket.WE_SEQ :  // คัดลอกจากบัตรแม่
  selectedQueueObject.value?.SEQ               // เลือกจาก dropdown

// ส่ง parent_id สำหรับการอัปเดต WE_CONT
parent_id: props.continuousDataFromPrevTicket ? props.continuousDataFromPrevTicket.PARENT_ID : null
```

## การทดสอบ

### ทดสอบการสร้างบัตรชั่งต่อเนื่อง:
```bash
# 1. สร้างบัตรชั่งแรก (มีเลขคิว "001")
# 2. กดปุ่ม "ชั่งต่อเนื่อง" จากบัตรแรก
# 3. ตรวจสอบว่าเลขคิว "001" ถูกแสดงในส่วน "เลขคิวที่คัดลอก"
# 4. บันทึกบัตรชั่งต่อเนื่อง
# 5. ตรวจสอบในฐานข้อมูล:
#    - บัตรต่อเนื่องมี WE_SEQ = "001"
#    - บัตรหลักมี WE_CONT = ID ของบัตรต่อเนื่อง
```

### ทดสอบการแสดงผล UI:
```bash
# 1. เปิด Modal ชั่งต่อเนื่อง
# 2. ตรวจสอบว่า dropdown เลือกคิวถูกซ่อน
# 3. ตรวจสอบว่าแสดงเลขคิวที่คัดลอกในกล่องสีน้ำเงิน
# 4. ตรวจสอบว่าแสดงข้อความ "(คัดลอกจากบัตรชั่งหลัก)"
```

## ข้อควรระวัง

1. **Migration ฐานข้อมูล**: ต้องเพิ่มคอลัมน์ `WE_CONT` ในตาราง `TBL_WEIGHT`
2. **การตรวจสอบข้อมูล**: ระบบจะตรวจสอบว่า parent_id มีอยู่จริงก่อนอัปเดต
3. **Error Handling**: หากการอัปเดตบัตรหลักล้มเหลว บัตรต่อเนื่องจะยังคงถูกสร้างสำเร็จ
4. **Backward Compatibility**: ฟิลด์เป็น nullable จึงไม่กระทบกับข้อมูลเก่า

## API ที่เกี่ยวข้อง

- `POST /api/tickets/` - สร้างบัตรชั่งใหม่/ต่อเนื่อง (รองรับ WE_SEQ และ parent_id)
- `GET /api/tickets/{ticket_id}` - ดึงข้อมูลบัตรชั่ง (แสดง WE_SEQ และ WE_CONT)

## ผลลัพธ์ที่คาดหวัง

หลังจากแก้ไขแล้ว ระบบจะสามารถ:
- คัดลอกเลขคิวจากบัตรชั่งหลักไปยังบัตรชั่งต่อเนื่องโดยอัตโนมัติ
- แสดงเลขคิวที่คัดลอกในกล่องสีน้ำเงินในหน้า Modal
- อัปเดตฟิลด์ WE_CONT ในบัตรชั่งหลักด้วย ID ของบัตรชั่งต่อเนื่อง
- รองรับการสร้างบัตรชั่งต่อเนื่องหลายครั้ง
- จัดการ error cases อย่างเหมาะสม

## ตัวอย่างข้อมูลที่บันทึก

### บัตรชั่งหลักหลังอัปเดต:
```json
{
  "WE_ID": "Z11225001",
  "WE_SEQ": "001",
  "WE_CONT": "Z11225002",  // ← ID ของบัตรชั่งต่อเนื่อง
  "WE_LICENSE": "กข-1234"
}
```

### บัตรชั่งต่อเนื่อง:
```json
{
  "WE_ID": "Z11225002",
  "WE_SEQ": "001",  // ← คัดลอกจากบัตรหลัก
  "WE_LICENSE": "กข-1234"
}
```
