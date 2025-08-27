import asyncio
import websockets
import json
import serial
import time
import configparser
import os
import re
from threading import Thread

# Configuration
CLIENT_CONFIG_FILE = "client_config.ini"
SERVER_WEBSOCKET_URL = "ws://localhost:8765"
CLIENT_ID = "scale_001"  # ระบุตัวตนของเครื่องนี้

# Serial Configuration
DEFAULT_SERIAL_PORT = "COM1"
DEFAULT_BAUD_RATE = 1200
DEFAULT_PARITY = "N"
DEFAULT_STOP_BITS = "1"
DEFAULT_BYTE_SIZE = "8"
DEFAULT_READ_TIMEOUT = 0.05

# Helper mappings
parity_map = {
    "N": serial.PARITY_NONE, "E": serial.PARITY_EVEN, "O": serial.PARITY_ODD,
    "M": serial.PARITY_MARK, "S": serial.PARITY_SPACE
}
stop_bits_map = {
    "1": serial.STOPBITS_ONE, "1.5": serial.STOPBITS_ONE_POINT_FIVE,
    "2": serial.STOPBITS_TWO
}
byte_size_map = {
    "8": serial.EIGHTBITS, "7": serial.SEVENBITS, "6": serial.SIXBITS,
    "5": serial.FIVEBITS
}

class RS232Client:
    def __init__(self):
        self.serial_config = self.load_config()
        self.serial_connection = None
        self.read_buffer = b''
        self.STX = b'\x02'
        self.ETX = b'\x03'
        self.last_weight = "0"
        self.websocket = None
        
    def load_config(self):
        """โหลด config จากไฟล์ในเครื่อง client"""
        config = configparser.ConfigParser()
        loaded_settings = {
            'port': DEFAULT_SERIAL_PORT,
            'baudrate': DEFAULT_BAUD_RATE,
            'parity_key': DEFAULT_PARITY,
            'stopbits_key': DEFAULT_STOP_BITS,
            'bytesize_key': DEFAULT_BYTE_SIZE,
            'timeout': DEFAULT_READ_TIMEOUT
        }
        
        if os.path.exists(CLIENT_CONFIG_FILE):
            try:
                config.read(CLIENT_CONFIG_FILE)
                if 'SerialConfig' in config:
                    cfg_section = config['SerialConfig']
                    loaded_settings['port'] = cfg_section.get('Port', DEFAULT_SERIAL_PORT)
                    loaded_settings['baudrate'] = cfg_section.getint('BaudRate', DEFAULT_BAUD_RATE)
                    loaded_settings['parity_key'] = cfg_section.get('Parity', DEFAULT_PARITY).upper()
                    loaded_settings['stopbits_key'] = cfg_section.get('StopBits', DEFAULT_STOP_BITS)
                    loaded_settings['bytesize_key'] = cfg_section.get('ByteSize', DEFAULT_BYTE_SIZE)
                    loaded_settings['timeout'] = cfg_section.getfloat('ReadTimeout', DEFAULT_READ_TIMEOUT)
                    print(f"Client {CLIENT_ID}: Loaded configuration from {CLIENT_CONFIG_FILE}")
            except Exception as e:
                print(f"Client {CLIENT_ID}: Error loading config: {e}. Using defaults.")
        else:
            print(f"Client {CLIENT_ID}: Config file not found. Using defaults.")
            
        return {
            'port': loaded_settings['port'],
            'baudrate': loaded_settings['baudrate'],
            'parity': parity_map.get(loaded_settings['parity_key'], serial.PARITY_NONE),
            'stopbits': stop_bits_map.get(loaded_settings['stopbits_key'], serial.STOPBITS_ONE),
            'bytesize': byte_size_map.get(loaded_settings['bytesize_key'], serial.EIGHTBITS),
            'timeout': loaded_settings['timeout']
        }
    
    def get_serial_connection(self):
        """เชื่อมต่อ RS232"""
        if self.serial_connection and self.serial_connection.is_open:
            return self.serial_connection
            
        try:
            print(f"Client {CLIENT_ID}: Connecting to {self.serial_config['port']}")
            self.serial_connection = serial.Serial(**self.serial_config)
            if self.serial_connection.is_open:
                print(f"Client {CLIENT_ID}: Connected to {self.serial_config['port']}")
                return self.serial_connection
        except serial.SerialException as e:
            print(f"Client {CLIENT_ID}: Serial connection error: {e}")
            self.serial_connection = None
        return None
    
    def parse_scale_data(self, cleaned_text):
        """Parse ข้อมูลจาก scale"""
        known_weight_indicators = [
            ("1CH", r"1CH\s+(0{3,})", True), (" H ", r"\sH\s+(0{3,})", True),
            ("1Rh", r"1Rh\s+(0{3,})", True), ("1BH", r"1BH\s+(\d+)", False),
            ("1@H", r"1@H\s+(\d+)", False),
        ]
        
        extracted_weight_values = []
        for indicator_text, pattern_regex, is_zero_indicator in known_weight_indicators:
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
    
    def read_weight_from_rs232(self):
        """อ่านน้ำหนักจาก RS232"""
        ser = self.get_serial_connection()
        if not ser:
            return self.last_weight
            
        try:
            if ser.in_waiting > 0:
                new_bytes = ser.read(ser.in_waiting)
                self.read_buffer += new_bytes
            
            while True:
                stx_index = self.read_buffer.find(self.STX)
                if stx_index != -1:
                    etx_index = self.read_buffer.find(self.ETX, stx_index + 1)
                    if etx_index != -1:
                        complete_message_bytes = self.read_buffer[stx_index + 1: etx_index]
                        try:
                            decoded_message = complete_message_bytes.decode('latin-1').strip()
                            parsed_value = self.parse_scale_data(decoded_message)
                            if parsed_value != "N/A":
                                self.last_weight = parsed_value
                        except Exception as e:
                            print(f"Client {CLIENT_ID}: Parse error: {e}")
                        self.read_buffer = self.read_buffer[etx_index + 1:]
                    else:
                        break
                else:
                    break
            
            return self.last_weight
        except Exception as e:
            print(f"Client {CLIENT_ID}: Serial read error: {e}")
            return "Error"
    
    async def send_weight_to_server(self):
        """ส่งข้อมูลน้ำหนักไปยัง server"""
        while True:
            try:
                if self.websocket:
                    weight = self.read_weight_from_rs232()
                    message = {
                        "client_id": CLIENT_ID,
                        "weight": weight,
                        "timestamp": time.time()
                    }
                    await self.websocket.send(json.dumps(message))
                    print(f"Client {CLIENT_ID}: Sent weight {weight}")
                await asyncio.sleep(0.5)
            except Exception as e:
                print(f"Client {CLIENT_ID}: Error sending data: {e}")
                await asyncio.sleep(1)
    
    async def connect_to_server(self):
        """เชื่อมต่อไปยัง WebSocket server"""
        while True:
            try:
                print(f"Client {CLIENT_ID}: Connecting to server {SERVER_WEBSOCKET_URL}")
                async with websockets.connect(SERVER_WEBSOCKET_URL) as websocket:
                    self.websocket = websocket
                    print(f"Client {CLIENT_ID}: Connected to server")
                    
                    # ส่งข้อมูลน้ำหนักไปยัง server
                    await self.send_weight_to_server()
                    
            except Exception as e:
                print(f"Client {CLIENT_ID}: Connection error: {e}")
                self.websocket = None
                await asyncio.sleep(5)  # รอ 5 วินาทีก่อนเชื่อมต่อใหม่
    
    async def run(self):
        """เริ่มต้นการทำงานของ client"""
        await self.connect_to_server()

if __name__ == '__main__':
    client = RS232Client()
    try:
        asyncio.run(client.run())
    except KeyboardInterrupt:
        print(f"Client {CLIENT_ID}: Stopped.")