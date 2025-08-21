# ระบบรายงานบัตรชั่ง (Weight Ticket Reports)

## ภาพรวม
ระบบรายงานบัตรชั่งประกอบด้วย 2 ประเภท:
1. **รายงานแบบชั่งแยก** (Separate Weighing) - ขนาด A5
2. **รายงานแบบชั่งรวม** (Combined Weighing) - ขนาด A4

## การติดตั้ง

### 1. ติดตั้ง Dependencies
```bash
pip install -r requirements.txt
```

### 2. ติดตั้ง Font ภาษาไทย (Optional)
หากต้องการใช้ font ภาษาไทย ให้ดาวน์โหลดไฟล์ `THSarabun.ttf` และวางไว้ในโฟลเดอร์ `backend/`

## API Endpoints

### 1. ตรวจสอบประเภทรายงาน
```
GET /api/reports/{ticket_id}/type
```
**Response:**
```json
{
  "ticket_id": "Z180821007",
  "report_type": "separate" // หรือ "combined"
}
```

### 2. สร้างรายงานแบบชั่งแยก
```
GET /api/reports/{ticket_id}/separate
```
**Response:** PDF file (A5 size)

### 3. สร้างรายงานแบบชั่งรวม
```
GET /api/reports/{ticket_id}/combined
```
**Response:** PDF file (A4 size)

### 4. สร้างรายงานอัตโนมัติ (แนะนำ)
```
GET /api/reports/{ticket_id}/auto
```
**Response:** PDF file (เลือกขนาดตามประเภทข้อมูล)

## โครงสร้างไฟล์

```
backend/
├── pdf_generator.py      # PDF Generator Class
├── report_service.py     # Report Service
├── main.py              # FastAPI endpoints
├── models.py            # Database models
├── schemas.py           # Pydantic schemas
└── requirements.txt     # Dependencies
```

## การใช้งาน

### 1. ผ่าน Frontend
- เลือกบัตรชั่งที่ต้องการ
- คลิกปุ่ม "พิมพ์รายงาน"
- ระบบจะดาวน์โหลดไฟล์ PDF อัตโนมัติ

### 2. ผ่าน API โดยตรง
```bash
# ตรวจสอบประเภทรายงาน
curl http://localhost:8000/api/reports/Z180821007/type

# สร้างรายงานอัตโนมัติ
curl -o report.pdf http://localhost:8000/api/reports/Z180821007/auto
```

## รายละเอียดรายงาน

### รายงานแบบชั่งแยก (A5)
- **ข้อมูลหลัก:** เลขที่บัตรชั่ง, เลขที่ใบจ่าย, ลูกค้า, สินค้า, จำนวน
- **ข้อมูลรถ:** ทะเบียนรถ, คนขับรถ, ประเภทรถ
- **ข้อมูลน้ำหนัก:** น้ำหนักเข้า, น้ำหนักออก, น้ำหนักสุทธิ
- **ส่วนท้าย:** หมายเหตุและลายเซ็น

### รายงานแบบชั่งรวม (A4)
- **ครึ่งบน:** เหมือนรายงานแบบชั่งแยก
- **ครึ่งล่าง:** ตารางรายการสินค้าในชั่งรวม
- **ข้อมูลรายการ:** ลำดับ, เลขที่เอกสาร, รายการ, รหัสสินค้า, ชื่อสินค้า, จำนวน, หน่วย

## การกำหนดประเภทรายงาน

ระบบจะตรวจสอบประเภทรายงานโดยดูจาก:
- **ชั่งแยก:** บัตรชั่งที่ไม่มีรายการใน `TBL_WEIGHT_ITEM`
- **ชั่งรวม:** บัตรชั่งที่มีรายการใน `TBL_WEIGHT_ITEM`

## การแก้ไขปัญหา

### 1. Font ภาษาไทยไม่แสดง
- ตรวจสอบว่าไฟล์ `THSarabun.ttf` อยู่ในโฟลเดอร์ที่ถูกต้อง
- หรือระบบจะใช้ font มาตรฐานแทน

### 2. PDF ไม่สร้าง
- ตรวจสอบ log ของ FastAPI
- ตรวจสอบว่าข้อมูลบัตรชั่งมีครบถ้วน

### 3. รายงานไม่ถูกต้อง
- ตรวจสอบข้อมูลในฐานข้อมูล
- ตรวจสอบการเชื่อมต่อฐานข้อมูล

## การปรับแต่ง

### 1. เปลี่ยน Font
แก้ไขใน `pdf_generator.py`:
```python
def setup_thai_font(self):
    # เปลี่ยนเป็น font อื่น
    pdfmetrics.registerFont(TTFont('YourFont', 'your-font.ttf'))
    self.thai_font = 'YourFont'
```

### 2. เปลี่ยนขนาดกระดาษ
แก้ไขใน `pdf_generator.py`:
```python
# สำหรับ A4
doc = SimpleDocTemplate(buffer, pagesize=A4)

# สำหรับ A5
doc = SimpleDocTemplate(buffer, pagesize=A5)
```

### 3. เปลี่ยนรูปแบบตาราง
แก้ไขใน `pdf_generator.py` ในฟังก์ชัน `_create_main_info()` และ `_create_weight_table()`

## หมายเหตุ
- ระบบใช้ ReportLab สำหรับสร้าง PDF
- รองรับภาษาไทย (ต้องมี font ที่เหมาะสม)
- รายงานจะถูกสร้างแบบ real-time จากข้อมูลในฐานข้อมูล
