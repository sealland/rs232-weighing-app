# การแก้ไขปัญหาน้ำหนักค้างหลังจาก WebSocket Reconnect

## 🐛 ปัญหาที่พบ

เมื่อ WebSocket connection หลุดและ reconnect แล้ว น้ำหนักจะค้างที่ 0 หรือค่าสุดท้ายที่ส่งไป

## 🔧 การแก้ไข

### 1. การล้าง Buffer เก่าเมื่อ Reconnect

เพิ่มการล้าง buffer เก่าเมื่อ reconnect เพื่อไม่ให้ส่งข้อมูลเก่า:

```python
# ล้าง buffer เก่าเมื่อ reconnect เพื่อไม่ให้ส่งข้อมูลเก่า
if len(self.read_buffer) > 0:
    self.log_message("Clearing old buffer after reconnect")
    self.read_buffer = b''
```

### 2. การตรวจสอบน้ำหนัก 0

เพิ่มการตรวจสอบน้ำหนัก 0 และไม่ส่งซ้ำ:

```python
# ตรวจสอบว่าน้ำหนักเป็น 0 หรือไม่ และไม่ส่งซ้ำ
if weight == "0" or weight == "0.0":
    # ถ้าน้ำหนักเป็น 0 ให้รอข้อมูลใหม่
    await asyncio.sleep(0.5)
    continue
```

### 3. การปรับปรุงการประมวลผลข้อมูลใหม่

ปรับปรุงการประมวลผลข้อมูลใหม่เพื่อไม่ให้ส่งข้อมูลเก่าที่เป็น 0:

```python
# ตรวจสอบข้อมูลใหม่
for line in lines:
    line = line.strip()
    if line:
        try:
            parsed_value = self.parse_scale_data(line)
            if parsed_value != "N/A":
                # ตรวจสอบว่าน้ำหนักเป็น 0 หรือไม่
                if parsed_value != "0" and parsed_value != "0.0":
                    self.last_weight = parsed_value
                    self.weight_label.config(text=f"⚖️ Weight: {parsed_value}")
                    self.log_message(f"New weight from buffer: {parsed_value}")
        except Exception as e:
            continue
```

### 4. การปรับปรุงการจัดการ Buffer

- **ล้าง buffer เก่า** เมื่อ reconnect
- **ไม่ส่งน้ำหนัก 0** ซ้ำๆ
- **ตรวจสอบข้อมูลใหม่** ก่อนอัปเดตน้ำหนัก

## 📊 ผลลัพธ์

หลังจากแก้ไขแล้ว:

1. **ไม่มีการส่งข้อมูลเก่า** - ล้าง buffer เมื่อ reconnect
2. **ไม่ส่งน้ำหนัก 0 ซ้ำ** - รอข้อมูลใหม่แทน
3. **น้ำหนักอัปเดตถูกต้อง** - หลังจาก reconnect
4. **การทำงานเสถียร** - ไม่ค้างอีกต่อไป

## 🔍 การตรวจสอบ

ตรวจสอบ log เพื่อดูการทำงาน:

- `"Clearing old buffer after reconnect"` - ล้าง buffer เก่า
- `"New weight from buffer: X.X"` - น้ำหนักใหม่จาก buffer
- `"New weight from timeout read: X.X"` - น้ำหนักใหม่จาก timeout read
- `"Updated weight after buffer trim: X.X"` - น้ำหนักอัปเดตหลัง trim

## 💡 ข้อแนะนำ

1. **ตรวจสอบ WebSocket URL** - ให้ถูกต้อง
2. **ปรับ timeout** - ตามความต้องการ
3. **ตรวจสอบ sensitivity** - ให้เหมาะสม
4. **ตรวจสอบ pattern** - ให้ตรงกับข้อมูล

## 🚨 หมายเหตุ

- การล้าง buffer อาจทำให้สูญเสียข้อมูลบางส่วน แต่จะป้องกันการส่งข้อมูลเก่า
- น้ำหนัก 0 จะไม่ถูกส่งซ้ำ เพื่อลดการรบกวน
- ข้อมูลใหม่จะถูกประมวลผลทันทีเมื่อได้รับ
