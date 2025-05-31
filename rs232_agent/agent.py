from flask import Flask, jsonify
import time # สำหรับจำลองการหน่วงเวลา
import random # สำหรับจำลองข้อมูลน้ำหนัก
from flask_cors import CORS

# --- ส่วนจำลองการอ่านค่าจาก RS232 ---
# ในสถานการณ์จริง ส่วนนี้จะใช้ library 'serial'
# และต้องกำหนด COM port, baudrate ฯลฯ ให้ถูกต้อง
def read_simulated_weight():
    """จำลองการอ่านค่าน้ำหนัก"""
    # จำลองว่าการอ่านค่าใช้เวลาเล็กน้อย
    time.sleep(0.1)
    # จำลองค่าน้ำหนักเป็นตัวเลขทศนิยมระหว่าง 10.00 ถึง 100.00
    simulated_value = round(random.uniform(10.0, 100.0), 2)
    # เครื่องชั่งบางรุ่นอาจส่งข้อมูลมาพร้อมหน่วย หรืออักขระพิเศษ
    # เราจะจำลองว่าส่งมาเป็น string ตัวเลข
    return str(simulated_value)

def read_actual_weight_from_rs232(serial_port_name="COM1", baud_rate=9600, timeout_val=1): # เพิ่ม timeout_val
    """
    อ่านค่าน้ำหนักจริงจาก RS232
    **คำเตือน:** ส่วนนี้ต้องปรับแก้ COM port, baud_rate และวิธีการ parse data ให้ตรงกับเครื่องชั่งของคุณ
    """
    try:
        import serial # ย้าย import มาไว้ในนี้ เพื่อไม่ให้ error ถ้า pyserial ยังไม่ได้ติดตั้ง
        # ser = serial.Serial(serial_port_name, baud_rate, timeout=timeout_val) # Timeout สำหรับการอ่าน
        # หรือกำหนดค่าอื่นๆ เพิ่มเติมถ้าจำเป็น เช่น:
        ser = serial.Serial(
            port=serial_port_name,
            baudrate=baud_rate,
            parity=serial.PARITY_NONE, # ตัวอย่าง: N
            stopbits=serial.STOPBITS_ONE, # ตัวอย่าง: 1
            bytesize=serial.EIGHTBITS, # ตัวอย่าง: 8
            timeout=timeout_val
        )

        if not ser.is_open:
            ser.open() # โดยปกติ constructor จะเปิดให้แล้ว แต่เช็คอีกทีก็ดี

        # --- ส่วนสำคัญ: การอ่านและ parse ข้อมูล ---
        # วิธีการอ่านขึ้นอยู่กับว่าเครื่องชั่งส่งข้อมูลมาอย่างไร

        # ตัวอย่าง 1: เครื่องชั่งส่งข้อมูลมาทีละบรรทัด (จบด้วย newline)
        line = ser.readline().decode('ascii', errors='ignore').strip()
        # print(f"Raw data from scale: '{line}'") # สำหรับ debug

        # --- ส่วนการ Parse ข้อมูล (ต้องปรับให้เข้ากับเครื่องชั่งของคุณ) ---
        # ตัวอย่างการ parse ถ้าข้อมูลเป็น "ST,GS,+00123.45kg"
        # if line and "GS," in line:
        #     parts = line.split(',')
        #     if len(parts) > 1:
        #         weight_str = parts[-1] # สมมติว่าส่วนน้ำหนักอยู่ท้ายสุด
        #         weight_str = weight_str.replace("kg", "").replace("KG", "").strip()
        #         # อาจจะต้องมีการจัดการกับเครื่องหมาย + หรือ -
        #         try:
        #             # พยายามแปลงเป็น float ก่อนเพื่อให้แน่ใจว่าเป็นตัวเลข
        #             # แล้วค่อยแปลงกลับเป็น string ตามต้องการ
        #             weight_value = float(weight_str)
        #             cleaned_line = f"{weight_value:.2f}" # จัดรูปแบบทศนิยม 2 ตำแหน่ง
        #         except ValueError:
        #             cleaned_line = "Invalid Data"
        #     else:
        #         cleaned_line = "Parse Error"
        # else:
        #     cleaned_line = "No Data" # หรือ "Waiting..."

        # **กรณีง่ายสุด: ถ้าเครื่องชั่งส่งเฉพาะตัวเลขน้ำหนัก**
        # cleaned_line = line # ถ้า line คือตัวเลขน้ำหนักเลย

        # **สำคัญ: แทนที่ส่วน parse นี้ด้วย logic ที่ถูกต้องสำหรับเครื่องชั่งของคุณ**
        # สำหรับการทดสอบเบื้องต้น อาจจะคืนค่า raw line ไปก่อนก็ได้
        cleaned_line = line if line else "N/A"


        ser.close()
        return cleaned_line
    except serial.SerialException as e:
        error_msg = f"Serial Port Error ({serial_port_name}): {e}"
        print(error_msg)
        return f"Error: {error_msg}" # คืนค่า error ที่สื่อความหมายมากขึ้น
    except Exception as e:
        error_msg = f"Unexpected Error: {e}"
        print(error_msg)
        return f"Error: {error_msg}"

def read_actual_weight_from_rs232xxx(serial_port_name="COM3", baud_rate=9600):
    """
    อ่านค่าน้ำหนักจริงจาก RS232 (ส่วนนี้ยังไม่ได้ใช้งานในตัวอย่างเริ่มต้น)
    **คำเตือน:** ส่วนนี้ต้องปรับแก้ COM port, baud_rate และวิธีการ parse data ให้ตรงกับเครื่องชั่งของคุณ
    """
    try:
        import serial # ย้าย import มาไว้ในนี้ เพื่อไม่ให้ error ถ้า pyserial ยังไม่ได้ติดตั้ง
        ser = serial.Serial(serial_port_name, baud_rate, timeout=1)
        if not ser.is_open:
            ser.open()

        # อ่านข้อมูล 1 บรรทัด (หรือตามรูปแบบข้อมูลของเครื่องชั่ง)
        # เครื่องชั่งส่วนใหญ่มักจะส่งข้อมูลมาเรื่อยๆ หรือส่งเมื่อมีการร้องขอ
        # หรือส่งเมื่อน้ำหนักนิ่ง
        # ตัวอย่างนี้เป็นการอ่านแบบง่ายๆ
        line = ser.readline().decode('ascii', errors='ignore').strip()

        # อาจจะต้องมีการ parse ข้อมูลที่ได้จาก line อีกที
        # เช่น ตัดอักขระที่ไม่ต้องการออก, แปลงเป็นตัวเลข
        # ตัวอย่าง: "ST,GS, 0.123kg\r\n" -> "0.123"
        # cleaned_line = line.split(',')[-1].replace('kg', '').strip() if line else "0.0"

        ser.close()
        return line if line else "N/A" # คืนค่าที่อ่านได้ หรือ "N/A" ถ้าไม่มีข้อมูล
    except serial.SerialException as e:
        print(f"Error opening/reading serial port {serial_port_name}: {e}")
        return f"Error: {e}"
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return "Error reading"

# --- สร้าง Flask App ---
app = Flask(__name__)
CORS(app)

@app.route('/get_weight', methods=['GET'])
def get_weight_endpoint():
    # --- เลือกใช้ฟังก์ชันอ่านค่า ---
    # 1. สำหรับทดสอบด้วยข้อมูลจำลอง:
    weight_data = read_simulated_weight()

    # 2. สำหรับเชื่อมต่อเครื่องชั่งจริง (เมื่อพร้อม):
    #    **ต้องยกเลิก comment บรรทัดล่าง และ comment บรรทัด read_simulated_weight() ข้างบน**
    #    **และตรวจสอบการตั้งค่า COM port, baud rate ให้ถูกต้อง**
    #    **และอาจจะต้องติดตั้ง pyserial เพิ่ม: pip install pyserial**
    # weight_data = read_actual_weight_from_rs232(serial_port_name="COM3", baud_rate=9600)

    return jsonify({"weight": weight_data})

if __name__ == '__main__':
    print("RS232 Agent is running...")
    print("Open your browser and go to http://127.0.0.1:5000/get_weight")
    # ใช้ host='0.0.0.0' เพื่อให้เข้าถึงได้จากเครื่องอื่นในเครือข่ายเดียวกัน
    # ถ้าใช้แค่ภายในเครื่องตัวเอง 127.0.0.1 ก็พอ
    app.run(host='0.0.0.0', port=5000, debug=True)