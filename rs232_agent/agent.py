# agent_websocket.py
import asyncio
import websockets
import json
import serial
import time
import random
import configparser
import os
import re
from threading import Thread

# --- Default Serial Configuration (เหมือนเดิม) ---
DEFAULT_AGENT_SERIAL_PORT = "COM1"
DEFAULT_AGENT_BAUD_RATE = 1200
DEFAULT_AGENT_PARITY_KEY = "N"
DEFAULT_AGENT_STOP_BITS_KEY = "1"
DEFAULT_AGENT_BYTE_SIZE_KEY = "8"
DEFAULT_AGENT_READ_TIMEOUT = 0.05
CONFIG_FILE_NAME = "scale_config.ini"

# --- Helper Dictionaries (เหมือนเดิม) ---
parity_map_agent = {
    "N": serial.PARITY_NONE, "E": serial.PARITY_EVEN, "O": serial.PARITY_ODD,
    "M": serial.PARITY_MARK, "S": serial.PARITY_SPACE
}
stop_bits_map_agent = {
    "1": serial.STOPBITS_ONE, "1.5": serial.STOPBITS_ONE_POINT_FIVE,
    "2": serial.STOPBITS_TWO
}
byte_size_map_agent = {
    "8": serial.EIGHTBITS, "7": serial.SEVENBITS, "6": serial.SIXBITS,
    "5": serial.FIVEBITS
}

# --- Global variables (ปรับปรุงเล็กน้อย) ---
current_serial_config = {}
serial_connection = None
agent_read_buffer = b''
AGENT_STX = b'\x02'
AGENT_ETX = b'\x03'
last_known_weight = "0"  # เริ่มต้นที่ 0
SIMULATION_MODE = False  # ตัวแปรใหม่สำหรับควบคุมโหมดจำลอง
FORCE_SIMULATION_MODE = True

# --- ส่วนที่เพิ่มเข้ามาสำหรับ WebSocket ---
CONNECTED_CLIENTS = set()

async def register_client(websocket):
    """เพิ่ม client ใหม่เมื่อมีการเชื่อมต่อ"""
    CONNECTED_CLIENTS.add(websocket)
    print(f"Client connected: {websocket.remote_address}. Total clients: {len(CONNECTED_CLIENTS)}")
    try:
        await websocket.wait_closed()
    finally:
        CONNECTED_CLIENTS.remove(websocket)
        print(f"Client disconnected: {websocket.remote_address}. Total clients: {len(CONNECTED_CLIENTS)}")

async def broadcast_weight(weight_data):
    """ส่งข้อมูลน้ำหนักไปยัง Client ทุกคนที่เชื่อมต่ออยู่"""
    if CONNECTED_CLIENTS:
        message = json.dumps({"weight": str(weight_data)})
        # สร้าง task สำหรับส่งข้อมูลให้ client แต่ละคนพร้อมๆ กัน
        await asyncio.gather(
            *[client.send(message) for client in CONNECTED_CLIENTS]
        )

# --- Function to load configuration (เหมือนเดิม) ---
def load_agent_config():
    global current_serial_config
    # ... (โค้ดส่วนนี้เหมือนเดิมทุกประการ) ...
    config = configparser.ConfigParser()
    loaded_settings = {
        'port': DEFAULT_AGENT_SERIAL_PORT,
        'baudrate': DEFAULT_AGENT_BAUD_RATE,
        'parity_key': DEFAULT_AGENT_PARITY_KEY,
        'stopbits_key': DEFAULT_AGENT_STOP_BITS_KEY,
        'bytesize_key': DEFAULT_AGENT_BYTE_SIZE_KEY,
        'timeout': DEFAULT_AGENT_READ_TIMEOUT
    }
    if os.path.exists(CONFIG_FILE_NAME):
        try:
            config.read(CONFIG_FILE_NAME)
            if 'SerialConfig' in config:
                cfg_section = config['SerialConfig']
                loaded_settings['port'] = cfg_section.get('Port', DEFAULT_AGENT_SERIAL_PORT)
                loaded_settings['baudrate'] = cfg_section.getint('BaudRate', DEFAULT_AGENT_BAUD_RATE)
                loaded_settings['parity_key'] = cfg_section.get('Parity', DEFAULT_AGENT_PARITY_KEY).upper()
                loaded_settings['stopbits_key'] = cfg_section.get('StopBits', DEFAULT_AGENT_STOP_BITS_KEY)
                loaded_settings['bytesize_key'] = cfg_section.get('ByteSize', DEFAULT_AGENT_BYTE_SIZE_KEY)
                loaded_settings['timeout'] = cfg_section.getfloat('ReadTimeout', DEFAULT_AGENT_READ_TIMEOUT)
                print(f"Agent: Loaded configuration from {CONFIG_FILE_NAME}")
        except Exception as e:
            print(f"Agent: Error loading config file {CONFIG_FILE_NAME}: {e}. Using default settings.")
    else:
        print(f"Agent: Config file {CONFIG_FILE_NAME} not found. Using default settings.")
    current_serial_config = {
        'port': loaded_settings['port'],
        'baudrate': loaded_settings['baudrate'],
        'parity': parity_map_agent.get(loaded_settings['parity_key'], serial.PARITY_NONE),
        'stopbits': stop_bits_map_agent.get(loaded_settings['stopbits_key'], serial.STOPBITS_ONE),
        'bytesize': byte_size_map_agent.get(loaded_settings['bytesize_key'], serial.EIGHTBITS),
        'timeout': loaded_settings['timeout']
    }
    print(f"Agent: Effective serial settings: {current_serial_config}")


# --- Parser function (เหมือนเดิม) ---
def agent_parse_scale_data(cleaned_text):
    # ... (โค้ดส่วนนี้เหมือนเดิมทุกประการ) ...
    known_weight_indicators_config = [
        ("1CH", r"1CH\s+(0{3,})", True), (" H ", r"\sH\s+(0{3,})", True),
        ("1Rh", r"1Rh\s+(0{3,})", True), ("1BH", r"1BH\s+(\d+)", False),
        ("1@H", r"1@H\s+(\d+)", False),
    ]
    extracted_weight_values = []
    for indicator_text, pattern_regex, is_zero_indicator in known_weight_indicators_config:
        matches = re.findall(pattern_regex, cleaned_text)
        if matches:
            for num_str_from_match in matches:
                if is_zero_indicator:
                    extracted_weight_values.append("0")
                else:
                    try:
                        weight_val = str(int(num_str_from_match))
                        extracted_weight_values.append(weight_val)
                    except ValueError:
                        pass
    if extracted_weight_values:
        non_zero_values = [val for val in extracted_weight_values if val != "0"]
        if non_zero_values:
            return non_zero_values[-1]
        elif "0" in extracted_weight_values:
            return "0"
    return "N/A"

# --- Function to manage serial connection (ปรับปรุงเล็กน้อย) ---
def get_serial_connection():
    global serial_connection, SIMULATION_MODE
    if serial_connection and serial_connection.is_open:
        return serial_connection
    try:
        print(f"Agent: Attempting to open serial port {current_serial_config['port']}")
        serial_connection = serial.Serial(**current_serial_config)
        if serial_connection.is_open:
            print(f"Agent: Serial port {current_serial_config['port']} opened successfully. LIVE MODE ACTIVATED.")
            SIMULATION_MODE = False
            return serial_connection
    except serial.SerialException as e:
        print(f"Agent: Error opening serial port: {e}")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print("!! AGENT: COULD NOT CONNECT TO RS232 PORT.            !!")
        print("!! RUNNING IN SIMULATION MODE.                        !!")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        SIMULATION_MODE = True
        serial_connection = None
    return None

# --- Function to read from RS232 (ปรับปรุงเล็กน้อย) ---
def read_weight_from_rs232_agent():
    global agent_read_buffer, last_known_weight
    ser = get_serial_connection() # พยายามเชื่อมต่อก่อน
    if not ser: # ถ้าเชื่อมต่อไม่ได้ ก็ไม่ต้องทำอะไร เพราะเราจะใช้ SIMULATION_MODE แทน
        return last_known_weight

    try:
        if ser.in_waiting > 0:
            new_bytes = ser.read(ser.in_waiting)
            agent_read_buffer += new_bytes
        
        while True:
            stx_index = agent_read_buffer.find(AGENT_STX)
            if stx_index != -1:
                etx_index = agent_read_buffer.find(AGENT_ETX, stx_index + 1)
                if etx_index != -1:
                    complete_message_bytes = agent_read_buffer[stx_index + 1: etx_index]
                    try:
                        decoded_message = complete_message_bytes.decode('latin-1').strip()
                        parsed_value = agent_parse_scale_data(decoded_message)
                        if parsed_value != "N/A":
                            last_known_weight = parsed_value
                    except Exception as e:
                        print(f"Agent: Decode/Parse error: {e}")
                    agent_read_buffer = agent_read_buffer[etx_index + 1:]
                else: break
            else: break
        
        return last_known_weight
    except Exception as e:
        print(f"Agent: Serial read error: {e}")
        last_known_weight = "Error"
        return last_known_weight

# --- ฟังก์ชันใหม่สำหรับสร้างข้อมูลจำลอง ---
def simulate_weight():
    global last_known_weight
    MAX_WEIGHT = 50500

    try:
        # แปลงน้ำหนักล่าสุดเป็นตัวเลข ถ้าแปลงไม่ได้ ให้เริ่มที่ 0
        current_weight = int(last_known_weight)
    except (ValueError, TypeError):
        current_weight = 0

    # 5% ที่จะเกิดการเปลี่ยนแปลงครั้งใหญ่ (รถขึ้น/ลงจากตาชั่ง)
    if random.random() < 0.05:
        # สุ่มน้ำหนักใหม่ทั้งหมด โดยสุ่มค่าที่หาร 10 ลงตัว
        # random.randrange(start, stop, step)
        new_weight = random.randrange(0, MAX_WEIGHT + 1, 10)
    else:
        # 95% ที่จะเกิดการเปลี่ยนแปลงเล็กน้อย
        # สุ่มค่าการเปลี่ยนแปลงที่ลงท้ายด้วย 0 (เช่น -50, -40, ..., 40, 50)
        change = random.randint(-5, 5) * 10
        new_weight = current_weight + change

    # --- บังคับใช้กฎ ---
    # 1. ตรวจสอบว่าน้ำหนักไม่ต่ำกว่า 0 และไม่เกิน MAX_WEIGHT
    new_weight = max(0, min(new_weight, MAX_WEIGHT))

    # 2. (เพื่อความแน่นอน) ทำให้ผลลัพธ์สุดท้ายลงท้ายด้วย 0 เสมอ
    # โดยการหารด้วย 10 แล้วปัดเศษทิ้ง จากนั้นคูณกลับด้วย 10
    final_weight = (new_weight // 10) * 10

    # อัปเดตค่าล่าสุดและส่งค่ากลับไป
    last_known_weight = str(final_weight)
    return last_known_weight

# --- โลจิกหลักที่ทำงานใน Background Thread ---
def weight_producer_loop():
    """
    Loop หลักที่จะทำงานตลอดเวลาเพื่อดึงค่าน้ำหนัก (จากของจริงหรือจำลอง)
    แล้วส่งไปให้ WebSocket Server
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def producer():
        while True:
            # ตรวจสอบสวิตช์บังคับ หรือ โหมดจำลองอัตโนมัติ
            if FORCE_SIMULATION_MODE or SIMULATION_MODE:
                weight = simulate_weight()
            else:
                weight = read_weight_from_rs232_agent()
            
            # ส่งข้อมูลไปให้ broadcast function
            await broadcast_weight(weight)
            await asyncio.sleep(0.5) # หน่วงเวลาเล็กน้อย

    loop.run_until_complete(producer())


# --- Main execution ---
async def main():
    # โหลด Config และพยายามเชื่อมต่อ Serial Port ครั้งแรก
    load_agent_config()
    get_serial_connection() # ผลลัพธ์จะไปกำหนดค่า SIMULATION_MODE

    # เริ่ม Thread ที่จะดึงข้อมูลน้ำหนักอยู่เบื้องหลัง
    producer_thread = Thread(target=weight_producer_loop, daemon=True)
    producer_thread.start()

    # เริ่ม WebSocket server ที่จะรอรับการเชื่อมต่อจาก Client
    async with websockets.serve(register_client, "0.0.0.0", 8765):
        print("WebSocket Server started at ws://0.0.0.0:8765")
        await asyncio.Future()  # run forever

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Server stopped.")