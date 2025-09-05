# 🔄 Hybrid Lightweight System - RS232 Scale Client

## 📋 ภาพรวม

**Hybrid Lightweight System** เป็นระบบใหม่ที่เพิ่มเข้ามาใน RS232 Scale Client โดยไม่กระทบกับระบบ Online เดิม ระบบนี้ช่วยให้สามารถ:

- ✅ **ทำงานได้ทั้ง Online และ Offline** โดยไม่กระทบระบบเดิม
- ✅ **สร้างบัตรชั่งได้เมื่อ Offline** พร้อมเลขที่ชั่วคราว
- ✅ **พิมพ์รายงานได้เมื่อ Offline** แบบง่าย
- ✅ **Sync ข้อมูลอัตโนมัติ** เมื่อกลับ Online
- ✅ **เก็บข้อมูลสำคัญครบถ้วน** ใน Local Database

## 🚀 ฟีเจอร์ใหม่

### 1. **Hybrid Data Management**
- ข้อมูล Online: ส่งไป Server ทันที + เก็บใน Local
- ข้อมูล Offline: เก็บใน Local เท่านั้น
- Sync อัตโนมัติเมื่อกลับ Online

### 2. **Weighing Ticket System**
- สร้างบัตรชั่งใหม่ (ชั่งเข้า)
- เสร็จสิ้นบัตรชั่ง (ชั่งออก)
- คำนวณน้ำหนักสุทธิอัตโนมัติ
- เลขที่บัตรชั่งชั่วคราว (L001, L002, ...)

### 3. **Report Generation**
- รายงานบัตรชั่งเดี่ยว
- รายงานสรุป
- Export เป็น CSV
- พิมพ์รายงาน

## 📁 ไฟล์ใหม่ที่เพิ่มเข้ามา

### 1. **hybrid_manager.py**
- จัดการการทำงานแบบ Hybrid
- Sync ข้อมูลอัตโนมัติ
- จัดการ Online/Offline Mode

### 2. **weighing_ticket.py**
- จัดการบัตรชั่ง
- Local Database สำหรับบัตรชั่ง
- ฟังก์ชัน CRUD พื้นฐาน

### 3. **report_generator.py**
- สร้างรายงานต่างๆ
- Export เป็น CSV
- ระบบพิมพ์รายงาน

## 🔧 การติดตั้ง

### 1. **วางไฟล์ใหม่**
```
rs232_agent/
├── hybrid_manager.py          # ไฟล์ใหม่
├── weighing_ticket.py         # ไฟล์ใหม่
├── report_generator.py        # ไฟล์ใหม่
└── rs232_client_gui.py       # แก้ไขแล้ว
```

### 2. **Import ในไฟล์หลัก**
```python
# Import สำหรับ Hybrid Lightweight System
from hybrid_manager import HybridLightweightManager
from weighing_ticket import WeighingTicketManager
from report_generator import ReportGenerator
```

### 3. **เริ่มต้นระบบ**
```python
# เพิ่ม Hybrid Lightweight System
self.weighing_ticket_manager = WeighingTicketManager()
self.report_generator = ReportGenerator(self.weighing_ticket_manager)
self.hybrid_manager = HybridLightweightManager(self)
```

## 🎯 วิธีการใช้งาน

### 1. **สร้างบัตรชั่งใหม่**
1. กดปุ่ม **"📝 Create Ticket"** ใน Hybrid Controls
2. กรอกข้อมูล:
   - เลขทะเบียนรถ
   - ชื่อคนขับ
   - รายการสินค้า
3. ระบบจะใช้น้ำหนักปัจจุบันเป็นน้ำหนักชั่งเข้า
4. กด **"✅ สร้างบัตรชั่ง"**

### 2. **เสร็จสิ้นบัตรชั่ง (ชั่งออก)**
1. ใช้ปุ่ม **"📊 Reports"** เพื่อดูรายการบัตรชั่ง
2. เลือกบัตรชั่งที่ต้องการเสร็จสิ้น
3. ระบบจะคำนวณน้ำหนักสุทธิอัตโนมัติ

### 3. **สร้างรายงาน**
1. กดปุ่ม **"📊 Reports"**
2. เลือกประเภทรายงาน:
   - 📊 รายงานสรุป
   - 📁 Export ทั้งหมด (CSV)
   - 📁 Export เสร็จสิ้น (CSV)

### 4. **Sync ข้อมูล**
- **อัตโนมัติ**: ระบบจะ sync ทุก 5 วินาทีเมื่อ Online
- **บังคับ**: กดปุ่ม **"🔄 Sync Now"** ใน Hybrid Status

## 📊 ข้อมูลที่เก็บใน Local Database

### **ตาราง weighing_tickets**
```sql
CREATE TABLE weighing_tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    local_ticket_id TEXT UNIQUE,           -- เลขที่บัตรชั่งชั่วคราว
    vehicle_number TEXT,                   -- เลขทะเบียนรถ
    driver_name TEXT,                      -- ชื่อคนขับ
    product TEXT,                          -- รายการสินค้า
    weight_in REAL,                        -- น้ำหนักชั่งเข้า
    weight_out REAL,                       -- น้ำหนักชั่งออก
    net_weight REAL,                       -- น้ำหนักสุทธิ
    weigh_in_time DATETIME,                -- เวลาชั่งเข้า
    weigh_out_time DATETIME,               -- เวลาชั่งออก
    status TEXT DEFAULT 'active',          -- สถานะ
    synced BOOLEAN DEFAULT 0,              -- สถานะการ sync
    server_ticket_id TEXT,                 -- เลขที่จาก Server
    branch TEXT,                           -- สาขา
    branch_prefix TEXT,                    -- Prefix ของสาขา
    scale_pattern TEXT,                    -- Scale pattern ที่ใช้
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

## 🔄 การทำงานของ Hybrid System

### **Online Mode**
```
ตาชั่ง → Hybrid Manager → Server (ทันที) + Local Database (backup)
```

### **Offline Mode**
```
ตาชั่ง → Hybrid Manager → Local Database (เก็บในคิว)
```

### **Sync Process**
```
Local Database → Hybrid Manager → Server (อัตโนมัติ)
```

## 📱 UI ใหม่ที่เพิ่มเข้ามา

### 1. **Hybrid Status Frame**
- แสดงสถานะ Hybrid Mode
- ปุ่ม Sync Now
- ข้อมูล Cache และ Queue

### 2. **Hybrid Controls Frame**
- ปุ่ม Create Ticket
- ปุ่ม Reports

### 3. **หน้าต่างสร้างบัตรชั่ง**
- ฟอร์มกรอกข้อมูล
- แสดงน้ำหนักปัจจุบัน
- ตรวจสอบความถูกต้อง

### 4. **หน้าต่างรายงาน**
- แสดงสถิติ
- ปุ่มสร้างรายงาน
- ปุ่ม Export CSV

## ⚠️ ข้อควรระวัง

### 1. **การ Sync ข้อมูล**
- ข้อมูลจะ sync อัตโนมัติเมื่อกลับ Online
- ใช้ปุ่ม "Sync Now" เพื่อบังคับ sync ทันที
- ตรวจสอบสถานะ Sync ใน Hybrid Status

### 2. **การสร้างบัตรชั่ง**
- ต้องมีน้ำหนักมากกว่า 0 ก่อนสร้างบัตรชั่ง
- ข้อมูลจะถูกเก็บใน Local Database แม้ Offline
- เลขที่บัตรชั่งจะถูกสร้างอัตโนมัติ

### 3. **การ Export ข้อมูล**
- ไฟล์ CSV จะถูกเก็บในโฟลเดอร์ `reports/`
- ไฟล์รายงานจะถูกเก็บในโฟลเดอร์ `reports/`
- ตรวจสอบสิทธิ์การเขียนไฟล์

## 🐛 การแก้ไขปัญหา

### 1. **Hybrid Manager ไม่ทำงาน**
```python
# ตรวจสอบว่า import ถูกต้อง
from hybrid_manager import HybridLightweightManager

# ตรวจสอบการเริ่มต้น
if hasattr(self, 'hybrid_manager'):
    print("Hybrid Manager พร้อมใช้งาน")
else:
    print("Hybrid Manager ไม่พร้อมใช้งาน")
```

### 2. **ไม่สามารถสร้างบัตรชั่งได้**
- ตรวจสอบน้ำหนักปัจจุบัน
- ตรวจสอบการเชื่อมต่อ Local Database
- ตรวจสอบสิทธิ์การเขียนไฟล์

### 3. **Sync ไม่ทำงาน**
- ตรวจสอบการเชื่อมต่อ Internet
- ตรวจสอบสถานะ Server
- ใช้ปุ่ม "Sync Now" เพื่อบังคับ sync

## 🔮 การพัฒนาต่อ

### 1. **ฟีเจอร์ที่อาจเพิ่มในอนาคต**
- ระบบค้นหาบัตรชั่ง
- รายงานแบบกราฟ
- การจัดการผู้ใช้
- การตั้งค่าขั้นสูง

### 2. **การปรับปรุงประสิทธิภาพ**
- การ cache ข้อมูล
- การ optimize database
- การจัดการ memory

## 📞 การสนับสนุน

หากมีปัญหาหรือคำถามเกี่ยวกับ Hybrid Lightweight System:

1. ตรวจสอบ Log ใน Activity Log
2. ตรวจสอบสถานะ Hybrid Mode
3. ตรวจสอบการเชื่อมต่อ Database
4. ตรวจสอบสิทธิ์การเขียนไฟล์

---

**Hybrid Lightweight System** ออกแบบมาเพื่อให้ระบบทำงานได้อย่างต่อเนื่องทั้งในสถานการณ์ Online และ Offline โดยไม่กระทบกับระบบเดิมที่มีอยู่
