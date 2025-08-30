# ฟีเจอร์ใหม่ใน RS232 Scale Client

## 🆕 ฟีเจอร์ที่เพิ่มใหม่

### 1. การตั้งค่าความไวในการอ่านน้ำหนัก (Sensitivity)
- **เพิ่มฟิลด์ Sensitivity (kg)** ในส่วน Serial Port Configuration
- **ค่าเริ่มต้น**: 0.1 kg
- **การทำงาน**: กรองข้อมูลน้ำหนักที่น้อยกว่าค่าความไวออกไป
- **ประโยชน์**: ลดการอ่านข้อมูลรบกวนจากตาชั่ง

### 2. การตรวจสอบไฟล์ Config ในหลาย Path
- **ตรวจสอบไฟล์ config ใน**:
  - โฟลเดอร์ปัจจุบัน
  - โฟลเดอร์โปรแกรม (executable)
  - โฟลเดอร์ script
- **การบันทึก**: บันทึกไฟล์ config ในโฟลเดอร์โปรแกรม
- **การโหลด**: โหลดไฟล์ config จาก path แรกที่พบ

### 3. ปุ่มซ่อนโปรแกรมลงใน System Tray
- **ปุ่ม "📌 Hide to Tray"**: ซ่อนโปรแกรมลงใน system tray
- **เมนู Tray**: คลิกขวาที่ tray icon เพื่อดูเมนู
  - Show Window: แสดงหน้าต่างหลัก
  - Open Frontend: เปิดหน้าเว็บ Frontend
  - Start Client: เริ่มต้น client
  - Stop Client: หยุด client
  - Exit: ปิดโปรแกรม

### 4. ปุ่มเปิดหน้าเว็บ Frontend
- **ปุ่ม "🌐 OPEN FRONTEND"**: ใหญ่และชัดเจน
- **URL**: http://192.168.132.7:5173/ (สามารถแก้ไขได้ในโค้ด)
- **การทำงาน**: เปิดหน้าเว็บใน browser อัตโนมัติ

## 🔧 การตั้งค่าใหม่

### Sensitivity Configuration
```ini
[SerialConfig]
sensitivity = 0.1
```

### Custom Pattern 3 Configuration
```ini
[CustomPattern3Config]
prefix = CUSTOM3
regex = CUSTOM3\s+(\d+)
iszero = False
```

## 📦 Dependencies ใหม่

เพิ่ม dependencies ใหม่ใน `requirements.txt`:
```
Pillow==10.4.0
pystray==0.19.5
```

## 🚀 การติดตั้ง

1. **ติดตั้ง dependencies ใหม่**:
   ```bash
   pip install -r requirements.txt
   ```

2. **รันโปรแกรม**:
   ```bash
   python rs232_client_gui.py
   ```

## 💡 วิธีใช้งาน

### การตั้งค่าความไว
1. เปิดโปรแกรม RS232 Scale Client
2. ไปที่ส่วน "Serial Port Configuration"
3. ตั้งค่า "Sensitivity (kg)" ตามต้องการ
4. กดปุ่ม "Save" เพื่อบันทึก

### การซ่อนโปรแกรมลง Tray
1. กดปุ่ม "📌 Hide to Tray"
2. โปรแกรมจะซ่อนลงใน system tray
3. คลิกขวาที่ tray icon เพื่อดูเมนู

### การเปิดหน้าเว็บ Frontend
1. กดปุ่ม "🌐 OPEN FRONTEND"
2. หน้าเว็บจะเปิดใน browser อัตโนมัติ

## 🔍 การแก้ไขปัญหา

### ปัญหา Tray Icon
- ตรวจสอบว่าได้ติดตั้ง `pystray` แล้ว
- บางระบบอาจต้องรันเป็น Administrator

### ปัญหา Frontend URL
- แก้ไขค่า `FRONTEND_URL` ในโค้ด
- ตรวจสอบว่า frontend server กำลังทำงาน

### ปัญหา Config File
- ตรวจสอบสิทธิ์การเขียนในโฟลเดอร์โปรแกรม
- ลองรันเป็น Administrator

## 📝 หมายเหตุ

- ฟีเจอร์ใหม่ทั้งหมดจะทำงานร่วมกับฟีเจอร์เดิมได้ปกติ
- การตั้งค่าเดิมจะยังคงทำงานได้
- ไฟล์ config จะถูกบันทึกในโฟลเดอร์โปรแกรมเพื่อความสะดวก
