import serial
import time

# --- Configuration (ปรับค่าเหล่านี้ให้ตรงกับเครื่องชั่งของคุณ) ---
SERIAL_PORT = "COM3"  # เช่น "COM1", "COM3", "/dev/ttyUSB0" บน Linux
BAUD_RATE = 9600      # เช่น 9600, 19200, 115200
PARITY = serial.PARITY_NONE # serial.PARITY_EVEN, serial.PARITY_ODD
STOP_BITS = serial.STOPBITS_ONE # serial.STOPBITS_TWO
BYTE_SIZE = serial.EIGHTBITS # serial.SEVENBITS
READ_TIMEOUT = 2  # วินาที, เวลาที่รออ่านข้อมูลก่อนจะ timeout

def parse_scale_data(raw_data_str):
    """
    ฟังก์ชันสำหรับ Parse ข้อมูลดิบที่ได้จากเครื่องชั่ง
    คุณจะต้องปรับแก้ส่วนนี้ให้เหมาะสมกับรูปแบบข้อมูลของเครื่องชั่งของคุณ
    """
    cleaned_data = raw_data_str # เริ่มต้นด้วยข้อมูลดิบ

    # --- ตัวอย่างการ Parse (สมมติฐาน) ---
    # 1. ถ้าข้อมูลมาพร้อมหน่วย "kg" และมีอักขระนำหน้า/ตามหลังที่ไม่ต้องการ:
    #    เช่น "ST,GS,+00123.45kg\r\n"
    if "kg" in raw_data_str.lower(): # ทำให้เป็นตัวพิมพ์เล็กก่อนเทียบ
        try:
            # พยายามหาตัวเลขที่มีจุดทศนิยม
            import re
            match = re.search(r"([+-]?\d+\.?\d*)", raw_data_str)
            if match:
                cleaned_data = match.group(1)
            else:
                # ถ้าไม่เจอแบบมีทศนิยม ลองหาแค่ตัวเลข
                match_int = re.search(r"([+-]?\d+)", raw_data_str)
                if match_int:
                    cleaned_data = match_int.group(1)
                else:
                    cleaned_data = "Parse Error: No number found"

        except Exception as e:
            cleaned_data = f"Parse Error: {e}"

    # 2. ถ้าข้อมูลเป็นตัวเลขล้วนๆ แต่อาจมี whitespace
    #    cleaned_data = raw_data_str.strip()

    # 3. ถ้าข้อมูลมีรูปแบบเฉพาะเจาะจงมาก อาจจะต้องใช้ string split, slicing หรือ regular expressions ที่ซับซ้อนกว่านี้

    return cleaned_data

def read_from_scale():
    try:
        print(f"Attempting to connect to {SERIAL_PORT} at {BAUD_RATE} baud...")
        ser = serial.Serial(
            port=SERIAL_PORT,
            baudrate=BAUD_RATE,
            parity=PARITY,
            stopbits=STOP_BITS,
            bytesize=BYTE_SIZE,
            timeout=READ_TIMEOUT
        )

        if ser.is_open:
            print(f"Successfully connected to {SERIAL_PORT}.")
            print("Reading data... (Press Ctrl+C to stop)")
            print("-" * 30)

            while True:
                try:
                    # อ่านข้อมูล 1 บรรทัด (จบด้วย newline \n)
                    # หรือถ้าเครื่องชั่งไม่ได้ส่ง newline อาจจะต้องใช้ ser.read(number_of_bytes)
                    raw_line = ser.readline()

                    if raw_line:
                        # แปลง bytes เป็น string (ลอง 'ascii', 'utf-8', หรือ encoding อื่นๆ ที่เครื่องชั่งใช้)
                        try:
                            decoded_line = raw_line.decode('ascii').strip()
                        except UnicodeDecodeError:
                            try:
                                decoded_line = raw_line.decode('utf-8').strip()
                            except UnicodeDecodeError:
                                decoded_line = f"Decode Error: {raw_line}"


                        print(f"Raw Data    : '{decoded_line}'")

                        parsed_value = parse_scale_data(decoded_line)
                        print(f"Parsed Value: '{parsed_value}'")
                        print("-" * 30)
                    else:
                        # Timeout เกิดขึ้น, ไม่ได้รับข้อมูล
                        print(f"Timeout waiting for data from {SERIAL_PORT}. No data received.")

                    # อาจจะใส่ time.sleep(0.1) เล็กน้อยถ้าต้องการอ่านเป็นช่วงๆ
                    # หรือถ้าเครื่องชั่งส่งข้อมูลต่อเนื่องก็ไม่ต้อง sleep

                except serial.SerialException as se:
                    print(f"Serial communication error: {se}")
                    break # ออกจาก loop ถ้ามีปัญหาการสื่อสาร
                except KeyboardInterrupt:
                    print("\nStopping data reading.")
                    break
                except Exception as e_read:
                    print(f"Error during reading: {e_read}")
                    time.sleep(1) # รอสักครู่แล้วลองใหม่

        else:
            print(f"Could not open serial port {SERIAL_PORT}.")

    except serial.SerialException as e:
        print(f"Error: Could not connect to serial port {SERIAL_PORT}. {e}")
    except Exception as e_main:
        print(f"An unexpected error occurred: {e_main}")
    finally:
        if 'ser' in locals() and ser.is_open:
            ser.close()
            print(f"Serial port {SERIAL_PORT} closed.")

if __name__ == "__main__":
    read_from_scale()