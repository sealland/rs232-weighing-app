import asyncio
import websockets
import json
import serial
import time
import configparser
import os
import re
import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime
import serial.tools.list_ports
import webbrowser
import sys
from PIL import Image, ImageTk
import pystray
from pystray import MenuItem as item
# ลบ import ที่เกี่ยวข้องกับ Offline Mode ออกแล้ว

# Configuration
CLIENT_CONFIG_FILE = "client_config.ini"
SERVER_WEBSOCKET_URL = "ws://localhost:8765"
CLIENT_ID = "scale_001"
FRONTEND_URL = "http://192.168.132.7:5173/"  # URL สำหรับ Frontend

# Serial Configuration
DEFAULT_SERIAL_PORT = "COM1"
DEFAULT_BAUD_RATE = 9600  # เปลี่ยนจาก 1200 เป็น 9600 ตาม HyperTerminal
DEFAULT_PARITY = "E"      # เปลี่ยนจาก N เป็น E ตาม HyperTerminal
DEFAULT_STOP_BITS = "1"
DEFAULT_BYTE_SIZE = "7"   # เปลี่ยนจาก 8 เป็น 7 ตาม HyperTerminal
DEFAULT_READ_TIMEOUT = 1.0  # เพิ่มจาก 0.05 เป็น 1.0 วินาที
DEFAULT_SENSITIVITY = 0.1  # ความไวในการอ่านน้ำหนัก (kg)

# Branch Configuration
BRANCH_CONFIG = {
    'สาขา 1 (SPS)': 'Z4',
    'สาขา 2 (OPS)': 'Z2',
    'สาขา 3 (SPN)': 'Z5',
    'สำนักงานใหญ่ P8': 'Z1',
    'สำนักงานใหญ่ P3': 'Z3',
    'โอเชี่ยนไพพ์ (OCP)': 'Z6',
    'มาลีค้าเหล็ก(มาลี)': 'Z7',
    'สาขาลพบุรี': 'DYNAMIC'  # จะใช้ปี พ.ศ. 2 ตัวสุดท้าย
}


# Scale Pattern Configuration - รองรับหลายรุ่น/ยี่ห้อ
SCALE_PATTERNS = {
    'Raw Data (No Parse)': [
        ("RAW", r".*", False),  # รับข้อมูลทั้งหมดโดยไม่ parse
    ],
    'Default': [
        ("1CH", r"1CH\s+(0{3,})", True),
        (" H ", r"\sH\s+(0{3,})", True),
        ("1Rh", r"1Rh\s+(0{3,})", True),
        ("1BH", r"1BH\s+(\d+)", False),
        ("1@H", r"1@H\s+(\d+)", False),
    ],
    'CAS Scale': [
        ("CAS", r"CAS\s+(\d+)", False),
        ("CAS", r"CAS\s+(0{3,})", True),
        ("ST", r"ST\s+(\d+)", False),
        ("ST", r"ST\s+(0{3,})", True),
    ],
    'ST,GS Format': [
        ("ST,GS", r"(ST),GS,\+([0-9]+\.?[0-9]*)kg", False),  # น้ำหนัก Stable เช่น ST,GS,+123.4kg
        ("US,GS", r"(US),GS,\+([0-9]+\.?[0-9]*)kg", False),  # น้ำหนัก Unstable เช่น US,GS,+123.4kg
        ("ST,GS", r"(ST),GS,\+0{3,}\.?0*kg", True),          # น้ำหนัก 0 Stable เช่น ST,GS,+00000.0kg
        ("US,GS", r"(US),GS,\+0{3,}\.?0*kg", True),          # น้ำหนัก 0 Unstable เช่น US,GS,+00000.0kg
        # เพิ่ม pattern สำหรับข้อมูลที่อาจถูกตัดขาด
        ("ST,GS", r"(ST),GS,\+([0-9]+\.?[0-9]*)$", False),   # น้ำหนัก Stable ที่ถูกตัดขาด
        ("US,GS", r"(US),GS,\+([0-9]+\.?[0-9]*)$", False),   # น้ำหนัก Unstable ที่ถูกตัดขาด
        ("ST,GS", r"(ST),GS,\+0{3,}\.?0*$", True),           # น้ำหนัก 0 Stable ที่ถูกตัดขาด
        ("US,GS", r"(US),GS,\+0{3,}\.?0*$", True),           # น้ำหนัก 0 Unstable ที่ถูกตัดขาด
        # เพิ่ม pattern สำหรับค่าติดลบ
        ("ST,GS", r"(ST),GS,-([0-9]+\.?[0-9]*)kg", False),   # น้ำหนัก Stable ติดลบ เช่น ST,GS,-123.4kg
        ("US,GS", r"(US),GS,-([0-9]+\.?[0-9]*)kg", False),   # น้ำหนัก Unstable ติดลบ เช่น US,GS,-123.4kg
        ("ST,GS", r"(ST),GS,-0{3,}\.?0*kg", True),           # น้ำหนัก 0 Stable ติดลบ เช่น ST,GS,-00000.0kg
        ("US,GS", r"(US),GS,-0{3,}\.?0*kg", True),           # น้ำหนัก 0 Unstable ติดลบ เช่น US,GS,-00000.0kg
        # เพิ่ม pattern สำหรับค่าติดลบที่ถูกตัดขาด
        ("ST,GS", r"(ST),GS,-([0-9]+\.?[0-9]*)$", False),    # น้ำหนัก Stable ติดลบที่ถูกตัดขาด
        ("US,GS", r"(US),GS,-([0-9]+\.?[0-9]*)$", False),    # น้ำหนัก Unstable ติดลบที่ถูกตัดขาด
        ("ST,GS", r"(ST),GS,-0{3,}\.?0*$", True),            # น้ำหนัก 0 Stable ติดลบที่ถูกตัดขาด
        ("US,GS", r"(US),GS,-0{3,}\.?0*$", True),            # น้ำหนัก 0 Unstable ติดลบที่ถูกตัดขาด
        # เพิ่ม pattern สำหรับข้อมูลที่ถูกตัดขาดมาก
        ("ST,GS", r"(ST),GS,-$", True),                       # ST,GS,- (น้ำหนัก 0)
        ("US,GS", r"(US),GS,-$", True),                       # US,GS,- (น้ำหนัก 0)
    ],
    'Mettler Toledo': [
        ("MT", r"MT\s+(\d+)", False),
        ("MT", r"MT\s+(0{3,})", True),
        ("WT", r"WT\s+(\d+)", False),
        ("WT", r"WT\s+(0{3,})", True),
    ],
    'Sartorius': [
        ("SA", r"SA\s+(\d+)", False),
        ("SA", r"SA\s+(0{3,})", True),
        ("WE", r"WE\s+(\d+)", False),
        ("WE", r"WE\s+(0{3,})", True),
    ],
    'Custom Pattern 1': [
        ("CUSTOM1", r"CUSTOM1\s+(\d+)", False),
        ("CUSTOM1", r"CUSTOM1\s+(0{3,})", True),
    ],
    'Custom Pattern 2': [
        ("CUSTOM2", r"CUSTOM2\s+(\d+)", False),
        ("CUSTOM2", r"CUSTOM2\s+(0{3,})", True),
    ],
    'Custom Pattern 3': []  # จะถูกเติมด้วยข้อมูลจากผู้ใช้
}

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

class RS232ClientGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"RS232 Scale Client - {CLIENT_ID}")
        self.root.geometry("980x750") # ปรับขนาดหน้าต่างให้เหมาะสม
        self.root.configure(bg='#f0f0f0')
        
        # Client variables
        self.serial_config = self.load_config()
        self.serial_connection = None
        self.read_buffer = b''
        self.STX = b'\x02'
        self.ETX = b'\x03'
        self.last_weight = "0"
        self.websocket = None
        self.is_connected = False
        self.is_running = False
        self.loop = None
        
        # Tray variables
        self.tray_icon = None
        self.is_minimized_to_tray = False
        
        # Sensitivity variable
        self.sensitivity = DEFAULT_SENSITIVITY
        
        # GUI variables
        self.port_var = tk.StringVar(value=self.serial_config['port'])
        self.baudrate_var = tk.StringVar(value=str(self.serial_config['baudrate']))
        self.parity_var = tk.StringVar(value=self.get_parity_key())
        self.stopbits_var = tk.StringVar(value=self.get_stopbits_key())
        self.bytesize_var = tk.StringVar(value=self.get_bytesize_key())
        self.timeout_var = tk.StringVar(value=str(self.serial_config['timeout']))
        self.sensitivity_var = tk.StringVar(value=str(self.sensitivity))
        self.server_url_var = tk.StringVar(value=SERVER_WEBSOCKET_URL)
        self.client_id_var = tk.StringVar(value=CLIENT_ID)
        self.branch_var = tk.StringVar(value='สำนักงานใหญ่ P8')  # Default branch
        self.scale_pattern_var = tk.StringVar(value='Raw Data (No Parse)')  # เปลี่ยนเป็น Raw Data
        # Custom Pattern 3 variables
        self.custom_pattern_prefix_var = tk.StringVar(value="CUSTOM3")
        self.custom_pattern_regex_var = tk.StringVar(value=r"CUSTOM3\s+(\d+)")
        self.custom_pattern_is_zero_var = tk.BooleanVar(value=False)
        
        # สร้าง UI ก่อน
        self.setup_ui()
        self.update_available_ports()
        
        # โหลดค่า sensitivity จาก config
        self.sensitivity = self.serial_config.get('sensitivity', DEFAULT_SENSITIVITY)
        self.sensitivity_var.set(str(self.sensitivity))
        
        # โหลด config เพิ่มเติมหลังจากสร้าง GUI แล้ว
        self.load_additional_config()
        
        # Log current configuration for debugging หลังจากสร้าง UI แล้ว
        self.log_message(f"Default config: {self.serial_config['port']}, {self.serial_config['baudrate']}, {self.get_parity_key()}, {self.get_stopbits_key()}, {self.get_bytesize_key()}, Sensitivity: {self.sensitivity}")
        
        # ตรวจสอบสถานะ Serial port หลังจากเริ่มต้น
        self.root.after(1000, self.test_connection_status)  # ตรวจสอบหลังจาก 1 วินาที
        
    def setup_ui(self):
        """สร้าง UI"""
        # Main container
        main_frame = ttk.Frame(self.root, padding="8")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # Title
        title_label = ttk.Label(main_frame, text="RS232 Scale Client Configuration", 
                               font=('Tahoma', 14, 'bold'))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 15))
        
        # Left Panel - Configuration
        left_panel = ttk.Frame(main_frame)
        left_panel.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))
        left_panel.columnconfigure(1, weight=1)
        
        # Configuration Frame
        config_frame = ttk.LabelFrame(left_panel, text="Serial Port Configuration", padding="8")
        config_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 8))
        config_frame.columnconfigure(1, weight=1)
        
        # Port selection
        ttk.Label(config_frame, text="Port:", font=('Tahoma', 8)).grid(row=0, column=0, sticky=tk.W, padx=(0, 8))
        port_frame = ttk.Frame(config_frame)
        port_frame.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=3)
        
        self.port_combo = ttk.Combobox(port_frame, textvariable=self.port_var, width=12, font=('Tahoma', 8))
        self.port_combo.grid(row=0, column=0, padx=(0, 5))
        
        refresh_btn = ttk.Button(port_frame, text="🔄", width=3, command=self.update_available_ports)
        refresh_btn.grid(row=0, column=1, padx=(0, 5))
        
        check_btn = ttk.Button(port_frame, text="🔍", width=3, command=self.check_ports)
        check_btn.grid(row=0, column=2)
        
        # Baud rate
        ttk.Label(config_frame, text="Baud Rate:", font=('Tahoma', 8)).grid(row=1, column=0, sticky=tk.W, padx=(0, 8))
        baudrate_combo = ttk.Combobox(config_frame, textvariable=self.baudrate_var, 
                                     values=['1200', '2400', '4800', '9600', '19200', '38400', '57600', '115200'],
                                     width=12, font=('Tahoma', 8))
        baudrate_combo.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=3)
        baudrate_combo.set('9600')  # Set default to 9600
        
        # Parity
        ttk.Label(config_frame, text="Parity:", font=('Tahoma', 8)).grid(row=2, column=0, sticky=tk.W, padx=(0, 8))
        parity_combo = ttk.Combobox(config_frame, textvariable=self.parity_var, 
                                   values=['N', 'E', 'O', 'M', 'S'],
                                   width=12, font=('Tahoma', 8))
        parity_combo.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=3)
        parity_combo.set('E')  # Set default to E
        
        # Stop bits
        ttk.Label(config_frame, text="Stop Bits:", font=('Tahoma', 8)).grid(row=3, column=0, sticky=tk.W, padx=(0, 8))
        stopbits_combo = ttk.Combobox(config_frame, textvariable=self.stopbits_var, 
                                     values=['1', '1.5', '2'],
                                     width=12, font=('Tahoma', 8))
        stopbits_combo.grid(row=3, column=1, sticky=(tk.W, tk.E), pady=3)
        
        # Byte size
        ttk.Label(config_frame, text="Byte Size:", font=('Tahoma', 8)).grid(row=4, column=0, sticky=tk.W, padx=(0, 8))
        bytesize_combo = ttk.Combobox(config_frame, textvariable=self.bytesize_var, 
                                     values=['5', '6', '7', '8'],
                                     width=12, font=('Tahoma', 8))
        bytesize_combo.grid(row=4, column=1, sticky=(tk.W, tk.E), pady=3)
        bytesize_combo.set('7')  # Set default to 7
        
        # Timeout
        ttk.Label(config_frame, text="Timeout (sec):", font=('Tahoma', 8)).grid(row=5, column=0, sticky=tk.W, padx=(0, 8))
        timeout_entry = ttk.Entry(config_frame, textvariable=self.timeout_var, width=12, font=('Tahoma', 8))
        timeout_entry.grid(row=5, column=1, sticky=(tk.W, tk.E), pady=3)
        
        # Sensitivity
        ttk.Label(config_frame, text="Sensitivity (kg):", font=('Tahoma', 8)).grid(row=6, column=0, sticky=tk.W, padx=(0, 8))
        sensitivity_entry = ttk.Entry(config_frame, textvariable=self.sensitivity_var, width=12, font=('Tahoma', 8))
        sensitivity_entry.grid(row=6, column=1, sticky=(tk.W, tk.E), pady=3)
        
        # Scale Pattern Configuration Frame
        scale_frame = ttk.LabelFrame(left_panel, text="Scale Pattern Configuration", padding="8")
        scale_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 8))
        scale_frame.columnconfigure(1, weight=1)
        
        # Scale pattern selection
        ttk.Label(scale_frame, text="Scale Pattern:", font=('Tahoma', 8)).grid(row=0, column=0, sticky=tk.W, padx=(0, 8))
        scale_pattern_combo = ttk.Combobox(scale_frame, textvariable=self.scale_pattern_var, 
                                         values=list(SCALE_PATTERNS.keys()), width=20, font=('Tahoma', 8))
        scale_pattern_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=3)
        
        # Scale pattern info (ซ่อนไว้)
        self.scale_pattern_info_label = ttk.Label(scale_frame, text="", 
                                                 font=('Tahoma', 7), foreground='gray')
        self.scale_pattern_info_label.grid(row=1, column=0, columnspan=2, pady=(3, 0))
        
        # Bind scale pattern selection change
        scale_pattern_combo.bind('<<ComboboxSelected>>', self.on_scale_pattern_change)
        
        # Custom Pattern 3 Configuration Frame
        custom_frame = ttk.LabelFrame(left_panel, text="Custom Pattern 3 Configuration", padding="8")
        custom_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 8))
        custom_frame.columnconfigure(1, weight=1)
        
        # Custom Pattern Prefix
        ttk.Label(custom_frame, text="Pattern Prefix:", font=('Tahoma', 8)).grid(row=0, column=0, sticky=tk.W, padx=(0, 8))
        custom_prefix_entry = ttk.Entry(custom_frame, textvariable=self.custom_pattern_prefix_var, width=15, font=('Tahoma', 8))
        custom_prefix_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=3)
        
        # Custom Pattern Regex
        ttk.Label(custom_frame, text="Regex Pattern:", font=('Tahoma', 8)).grid(row=1, column=0, sticky=tk.W, padx=(0, 8))
        custom_regex_entry = ttk.Entry(custom_frame, textvariable=self.custom_pattern_regex_var, width=25, font=('Tahoma', 8))
        custom_regex_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=3)
        
        # Custom Pattern Is Zero Checkbox
        custom_zero_check = ttk.Checkbutton(custom_frame, text="Is Zero Indicator", 
                                           variable=self.custom_pattern_is_zero_var, 
                                           command=self.update_custom_pattern)
        custom_zero_check.grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=3)
        
        # Custom Pattern Buttons Frame
        custom_buttons_frame = ttk.Frame(custom_frame)
        custom_buttons_frame.grid(row=3, column=0, columnspan=2, pady=3)
        
        # Update Custom Pattern Button
        update_custom_btn = ttk.Button(custom_buttons_frame, text="Update Custom Pattern", 
                                      command=self.update_custom_pattern, width=18)
        update_custom_btn.grid(row=0, column=0, padx=(0, 5))
        
        # Help Button
        help_btn = ttk.Button(custom_buttons_frame, text="❓ Help", 
                             command=self.show_help, width=8)
        help_btn.grid(row=0, column=1)

        # Branch Configuration Frame
        branch_frame = ttk.LabelFrame(left_panel, text="Branch Configuration", padding="8")
        branch_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 8))
        branch_frame.columnconfigure(1, weight=1)
        
        # Branch selection
        ttk.Label(branch_frame, text="Branch:", font=('Tahoma', 8)).grid(row=0, column=0, sticky=tk.W, padx=(0, 8))
        branch_combo = ttk.Combobox(branch_frame, textvariable=self.branch_var, 
                                   values=list(BRANCH_CONFIG.keys()), width=25, font=('Tahoma', 8))
        branch_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=3)
        
        # Branch prefix display
        self.branch_prefix_label = ttk.Label(branch_frame, text="Prefix: Z1", font=('Tahoma', 9, 'bold'))
        self.branch_prefix_label.grid(row=1, column=0, columnspan=2, pady=(3, 0))
        
        # Bind branch selection change
        branch_combo.bind('<<ComboboxSelected>>', self.on_branch_change)
        
        # Server Configuration Frame
        server_frame = ttk.LabelFrame(left_panel, text="Server Configuration", padding="8")
        server_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 8))
        server_frame.columnconfigure(1, weight=1)
        
        # Server URL
        ttk.Label(server_frame, text="Server URL:", font=('Tahoma', 8)).grid(row=0, column=0, sticky=tk.W, padx=(0, 8))
        server_entry = ttk.Entry(server_frame, textvariable=self.server_url_var, width=35, font=('Tahoma', 8))
        server_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=3)
        
        ttk.Label(server_frame, text="Client ID:", font=('Tahoma', 8)).grid(row=1, column=0, sticky=tk.W, padx=(0, 8))
        client_id_entry = ttk.Entry(server_frame, textvariable=self.client_id_var, width=15, font=('Tahoma', 8))
        client_id_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=3)
        
        # Config Path Note (ย้ายมาไว้ล่างสุดของ left_panel)
        config_abs_path = os.path.abspath(CLIENT_CONFIG_FILE)
        config_note_label = ttk.Label(left_panel, 
                                     text=f"Config: {os.path.basename(config_abs_path)}", 
                                     font=('Tahoma', 7), 
                                     foreground='gray')
        config_note_label.grid(row=5, column=0, columnspan=2, sticky=tk.W, pady=(10, 5))
        
        # Right Panel - Status & Monitoring
        right_panel = ttk.Frame(main_frame)
        right_panel.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(5, 0))
        right_panel.columnconfigure(0, weight=1)
        right_panel.columnconfigure(1, weight=1)
        right_panel.rowconfigure(1, weight=1) 
        self.right_panel = right_panel

        # Status Frame
        status_frame = ttk.LabelFrame(right_panel, text="Status & Monitoring", padding="8")
        status_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 8))
        status_frame.columnconfigure(0, weight=1)
        
        # Status indicators
        status_indicators_frame = ttk.Frame(status_frame)
        status_indicators_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 8))
        status_indicators_frame.columnconfigure(0, weight=3) 
        status_indicators_frame.columnconfigure(1, weight=3)
        status_indicators_frame.columnconfigure(2, weight=4)
        
        # Serial status
        self.serial_status_label = ttk.Label(status_indicators_frame, text="🔴 Serial: Disconnected", 
                                            font=('Tahoma', 9, 'bold'))
        self.serial_status_label.grid(row=0, column=0, sticky=tk.W)
        
        # Server status - แสดงสีแดงเมื่อ Disconnected
        self.server_status_label = ttk.Label(status_indicators_frame, text="🔴 Server: Disconnected", 
                                            font=('Tahoma', 9, 'bold'), foreground='red')
        self.server_status_label.grid(row=0, column=1, sticky=tk.W)
        
        # Current weight
        self.weight_label = ttk.Label(status_indicators_frame, text="⚖️ Weight: 0 kg", 
                                    font=('Tahoma', 11, 'bold'))
        self.weight_label.grid(row=0, column=2, sticky=tk.E)
        
        # Log area
        log_frame = ttk.Frame(status_frame)
        log_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(1, weight=1)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=6, width=50, font=('Tahoma', 8)) # <--- ลดขนาด
        self.log_text.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        clear_log_btn = ttk.Button(log_frame, text="Clear Log", command=self.clear_log, width=10)
        clear_log_btn.grid(row=2, column=0, pady=(3, 0))
        
        # Real-time RS232 Data Display Frame
        realtime_frame = ttk.LabelFrame(right_panel, text="🔍 Real-time RS232 Data", padding="8")
        realtime_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 8))
        realtime_frame.columnconfigure(0, weight=1)
        realtime_frame.rowconfigure(1, weight=1)
        
        # Real-time data controls
        realtime_controls_frame = ttk.Frame(realtime_frame)
        realtime_controls_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        realtime_controls_frame.columnconfigure((0,1,2,3,4,5), weight=1) # ให้ทุกคอลัมน์ขยายเท่ากัน
        
        # Start/Stop real-time monitoring button
        self.realtime_monitor_var = tk.BooleanVar(value=False)
        self.realtime_monitor_btn = ttk.Button(realtime_controls_frame, text="▶️ Start Monitoring", 
                                             command=self.toggle_realtime_monitoring)
        self.realtime_monitor_btn.grid(row=0, column=0, padx=(0, 3), sticky=tk.EW)
        
        # Clear real-time data button
        clear_realtime_btn = ttk.Button(realtime_controls_frame, text="🗑️ Clear", 
                                      command=self.clear_realtime_data)
        clear_realtime_btn.grid(row=0, column=1, padx=(0, 5), sticky=tk.EW)
        
        # Auto-scroll checkbox
        self.auto_scroll_var = tk.BooleanVar(value=True)
        auto_scroll_check = ttk.Checkbutton(realtime_controls_frame, text="Auto-scroll", 
                                           variable=self.auto_scroll_var)
        auto_scroll_check.grid(row=0, column=2, padx=(0, 5))
        
        # Max lines display
        max_lines_frame = ttk.Frame(realtime_controls_frame)
        max_lines_frame.grid(row=0, column=3, columnspan=2, sticky=tk.W)
        ttk.Label(max_lines_frame, text="Max lines:", font=('Tahoma', 7)).pack(side=tk.LEFT)
        self.max_lines_var = tk.StringVar(value="100")
        max_lines_spinbox = ttk.Spinbox(max_lines_frame, from_=10, to=1000, 
                                       textvariable=self.max_lines_var, width=6, font=('Tahoma', 7))
        max_lines_spinbox.pack(side=tk.LEFT)
        
        # Export button
        export_btn = ttk.Button(realtime_controls_frame, text="📁 Export", 
                               command=self.export_realtime_data)
        export_btn.grid(row=0, column=5, sticky=tk.EW)
        
        # Bind events
        max_lines_spinbox.bind('<KeyRelease>', self.on_max_lines_change)
        max_lines_spinbox.bind('<<Increment>>', self.on_max_lines_change)
        max_lines_spinbox.bind('<<Decrement>>', self.on_max_lines_change)
        auto_scroll_check.bind('<Button-1>', self.on_auto_scroll_change)
        
        # Real-time data display
        self.realtime_text = scrolledtext.ScrolledText(realtime_frame, height=10, width=50, font=('Consolas', 8), bg='#1e1e1e', fg='#00ff00') # <--- ลดขนาด
        self.realtime_text.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Real-time data info
        self.realtime_info_label = ttk.Label(realtime_frame, text="📊 Ready to monitor RS232 data...", 
                                           font=('Tahoma', 7), foreground='gray')
        self.realtime_info_label.grid(row=2, column=0, sticky=tk.W, pady=(3, 0))
        
        # Update displays
        self.update_branch_prefix_display()
        self.update_scale_pattern_info()
        
        # Real-time monitoring variables
        self.realtime_data_buffer = []
        self.realtime_monitoring_active = False
        self.realtime_update_timer = None
        
        # === ย้าย Control Frames มาไว้ที่ Right Panel ===
        
        # Control Buttons Frame
        control_frame = ttk.LabelFrame(right_panel, text="Main Controls", padding="8")
        control_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 8), padx=(0, 4))
        control_frame.columnconfigure((0, 1, 2, 3), weight=1)

        self.start_btn = ttk.Button(control_frame, text="▶️ Start", command=self.start_client)
        self.start_btn.grid(row=0, column=0, padx=2, sticky=tk.EW)
        
        self.stop_btn = ttk.Button(control_frame, text="⏹️ Stop", command=self.stop_client, state='disabled')
        self.stop_btn.grid(row=0, column=1, padx=2, sticky=tk.EW)
        
        self.save_btn = ttk.Button(control_frame, text="💾 Save", command=self.save_configuration)
        self.save_btn.grid(row=0, column=2, padx=2, sticky=tk.EW)

        self.test_btn = ttk.Button(control_frame, text="🧪 Test All", command=self.test_all_functions)
        self.test_btn.grid(row=0, column=3, padx=2, sticky=tk.EW)
        
        # App & Help Buttons Frame
        app_help_frame = ttk.LabelFrame(right_panel, text="Application", padding="8")
        app_help_frame.grid(row=2, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 8), padx=(4, 0))
        app_help_frame.columnconfigure((0, 1, 2, 3), weight=1)

        self.frontend_btn = ttk.Button(app_help_frame, text="🌐 Frontend", command=self.open_frontend, style='Accent.TButton')
        self.frontend_btn.grid(row=0, column=0, padx=2, sticky=tk.EW)
        
        # เพิ่มปุ่ม Offline Scale
        self.offline_scale_btn = ttk.Button(app_help_frame, text="⚖️ Offline Scale", command=self.open_offline_scale)
        self.offline_scale_btn.grid(row=0, column=1, padx=2, sticky=tk.EW)
        
        self.tray_btn = ttk.Button(app_help_frame, text="📌 Tray", command=self.minimize_to_tray)
        self.tray_btn.grid(row=0, column=2, padx=2, sticky=tk.EW)
        
        help_btn = ttk.Button(app_help_frame, text="❓ Help", command=self.show_main_help)
        help_btn.grid(row=0, column=3, padx=2, sticky=tk.EW)
        
        # Debugging Buttons Frame
        debug_frame = ttk.LabelFrame(right_panel, text="Debugging Tools", padding="8")
        debug_frame.grid(row=3, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 8), padx=(0, 4))
        debug_frame.columnconfigure((0, 1), weight=1)

        debug_btn = ttk.Button(debug_frame, text="🐛 Debug Serial", command=self.debug_serial_reading)
        debug_btn.grid(row=0, column=0, padx=2, sticky=tk.EW)
        
        pattern_test_btn = ttk.Button(debug_frame, text="🔍 Test Pattern", command=self.test_pattern_parsing)
        pattern_test_btn.grid(row=0, column=1, padx=2, sticky=tk.EW)

        # Update displays and right_panel column weights
        right_panel.columnconfigure(0, weight=1)
        right_panel.columnconfigure(1, weight=1)
        self.update_branch_prefix_display()
        self.update_scale_pattern_info()

    def open_offline_scale(self):
        """เปิดไฟล์ offline_weighing.html สำหรับใช้งานตาชั่งผ่านระบบ Offline"""
        try:
            # หาไฟล์ offline_weighing.html ในโฟลเดอร์ปัจจุบัน
            offline_file = "offline_weighing.html"
            if os.path.exists(offline_file):
                # เปิดไฟล์ในเบราว์เซอร์
                file_path = os.path.abspath(offline_file)
                file_url = f"file:///{file_path.replace(os.sep, '/')}"
                webbrowser.open(file_url)
                self.log_message(f"Opened offline scale file: {file_path}")
                messagebox.showinfo("Offline Scale", f"Opening offline scale file:\n{file_path}")
            else:
                # ถ้าไม่พบไฟล์ ให้แจ้งเตือน
                self.log_message("Offline scale file not found: offline_weighing.html")
                messagebox.showwarning("File Not Found", 
                                     "Offline scale file 'offline_weighing.html' not found!\n\n"
                                     "Please ensure the file exists in the same directory as this application.")
        except Exception as e:
            self.log_message(f"Error opening offline scale file: {e}")
            messagebox.showerror("Error", f"Failed to open offline scale file: {e}")

    def show_help(self):
        """แสดงหน้าต่าง Help"""
        help_window = tk.Toplevel(self.root)
        help_window.title("❓ Help - Custom Pattern 3")
        help_window.geometry("600x500")
        help_window.configure(bg='#f0f0f0')
        
        # Make window modal
        help_window.transient(self.root)
        help_window.grab_set()
        
        # Main frame
        main_frame = ttk.Frame(help_window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="❓ วิธีใช้งาน Custom Pattern 3", 
                               font=('Tahoma', 14, 'bold'))
        title_label.pack(pady=(0, 15))
        
        # Help text
        help_text = scrolledtext.ScrolledText(main_frame, height=20, width=70, font=('Tahoma', 9))
        help_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        help_content = """❓ วิธีตั้งค่า Custom Pattern 3

📋 ขั้นตอนการตั้งค่า:
1. เลือก Scale Pattern เป็น "Custom Pattern 3"
2. กรอกข้อมูลในช่องต่างๆ
3. กดปุ่ม "Update Custom Pattern"
4. กดปุ่ม "Save" เพื่อบันทึก

�� การกรอกข้อมูล:

�� Pattern Prefix:
   • ใส่ชื่อของ Pattern เช่น "1@H", "CAS", "MT"
   • ใช้เป็นชื่อเรียก Pattern นี้

🔸 Regex Pattern:
   • ใส่รูปแบบข้อมูลที่ส่งมาจากตาชั่ง
   • ใช้ Regular Expression เพื่อจับค่าน้ำหนัก

🔸 Is Zero Indicator:
   • ติ๊กถ้า Pattern นี้เป็นสัญญาณน้ำหนัก 0
   • ไม่ติ๊กถ้าเป็นน้ำหนักจริง

📖 ตัวอย่างการใช้งาน:

🔹 ตัวอย่างที่ 1: Pattern "1@H"
   • Pattern Prefix: 1@H
   • Regex Pattern: 1@H\\s+(\\d+)
   • Is Zero Indicator: ไม่ติ๊ก
   • ข้อมูลที่จับได้: "1@H 1234" → น้ำหนัก = 1234

🔹 ตัวอย่างที่ 2: Pattern "CAS"
   • Pattern Prefix: CAS
   • Regex Pattern: CAS\\s+(\\d+)
   • Is Zero Indicator: ไม่ติ๊ก
   • ข้อมูลที่จับได้: "CAS 567" → น้ำหนัก = 567

🔹 ตัวอย่างที่ 3: Zero Pattern "H"
   • Pattern Prefix: H
   • Regex Pattern: \\sH\\s+(0{3,})
   • Is Zero Indicator: ติ๊ก
   • ข้อมูลที่จับได้: " H 0000" → น้ำหนัก = 0

📚 รูปแบบ Regex ที่ใช้บ่อย:

�� จับตัวเลขหลังช่องว่าง:
   • รูปแบบ: Pattern\\s+(\\d+)
   • ตัวอย่าง: "1@H 1234" → จับ "1234"

🔸 จับตัวเลขหลังเครื่องหมาย:
   • รูปแบบ: Pattern:(\\d+)
   • ตัวอย่าง: "1@H:1234" → จับ "1234"

🔸 จับตัวเลขในวงเล็บ:
   • รูปแบบ: Pattern\\((\\d+)\\)
   • ตัวอย่าง: "1@H(1234)" → จับ "1234"

�� จับ Zero Pattern:
   • รูปแบบ: Pattern\\s+(0{3,})
   • ตัวอย่าง: " H 0000" → จับ "0000"

⚠️ ข้อควรระวัง:
• ต้องกรอกทั้ง Pattern Prefix และ Regex Pattern
• Regex Pattern ต้องมี (\\d+) เพื่อจับตัวเลข
• ทดสอบ Pattern ก่อนใช้งานจริง
• ดูข้อมูลใน Activity Log เพื่อตรวจสอบ

💡 เคล็ดลับ:
• ใช้ Activity Log ดูข้อมูลจริงที่ส่งมาจากตาชั่ง
• ทดสอบ Pattern ด้วยข้อมูลตัวอย่าง
• บันทึกการตั้งค่าหลังจากทดสอบแล้ว
• ใช้ Help นี้เป็นคู่มืออ้างอิง"""
        
        help_text.insert(tk.END, help_content)
        help_text.config(state=tk.DISABLED)
        
        # Close button
        close_btn = ttk.Button(main_frame, text="ปิด", command=help_window.destroy, width=10)
        close_btn.pack(pady=(0, 5))
        
        # Center window
        help_window.update_idletasks()
        x = (help_window.winfo_screenwidth() // 2) - (help_window.winfo_width() // 2)
        y = (help_window.winfo_screenheight() // 2) - (help_window.winfo_height() // 2)
        help_window.geometry(f"+{x}+{y}")
        
    def update_custom_pattern(self):
        """อัปเดต Custom Pattern 3"""
        try:
            prefix = self.custom_pattern_prefix_var.get().strip()
            regex_pattern = self.custom_pattern_regex_var.get().strip()
            is_zero = self.custom_pattern_is_zero_var.get()
            
            if not prefix or not regex_pattern:
                messagebox.showwarning("Warning", "Please fill in both Prefix and Regex Pattern fields.")
                return
            
            # อัปเดต Custom Pattern 3
            SCALE_PATTERNS['Custom Pattern 3'] = [
                (prefix, regex_pattern, is_zero)
            ]
            
            self.log_message(f"Custom Pattern 3 updated: {prefix} -> {regex_pattern} (Zero: {is_zero})")
            self.update_scale_pattern_info()
            messagebox.showinfo("Success", "Custom Pattern 3 updated successfully!")
            
        except Exception as e:
            self.log_message(f"Error updating custom pattern: {e}")
            messagebox.showerror("Error", f"Failed to update custom pattern: {e}")
    
    def check_websocket_connection(self):
        """ตรวจสอบการเชื่อมต่อ WebSocket"""
        try:
            if self.websocket and not self.websocket.closed:
                return True
            else:
                self.log_message("WebSocket connection check failed")
                return False
        except Exception as e:
            self.log_message(f"WebSocket connection check error: {e}")
            return False
    
    async def ensure_websocket_connection(self):
        """ตรวจสอบและรักษาการเชื่อมต่อ WebSocket"""
        if not self.check_websocket_connection():
            self.log_message("Attempting to reconnect WebSocket...")
            try:
                server_url = self.server_url_var.get().strip()
                if server_url:
                    self.websocket = await websockets.connect(server_url)
                    self.is_connected = True
                    self.log_message("WebSocket reconnected successfully")
                    return True
            except Exception as e:
                self.log_message(f"WebSocket reconnection failed: {e}")
                return False
        return True
        
    def on_branch_change(self, event=None):
        """เมื่อมีการเปลี่ยนสาขา"""
        self.update_branch_prefix_display()
        self.log_message(f"Branch changed to: {self.branch_var.get()}")
        
    def on_scale_pattern_change(self, event=None):
        """เมื่อมีการเปลี่ยน Scale Pattern"""
        self.update_scale_pattern_info()
        self.log_message(f"Scale pattern changed to: {self.scale_pattern_var.get()}")
        
    def update_branch_prefix_display(self):
        """อัปเดตการแสดง Prefix ของสาขา"""
        selected_branch = self.branch_var.get()
        prefix = self.get_branch_prefix(selected_branch)
        self.branch_prefix_label.config(text=f"Prefix: {prefix}")
        
    def update_scale_pattern_info(self):
        """อัปเดตการแสดงข้อมูล Scale Pattern (ซ่อนไว้)"""
        # ซ่อนการแสดงรายละเอียด patterns
        self.scale_pattern_info_label.config(text="")
        
    # toggle_offline_mode function ถูกลบออกแล้ว - ใช้งาน Online Mode เท่านั้น
        
    def get_branch_prefix(self, branch_name):
        """ดึง Prefix ของสาขา"""
        if branch_name not in BRANCH_CONFIG:
            return 'Z1'  # Default
            
        prefix = BRANCH_CONFIG[branch_name]
        
        # สำหรับสาขาลพบุรี ใช้ปี พ.ศ. 2 ตัวสุดท้าย
        if prefix == 'DYNAMIC':
            current_year = datetime.now().year + 543  # แปลงเป็นปี พ.ศ.
            return str(current_year)[-2:]  # เอา 2 ตัวสุดท้าย
            
        return prefix
        
    def log_message(self, message):
        """เพิ่มข้อความลงใน log"""
        try:
            timestamp = datetime.now().strftime("%H:%M:%S")
            log_entry = f"[{timestamp}] {message}\n"
            self.log_text.insert(tk.END, log_entry)
            self.log_text.see(tk.END)
            print(log_entry.strip())
        except Exception as e:
            print(f"Log error: {e}")
        
    def clear_log(self):
        """ล้าง log"""
        try:
            self.log_text.delete(1.0, tk.END)
        except Exception as e:
            print(f"Clear log error: {e}")
    
    def toggle_realtime_monitoring(self):
        """เปิด/ปิดการ monitor ข้อมูล real-time"""
        try:
            if not self.realtime_monitoring_active:
                self.log_message("Attempting to start real-time monitoring...")
                ser = self.get_serial_connection()
                if not ser or not ser.is_open:
                    messagebox.showwarning("Warning", "Serial connection not available or not open!")
                    self.log_message("Failed to start monitoring: Serial connection is not open.")
                    return
                
                self.realtime_monitoring_active = True
                self.realtime_monitor_btn.config(text="⏸️ Stop Monitoring")
                self.realtime_info_label.config(text="📊 Monitoring...", foreground='green')
                self.log_message("Real-time monitoring started.")
                self.start_realtime_reading()
            else:
                self.realtime_monitoring_active = False
                self.realtime_monitor_btn.config(text="▶️ Start Monitoring")
                self.realtime_info_label.config(text="📊 Monitoring stopped.", foreground='gray')
                self.log_message("Real-time monitoring stopped.")
                if self.realtime_update_timer:
                    self.root.after_cancel(self.realtime_update_timer)
                    self.realtime_update_timer = None
        except Exception as e:
            self.log_message(f"Error in toggle_realtime_monitoring: {e}")

    def start_realtime_reading(self):
        """เริ่มการอ่านข้อมูล real-time"""
        if not self.realtime_monitoring_active:
            return
        
        try:
            ser = self.get_serial_connection()
            if ser and ser.in_waiting > 0:
                new_bytes = ser.read(ser.in_waiting)
                if new_bytes:
                    self.log_message(f"Read {len(new_bytes)} bytes from serial port.")
                    self.add_realtime_data(new_bytes)
                else:
                    self.log_message("in_waiting > 0 but read() returned no bytes.")
            
            self.realtime_update_timer = self.root.after(200, self.start_realtime_reading)
            
        except Exception as e:
            self.log_message(f"Error in start_realtime_reading: {e}")
            self.realtime_monitoring_active = False
            self.realtime_monitor_btn.config(text="▶️ Start Monitoring")
            self.realtime_info_label.config(text="⚠️ Error! Monitoring stopped.", foreground='red')

    def clear_realtime_data(self):
        """ล้างข้อมูล real-time"""
        try:
            self.realtime_text.delete(1.0, tk.END)
            self.realtime_data_buffer.clear()
            self.realtime_info_label.config(text="📊 Real-time data cleared", foreground='gray')
            self.log_message("Real-time data cleared")
        except Exception as e:
            self.log_message(f"Clear real-time data error: {e}")
    
    def update_realtime_display(self):
        """อัปเดตการแสดงข้อมูล real-time"""
        try:
            if not self.realtime_monitoring_active:
                return
            
            # อัปเดตการแสดงผลข้อมูลที่มีอยู่แล้ว
            if self.realtime_data_buffer:
                self.update_realtime_text()
                
                # อัปเดตข้อมูลสถิติ
                total_bytes = sum(entry['length'] for entry in self.realtime_data_buffer)
                self.realtime_info_label.config(
                    text=f"📊 Monitoring: {len(self.realtime_data_buffer)} packets, {total_bytes} bytes received",
                    foreground='green'
                )
            
            # ตั้งเวลาเรียกฟังก์ชันนี้อีกครั้ง (ทุก 200ms)
            self.realtime_update_timer = self.root.after(200, self.update_realtime_display)
            
        except Exception as e:
            self.log_message(f"Update real-time display error: {e}")
            # ตั้งเวลาเรียกฟังก์ชันนี้อีกครั้งแม้เกิดข้อผิดพลาด
            self.realtime_update_timer = self.root.after(200, self.update_realtime_display)
    
    def update_realtime_text(self):
        """อัปเดตข้อความใน real-time display"""
        try:
            self.realtime_text.delete(1.0, tk.END)
            
            if not self.realtime_data_buffer:
                self.realtime_text.insert(tk.END, "No data received yet...\n")
                return
            
            # แสดงข้อมูลล่าสุดก่อน (reverse order)
            for entry in reversed(self.realtime_data_buffer):
                timestamp = entry['timestamp']
                ascii_data = entry['ascii']
                length = entry['length']
                
                # สร้างบรรทัดข้อมูล - ลบ HEX และ DEC
                line = f"[{timestamp}] ({length} bytes)\n"
                line += f"ASCII: {ascii_data}\n"
                line += "-" * 50 + "\n"
                
                self.realtime_text.insert(tk.END, line)
            
            # Auto-scroll ถ้าเปิดใช้งาน
            if self.auto_scroll_var.get():
                self.realtime_text.see(tk.END)
                
        except Exception as e:
            self.log_message(f"Update real-time text error: {e}")

    
    def add_realtime_data(self, data_bytes):
        """เพิ่มข้อมูล real-time ลงใน buffer"""
        try:
            # แปลงข้อมูลเป็นรูปแบบต่างๆ
            hex_data = ' '.join([f'{b:02X}' for b in data_bytes])
            ascii_data = ''.join([chr(b) if 32 <= b <= 126 else '.' for b in data_bytes])
            decimal_data = ' '.join([str(b) for b in data_bytes])
            
            # สร้าง entry ใหม่
            entry = {
                'timestamp': datetime.now().strftime('%H:%M:%S.%f')[:-3],
                'length': len(data_bytes),
                'hex': hex_data,
                'ascii': ascii_data,
                'decimal': decimal_data
            }
            
            # เพิ่มลงใน buffer
            self.realtime_data_buffer.append(entry)
            
            # จำกัดขนาด buffer
            max_lines = int(self.max_lines_var.get())
            if len(self.realtime_data_buffer) > max_lines:
                self.realtime_data_buffer = self.realtime_data_buffer[-max_lines:]
            
            # อัปเดตการแสดงผล
            self.update_realtime_text()
            
            # Auto-scroll ถ้าเปิดใช้งาน
            if self.auto_scroll_var.get():
                self.realtime_text.see(tk.END)
            
            # ลอง parse ข้อมูลใหม่
            try:
                decoded = data_bytes.decode('latin-1', errors='ignore')
                lines = []
                for line in decoded.split('\r\n'):
                    lines.extend(line.split('\n'))
                
                # ตรวจสอบทุกบรรทัด
                for line in lines:
                    line = line.strip()
                    if line:
                        parsed_value = self.parse_scale_data(line)
                        if parsed_value != "N/A":
                            self.last_weight = parsed_value
                            self.weight_label.config(text=f"⚖️ Weight: {parsed_value}")
                            # ไม่ log ทุกครั้งเพื่อลด spam
                            break
            except Exception as e:
                # ไม่เป็นไรถ้า parse ไม่ได้
                pass
                
        except Exception as e:
            self.log_message(f"Add real-time data error: {e}")
    
    def on_max_lines_change(self, event=None):
        """เมื่อมีการเปลี่ยนแปลงจำนวนบรรทัดสูงสุด"""
        try:
            max_lines = int(self.max_lines_var.get())
            if len(self.realtime_data_buffer) > max_lines:
                self.realtime_data_buffer = self.realtime_data_buffer[-max_lines:]
                self.update_realtime_text()
            self.log_message(f"Max lines changed to: {max_lines}")
        except ValueError:
            self.log_message("Invalid max lines value")
        except Exception as e:
            self.log_message(f"Max lines change error: {e}")
    
    def on_auto_scroll_change(self, event=None):
        """เมื่อมีการเปลี่ยนแปลงการตั้งค่า auto-scroll"""
        try:
            auto_scroll = self.auto_scroll_var.get()
            if auto_scroll and self.realtime_data_buffer:
                self.realtime_text.see(tk.END)
            self.log_message(f"Auto-scroll {'enabled' if auto_scroll else 'disabled'}")
        except Exception as e:
            self.log_message(f"Auto-scroll change error: {e}")
    
    def export_realtime_data(self):
        """ส่งออกข้อมูล real-time เป็นไฟล์"""
        try:
            if not self.realtime_data_buffer:
                messagebox.showwarning("Warning", "No real-time data to export!")
                return
            
            from tkinter import filedialog
            filename = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                title="Export Real-time Data"
            )
            
            if filename:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write("Real-time RS232 Data Export\n")
                    f.write("=" * 50 + "\n\n")
                    
                    for entry in self.realtime_data_buffer:
                        f.write(f"[{entry['timestamp']}] ({entry['length']} bytes)\n")
                        f.write(f"HEX: {entry['hex']}\n")
                        f.write(f"ASCII: {entry['ascii']}\n")
                        f.write(f"DEC: {entry['decimal']}\n")
                        f.write("-" * 50 + "\n")
                
                self.log_message(f"Real-time data exported to: {filename}")
                messagebox.showinfo("Success", f"Real-time data exported successfully!\n\nFile: {filename}")
                
        except Exception as e:
            self.log_message(f"Export real-time data error: {e}")
            messagebox.showerror("Error", f"Failed to export real-time data: {e}")
        
    def check_ports(self):
        """ตรวจสอบ port ทั้งหมด"""
        try:
            self.log_message("=== Checking Available Ports ===")
            ports = list(serial.tools.list_ports.comports())
            
            if not ports:
                self.log_message("No serial ports found!")
                messagebox.showwarning("Warning", "No serial ports found!\nPlease check your USB to Serial adapter.")
                return
            
            for port in ports:
                self.log_message(f"Port: {port.device}")
                self.log_message(f"  Description: {port.description}")
                self.log_message(f"  Hardware ID: {port.hwid}")
                self.log_message(f"  Manufacturer: {port.manufacturer}")
                self.log_message(f"  Product: {port.product}")
                self.log_message("")
                
            self.log_message("=== Port Check Complete ===")
            
        except Exception as e:
            self.log_message(f"Error checking ports: {e}")
        
    def update_available_ports(self):
        """อัปเดตรายการ port ที่ใช้งานได้"""
        try:
            ports = [port.device for port in serial.tools.list_ports.comports()]
            self.port_combo['values'] = ports
            if ports and self.port_var.get() not in ports:
                self.port_var.set(ports[0])
            self.log_message(f"Available ports: {', '.join(ports)}")
        except Exception as e:
            self.log_message(f"Error updating ports: {e}")
        
    def get_parity_key(self):
        """แปลง parity กลับเป็น key"""
        try:
            for key, value in parity_map.items():
                if value == self.serial_config['parity']:
                    return key
            return 'N'
        except Exception as e:
            print(f"Parity key error: {e}")
            return 'N'
        
    def get_stopbits_key(self):
        """แปลง stopbits กลับเป็น key"""
        try:
            for key, value in stop_bits_map.items():
                if value == self.serial_config['stopbits']:
                    return key
            return '1'
        except Exception as e:
            print(f"Stopbits key error: {e}")
            return '1'
        
    def get_bytesize_key(self):
        """แปลง bytesize กลับเป็น key"""
        try:
            for key, value in byte_size_map.items():
                if value == self.serial_config['bytesize']:
                    return key
            return '8'
        except Exception as e:
            print(f"Bytesize key error: {e}")
            return '8'
        
    # ... existing code ...

    def load_config(self):
        """โหลด config จากไฟล์"""
        try:
            config = configparser.ConfigParser()
            loaded_settings = {
                'port': DEFAULT_SERIAL_PORT,
                'baudrate': DEFAULT_BAUD_RATE,
                'parity_key': DEFAULT_PARITY,
                'stopbits_key': DEFAULT_STOP_BITS,
                'bytesize_key': DEFAULT_BYTE_SIZE,
                'timeout': DEFAULT_READ_TIMEOUT,
                'sensitivity': DEFAULT_SENSITIVITY
            }
            
            # เก็บข้อมูล config เพิ่มเติมสำหรับโหลดทีหลัง
            self.config_data = {
                'branch': 'สำนักงานใหญ่ P8',
                'scale_pattern': 'Raw Data (No Parse)',
                'custom_prefix': 'CUSTOM3',
                'custom_regex': r'CUSTOM3\s+(\d+)',
                'custom_iszero': False
            }
            
            # ตรวจสอบไฟล์ config ใน path ของโปรแกรม
            config_paths = [
                CLIENT_CONFIG_FILE,  # ไฟล์ในโฟลเดอร์ปัจจุบัน
                os.path.join(os.path.dirname(sys.executable), CLIENT_CONFIG_FILE),  # ไฟล์ในโฟลเดอร์โปรแกรม
                os.path.join(os.path.dirname(os.path.abspath(__file__)), CLIENT_CONFIG_FILE)  # ไฟล์ในโฟลเดอร์ script
            ]
            
            config_loaded = False
            for config_path in config_paths:
                if os.path.exists(config_path):
                    try:
                        # แก้ไขปัญหา encoding โดยระบุ encoding เป็น utf-8
                        config.read(config_path, encoding='utf-8')
                        if 'SerialConfig' in config:
                            cfg_section = config['SerialConfig']
                            loaded_settings['port'] = cfg_section.get('Port', DEFAULT_SERIAL_PORT)
                            loaded_settings['baudrate'] = cfg_section.getint('BaudRate', DEFAULT_BAUD_RATE)
                            loaded_settings['parity_key'] = cfg_section.get('Parity', DEFAULT_PARITY).upper()
                            loaded_settings['stopbits_key'] = cfg_section.get('StopBits', DEFAULT_STOP_BITS)
                            loaded_settings['bytesize_key'] = cfg_section.get('ByteSize', DEFAULT_BYTE_SIZE)
                            loaded_settings['timeout'] = cfg_section.getfloat('ReadTimeout', DEFAULT_READ_TIMEOUT)
                            loaded_settings['sensitivity'] = cfg_section.getfloat('Sensitivity', DEFAULT_SENSITIVITY)
                            
                            # Load branch configuration
                            if 'BranchConfig' in config:
                                branch_section = config['BranchConfig']
                                self.config_data['branch'] = branch_section.get('Branch', 'สำนักงานใหญ่ P8')
                                
                            # Load scale pattern configuration
                            if 'ScaleConfig' in config:
                                scale_section = config['ScaleConfig']
                                self.config_data['scale_pattern'] = scale_section.get('Pattern', 'Raw Data (No Parse)')
                                
                            # Load custom pattern 3 configuration
                            if 'CustomPattern3Config' in config:
                                custom_section = config['CustomPattern3Config']
                                self.config_data['custom_prefix'] = custom_section.get('Prefix', 'CUSTOM3')
                                self.config_data['custom_regex'] = custom_section.get('Regex', r'CUSTOM3\s+(\d+)')
                                self.config_data['custom_iszero'] = custom_section.getboolean('IsZero', False)
                            
                            config_loaded = True
                            print(f"Config loaded from: {config_path}")
                            break
                            
                    except Exception as e:
                        print(f"Error loading config from {config_path}: {e}")
                        continue
            
            if not config_loaded:
                print("No valid config file found. Using defaults.")
            
            return {
                'port': loaded_settings['port'],
                'baudrate': loaded_settings['baudrate'],
                'parity': parity_map.get(loaded_settings['parity_key'], serial.PARITY_NONE),
                'stopbits': stop_bits_map.get(loaded_settings['stopbits_key'], serial.STOPBITS_ONE),
                'bytesize': byte_size_map.get(loaded_settings['bytesize_key'], serial.EIGHTBITS),
                'timeout': loaded_settings['timeout'],
                'sensitivity': loaded_settings['sensitivity']
            }
        except Exception as e:
            print(f"Load config error: {e}")
            return {
                'port': DEFAULT_SERIAL_PORT,
                'baudrate': DEFAULT_BAUD_RATE,
                'parity': serial.PARITY_NONE,
                'stopbits': serial.STOPBITS_ONE,
                'bytesize': serial.EIGHTBITS,
                'timeout': DEFAULT_READ_TIMEOUT,
                'sensitivity': DEFAULT_SENSITIVITY
            }

# ... existing code ...
        
    def save_configuration(self):
        """บันทึกการตั้งค่า"""
        try:
            config = configparser.ConfigParser()
            config['SerialConfig'] = {
                'Port': self.port_var.get(),
                'BaudRate': self.baudrate_var.get(),
                'Parity': self.parity_var.get(),
                'StopBits': self.stopbits_var.get(),
                'ByteSize': self.bytesize_var.get(),
                'ReadTimeout': self.timeout_var.get(),
                'Sensitivity': self.sensitivity_var.get()
            }
            
            # Save branch configuration
            config['BranchConfig'] = {
                'Branch': self.branch_var.get()
            }
            
            # Save scale pattern configuration
            config['ScaleConfig'] = {
                'Pattern': self.scale_pattern_var.get()
            }
            
            # Save custom pattern 3 configuration
            config['CustomPattern3Config'] = {
                'Prefix': self.custom_pattern_prefix_var.get(),
                'Regex': self.custom_pattern_regex_var.get(),
                'IsZero': str(self.custom_pattern_is_zero_var.get())
            }
            
            # บันทึกไฟล์ในโฟลเดอร์โปรแกรม
            config_path = os.path.join(os.path.dirname(sys.executable), CLIENT_CONFIG_FILE)
            if not os.path.exists(os.path.dirname(config_path)):
                config_path = CLIENT_CONFIG_FILE  # Fallback to current directory
            
            with open(config_path, 'w') as configfile:
                config.write(configfile)
                
            config_abs_path = os.path.abspath(config_path)
            self.log_message(f"Configuration saved to: {config_abs_path}")
            messagebox.showinfo("Success", f"Configuration saved successfully!\n\nFile: {config_abs_path}")
            
        except Exception as e:
            self.log_message(f"Error saving configuration: {e}")
            messagebox.showerror("Error", f"Failed to save configuration: {e}")
            
    def test_serial_connection(self):
        """ทดสอบการเชื่อมต่อ Serial"""
        try:
            test_config = {
                'port': self.port_var.get(),
                'baudrate': int(self.baudrate_var.get()),
                'parity': parity_map.get(self.parity_var.get(), serial.PARITY_NONE),
                'stopbits': stop_bits_map.get(self.stopbits_var.get(), serial.STOPBITS_ONE),
                'bytesize': byte_size_map.get(self.bytesize_var.get(), serial.EIGHTBITS),
                'timeout': float(self.timeout_var.get())
            }
            
            self.log_message(f"Testing connection to {test_config['port']}...")
            self.log_message(f"Config: {test_config['port']}, {test_config['baudrate']}, {self.parity_var.get()}, {self.stopbits_var.get()}, {self.bytesize_var.get()}")
            
            with serial.Serial(**test_config) as test_ser:
                if test_ser.is_open:
                    self.log_message("Serial connection test successful!")
                    self.serial_status_label.config(text="🟢 Serial: Test OK")
                    
                    # แนะนำให้เปิด real-time monitoring
                    result = messagebox.askyesno("Test Successful", 
                                               "Serial connection test successful!\n\n"
                                               "Would you like to start real-time monitoring\n"
                                               "to see the data from the scale?")
                    if result:
                        self.toggle_realtime_monitoring()
                else:
                    self.log_message("Serial connection test failed!")
                    self.serial_status_label.config(text="🔴 Serial: Test Failed")
                    messagebox.showerror("Error", "Serial connection test failed!")
                    
        except serial.SerialException as e:
            self.log_message(f"Serial connection test error: {e}")
            self.serial_status_label.config(text="🔴 Serial: Error")
            messagebox.showerror("Error", f"Serial connection test failed: {e}")
        except PermissionError as e:
            self.log_message(f"Permission Error: {e}")
            self.serial_status_label.config(text="🔴 Serial: Permission Denied")
            messagebox.showerror("Permission Error", 
                               "Cannot access the serial port.\n\n"
                               "Possible solutions:\n"
                               "1. Run as Administrator\n"
                               "2. Close other applications using this port\n"
                               "3. Check Device Manager for port conflicts\n"
                               "4. Reconnect USB to Serial adapter")
        except Exception as e:
            self.log_message(f"Unexpected error: {e}")
            self.serial_status_label.config(text="🔴 Serial: Error")
            messagebox.showerror("Error", f"Unexpected error: {e}")

        
    def test_all_functions(self):
        """ทดสอบทุกฟังก์ชัน"""
        try:
            self.log_message("=== Testing All Functions ===")
            
            # 1. ทดสอบการเชื่อมต่อ Serial
            self.log_message("1. Testing Serial Connection...")
            ser = self.get_serial_connection()
            if not ser:
                self.log_message("   ❌ Serial connection failed")
                messagebox.showerror("Error", "Serial connection failed!")
                return
            else:
                self.log_message("   ✅ Serial connection successful!")
            
            # 2. ทดสอบการอ่านข้อมูล
            self.log_message("2. Testing Data Reading...")
            
            # ล้าง buffer ก่อน
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            self.read_buffer = b''
            
            # อ่านข้อมูล 5 ครั้ง
            data_received = False
            for i in range(5):
                try:
                    original_timeout = ser.timeout
                    ser.timeout = 0.5
                    
                    data = ser.read(100)
                    if data:
                        # ลบการแสดง Hex และ ASCII
                        self.log_message(f"   Read {i+1}: {data.decode('latin-1', errors='ignore')}")
                        self.read_buffer += data
                        data_received = True
                    else:
                        self.log_message(f"   Read {i+1}: No data")
                    
                    ser.timeout = original_timeout
                    time.sleep(0.3)  # เพิ่มเวลารอ
                    
                except Exception as e:
                    self.log_message(f"   Read {i+1} error: {e}")
            
            if not data_received:
                self.log_message("   ⚠️ No data received from scale")
                messagebox.showwarning("Warning", "No data received from scale!\nPlease check if the scale is sending data.")
                return
            
            # 3. ทดสอบการ parse และแสดงผล
            self.log_message("3. Testing Data Parsing and Display...")
            if self.read_buffer:
                try:
                    decoded = self.read_buffer.decode('latin-1', errors='ignore')
                    self.log_message(f"   Decoded: '{decoded}'")
                    
                    # แยกข้อมูลตามบรรทัด
                    lines = decoded.split('\r\n') + decoded.split('\n')
                    for line in lines:
                        line = line.strip()
                        if line:
                            self.log_message(f"   Processing line: '{line}'")
                            parsed_value = self.parse_scale_data(line)
                            self.log_message(f"   Parsed result: {parsed_value}")
                            
                            # อัปเดต weight label
                            if parsed_value != "N/A":
                                self.last_weight = parsed_value
                                self.weight_label.config(text=f"⚖️ Weight: {parsed_value}")
                                self.log_message(f"   ✅ Updated weight: {parsed_value}")
                                break
                            else:
                                self.log_message(f"   ❌ Failed to parse: {line}")
                    
                except Exception as e:
                    self.log_message(f"   Parse error: {e}")
            
            # 4. แนะนำการใช้งาน
            self.log_message("4. Test Complete!")
            result = messagebox.askyesno("Test Complete", 
                                    "All tests completed!\n\n"
                                    "Would you like to:\n"
                                    "• Start real-time monitoring?\n"
                                    "• Start the client?")
            
            if result:
                # เปิด real-time monitoring
                if not self.realtime_monitoring_active:
                    self.toggle_realtime_monitoring()
                
                # แนะนำให้เริ่ม client
                if not self.is_running:
                    result2 = messagebox.askyesno("Start Client", 
                                                "Would you like to start the client now?")
                    if result2:
                        self.start_client()
            
        except Exception as e:
            self.log_message(f"Test all functions error: {e}")
            messagebox.showerror("Error", f"Test failed: {e}")

    def test_pattern_parsing(self):
        """ทดสอบการ parse pattern โดยเฉพาะ"""
        try:
            self.log_message("=== Testing Pattern Parsing ===")
            
            # ข้อมูลทดสอบ
            test_data = "ST,GS,+00000.0kg"
            self.log_message(f"Test data: '{test_data}'")
            
            # ทดสอบทุก pattern
            for pattern_name, patterns in SCALE_PATTERNS.items():
                self.log_message(f"Testing pattern: {pattern_name}")
                
                # ตั้งค่า pattern ชั่วคราว
                original_pattern = self.scale_pattern_var.get()
                self.scale_pattern_var.set(pattern_name)
                
                # ทดสอบ parse
                parsed_value = self.parse_scale_data(test_data)
                self.log_message(f"   Result: {parsed_value}")
                
                # คืนค่า pattern เดิม
                self.scale_pattern_var.set(original_pattern)
            
            self.log_message("=== Pattern Testing Complete ===")
            
        except Exception as e:
            self.log_message(f"Pattern testing error: {e}")
    def test_connection_status(self):
        """ทดสอบสถานะการเชื่อมต่อและอัปเดต status"""
        try:
            # ตรวจสอบว่ามีการเชื่อมต่ออยู่หรือไม่
            if self.serial_connection and self.serial_connection.is_open:
                self.serial_status_label.config(text="🟢 Serial: Connected")
                self.log_message("Serial connection is active")
                return True
            else:
                # ลองเชื่อมต่อใหม่
                test_config = {
                    'port': self.port_var.get(),
                    'baudrate': int(self.baudrate_var.get()),
                    'parity': parity_map.get(self.parity_var.get(), serial.PARITY_NONE),
                    'stopbits': stop_bits_map.get(self.stopbits_var.get(), serial.STOPBITS_ONE),
                    'bytesize': byte_size_map.get(self.bytesize_var.get(), serial.EIGHTBITS),
                    'timeout': 0.1  # ใช้ timeout สั้นๆ
                }
                
                with serial.Serial(**test_config) as test_ser:
                    if test_ser.is_open:
                        self.serial_status_label.config(text="🟢 Serial: Available")
                        self.log_message("Serial port is available")
                        return True
                    else:
                        self.serial_status_label.config(text="🔴 Serial: Unavailable")
                        self.log_message("Serial port is unavailable")
                        return False
                        
        except serial.SerialException as e:
            self.serial_status_label.config(text="🔴 Serial: Error")
            self.log_message(f"Serial status check error: {e}")
            return False
        except PermissionError as e:
            self.serial_status_label.config(text="🔴 Serial: Permission Denied")
            self.log_message(f"Permission error: {e}")
            return False
        except Exception as e:
            self.serial_status_label.config(text="🔴 Serial: Error")
            self.log_message(f"Unexpected error: {e}")
            return False

    def debug_serial_reading(self):
        """Debug การอ่านข้อมูล Serial"""
        try:
            self.log_message("=== Debug Serial Reading ===")
            
            ser = self.get_serial_connection()
            if not ser:
                self.log_message("❌ Serial connection not available!")
                return
            
            # แสดงการตั้งค่า
            self.log_message(f"✅ Serial connected: {ser.port}")
            self.log_message(f"   Baudrate: {ser.baudrate}")
            self.log_message(f"   Parity: {ser.parity}")
            self.log_message(f"   Stop bits: {ser.stopbits}")
            self.log_message(f"   Byte size: {ser.bytesize}")
            self.log_message(f"   Timeout: {ser.timeout}")
            
            # ล้าง buffer
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            self.read_buffer = b''
            
            self.log_message("📖 Reading data continuously...")
            
            # อ่านข้อมูล 10 ครั้ง
            for i in range(10):
                try:
                    original_timeout = ser.timeout
                    ser.timeout = 0.2
                    
                    # ตรวจสอบข้อมูลใน buffer
                    if ser.in_waiting > 0:
                        self.log_message(f"   Buffer has {ser.in_waiting} bytes")
                    
                    # อ่านข้อมูล
                    data = ser.read(100)
                    if data:
                        self.log_message(f"   Read {i+1}: {len(data)} bytes")
                        # ลบการแสดง HEX และ ASCII
                        self.log_message(f"      Data: '{data.decode('latin-1', errors='ignore')}'")
                        
                        # เพิ่มข้อมูลลงใน buffer
                        self.read_buffer += data
                        
                        # ลอง decode
                        try:
                            decoded = self.read_buffer.decode('latin-1', errors='ignore')
                            self.log_message(f"      Full buffer: '{decoded}'")
                            
                            # แยกบรรทัด
                            lines = decoded.split('\r\n') + decoded.split('\n')
                            for j, line in enumerate(lines):
                                if line.strip():
                                    self.log_message(f"      Line {j+1}: '{line.strip()}'")
                        except Exception as e:
                            self.log_message(f"      Decode error: {e}")
                    else:
                        self.log_message(f"   Read {i+1}: No data")
                    
                    ser.timeout = original_timeout
                    time.sleep(0.1)
                    
                except Exception as e:
                    self.log_message(f"   Read {i+1} error: {e}")
            
            self.log_message("=== Debug Complete ===")
            
        except Exception as e:
            self.log_message(f"Debug error: {e}")

    def get_serial_connection(self):
        """เชื่อมต่อ RS232"""
        if self.serial_connection and self.serial_connection.is_open:
            return self.serial_connection
            
        try:
            current_config = {
                'port': self.port_var.get(),
                'baudrate': int(self.baudrate_var.get()),
                'parity': parity_map.get(self.parity_var.get(), serial.PARITY_NONE),
                'stopbits': stop_bits_map.get(self.stopbits_var.get(), serial.STOPBITS_ONE),
                'bytesize': byte_size_map.get(self.bytesize_var.get(), serial.EIGHTBITS),
                'timeout': float(self.timeout_var.get())
            }
            
            # Log configuration for debugging
            self.log_message(f"Connecting with config: {current_config['port']}, {current_config['baudrate']}, {self.parity_var.get()}, {self.stopbits_var.get()}, {self.bytesize_var.get()}")
            
            self.serial_connection = serial.Serial(**current_config)
            if self.serial_connection.is_open:
                self.log_message(f"Connected to {current_config['port']}")
                self.serial_status_label.config(text="🟢 Serial: Connected")
                return self.serial_connection
        except serial.SerialException as e:
            self.log_message(f"Serial connection error: {e}")
            self.serial_status_label.config(text="🔴 Serial: Error")
            self.serial_connection = None
        except PermissionError as e:
            self.log_message(f"Permission Error: {e}")
            self.serial_status_label.config(text="�� Serial: Permission Denied")
            self.serial_connection = None
        except Exception as e:
            self.log_message(f"Unexpected serial error: {e}")
            self.serial_connection = None
        return None
        
    def parse_scale_data(self, cleaned_text):
        """Parse ข้อมูลจาก scale ตาม Pattern ที่เลือก"""
        try:
            # ใช้ Pattern ตามที่เลือก
            selected_pattern = self.scale_pattern_var.get()
            if selected_pattern not in SCALE_PATTERNS:
                selected_pattern = 'Default'  # Fallback to default
                
            # ถ้าเป็น Raw Data (No Parse) ให้แสดงข้อมูลดิบเลย
            if selected_pattern == 'Raw Data (No Parse)':
                return cleaned_text.strip()
                
            known_weight_indicators = SCALE_PATTERNS[selected_pattern]
        
            extracted_weight_values = []
            for indicator_text, pattern_regex, is_zero_indicator in known_weight_indicators:
                matches = re.findall(pattern_regex, cleaned_text)
                if matches:
                    self.log_message(f"Pattern '{indicator_text}' matched: {matches} for text: '{cleaned_text}'")
                    for match in matches:
                        if is_zero_indicator:
                            extracted_weight_values.append("0")
                        else:
                            try:
                                # สำหรับ ST,GS Format ที่มี 2 capture groups
                                if isinstance(match, tuple) and len(match) == 2:
                                    num_str_from_match = match[1]  # ตัวเลข (ตัวที่ 2)
                                else:
                                    # สำหรับ Pattern อื่นๆ ที่มี 1 capture group
                                    num_str_from_match = match
                                
                                # รองรับทั้งตัวเลขเต็มและทศนิยม รวมถึงค่าติดลบ
                                if '.' in num_str_from_match:
                                    weight_val = float(num_str_from_match)
                                else:
                                    weight_val = float(int(num_str_from_match))
                                
                                # จัดการค่าติดลบ - เก็บค่าติดลบไว้เพื่อการวิเคราะห์
                                if weight_val < 0:
                                    # ค่าติดลบอาจหมายถึงการชั่งผิดทิศทางหรือมีปัญหา
                                    # ให้เก็บค่าสัมบูรณ์ไว้ แต่เพิ่ม log เพื่อแจ้งเตือน
                                    if abs(weight_val) < 0.1:  # ค่าติดลบน้อยกว่า 0.1 kg
                                        weight_val = 0.0
                                        self.log_message(f"Negative weight below threshold, treating as 0: {cleaned_text}")
                                    else:
                                        # ค่าติดลบที่มากกว่า ให้ใช้ค่าสัมบูรณ์
                                        original_val = weight_val
                                        weight_val = abs(weight_val)
                                        self.log_message(f"Negative weight converted to positive: {original_val} -> {weight_val} (from: {cleaned_text})")
                                
                                # ใช้ความไวในการกรองข้อมูล
                                sensitivity = float(self.sensitivity_var.get())
                                if abs(weight_val) < sensitivity:
                                    weight_val = 0.0
                                
                                extracted_weight_values.append(str(weight_val))
                            except ValueError:
                                pass
                            
            if extracted_weight_values:
                non_zero_values = [val for val in extracted_weight_values if val != "0" and val != "0.0"]
                if non_zero_values:
                    weight_result = non_zero_values[-1]
                    self.log_message(f"Parsed weight from complete pattern: {cleaned_text} -> {weight_result}")
                    # ลบการบันทึกใน Local Database
                    return weight_result
                elif "0" in extracted_weight_values or "0.0" in extracted_weight_values:
                    weight_result = "0"
                    self.log_message(f"Parsed zero weight from complete pattern: {cleaned_text} -> {weight_result}")
                    # ลบการบันทึกใน Local Database
                    return weight_result
            
            # เพิ่มการตรวจสอบข้อมูลที่อาจถูกตัดขาด
            if selected_pattern == 'ST,GS Format':
                # ตรวจสอบว่ามีข้อมูล ST,GS หรือ US,GS ที่ไม่สมบูรณ์หรือไม่
                if 'ST,GS' in cleaned_text or 'US,GS' in cleaned_text:
                    # ลองหา pattern ที่ไม่สมบูรณ์ (รวมถึงค่าติดลบ)
                    incomplete_patterns = [
                        (r"ST,GS,\+([0-9]+\.?[0-9]*)$", False),
                        (r"US,GS,\+([0-9]+\.?[0-9]*)$", False),
                        (r"ST,GS,\+0{3,}\.?0*$", True),
                        (r"US,GS,\+0{3,}\.?0*$", True),
                        # เพิ่ม pattern สำหรับค่าติดลบที่ถูกตัดขาด
                        (r"ST,GS,-([0-9]+\.?[0-9]*)$", False),
                        (r"US,GS,-([0-9]+\.?[0-9]*)$", False),
                        (r"ST,GS,-0{3,}\.?0*$", True),
                        (r"US,GS,-0{3,}\.?0*$", True),
                        # เพิ่ม pattern สำหรับข้อมูลที่ถูกตัดขาดมาก
                        (r"ST,GS,-$", True),
                        (r"US,GS,-$", True),
                    ]
                    
                    for pattern_regex, is_zero_indicator in incomplete_patterns:
                        matches = re.findall(pattern_regex, cleaned_text)
                        if matches:
                            if is_zero_indicator:
                                weight_result = "0"
                                self.log_message(f"Found incomplete zero weight pattern: {cleaned_text}")
                                # ลบการบันทึกใน Local Database
                                return weight_result
                            else:
                                try:
                                    num_str_from_match = matches[0] if isinstance(matches[0], str) else matches[0][0]
                                    if '.' in num_str_from_match:
                                        weight_val = float(num_str_from_match)
                                    else:
                                        weight_val = float(int(num_str_from_match))
                                    
                                    # ใช้ความไวในการกรองข้อมูล
                                    sensitivity = float(self.sensitivity_var.get())
                                    if abs(weight_val) < sensitivity:
                                        weight_val = 0.0
                                    
                                    weight_result = str(weight_val)
                                    self.log_message(f"Found incomplete weight pattern: {cleaned_text} -> {weight_result}")
                                    # ลบการบันทึกใน Local Database
                                    return weight_result
                                except ValueError:
                                    pass
            
            return "N/A"
        except Exception as e:
            self.log_message(f"Parse error: {e}")
            return "N/A"

    # ลบ save_weight_locally และ send_offline_data_to_server functions

    # ลบ show_local_data_window function

    def read_weight_from_rs232(self):
        """อ่านน้ำหนักจาก RS232"""
        ser = self.get_serial_connection()
        if not ser:
            return self.last_weight
            
        try:
            # ตรวจสอบและจำกัดขนาด buffer เพื่อป้องกัน overflow
            if len(self.read_buffer) > 2000:  # เพิ่มขนาด buffer limit
                self.read_buffer = self.read_buffer[-1000:]  # เก็บข้อมูลล่าสุด 1000 bytes
                self.log_message("Buffer size limit reached, trimming...")
                
                # หลังจาก trim แล้ว ให้ประมวลผลข้อมูลใหม่
                try:
                    decoded_message = self.read_buffer.decode('latin-1', errors='ignore')
                    lines = []
                    for line in decoded_message.split('\r\n'):
                        lines.extend(line.split('\n'))
                    
                    # ประมวลผลบรรทัดสุดท้ายเพื่อหาน้ำหนักล่าสุด
                    for line in reversed(lines):
                        line = line.strip()
                        if line:
                            try:
                                parsed_value = self.parse_scale_data(line)
                                if parsed_value != "N/A":
                                                                                # ตรวจสอบว่าน้ำหนักเป็น 0 หรือไม่
                                            if parsed_value != "0" and parsed_value != "0.0":
                                                self.last_weight = parsed_value
                                                self.weight_label.config(text=f"⚖️ Weight: {parsed_value}")
                                                # ลดการ log เพื่อเพิ่มความเร็ว
                                                # self.log_message(f"Updated weight after buffer trim: {parsed_value}")
                                                break
                            except Exception as e:
                                continue
                except Exception as e:
                    self.log_message(f"Error processing trimmed buffer: {e}")
            
            # อ่านข้อมูลที่มีอยู่ใน buffer
            # ... existing code ...

            # อ่านข้อมูลที่มีอยู่ใน buffer
            if ser.in_waiting > 0:
                try:
                    new_bytes = ser.read(ser.in_waiting)
                    if new_bytes:
                        self.read_buffer += new_bytes
                        
                        # ส่งข้อมูลไปยัง real-time display
                        if self.realtime_monitoring_active:
                            self.add_realtime_data(new_bytes)
                        
                        # ประมวลผลข้อมูลใหม่ทันที
                        try:
                            decoded_new = new_bytes.decode('latin-1', errors='ignore')
                            lines = []
                            for line in decoded_new.split('\r\n'):
                                lines.extend(line.split('\n'))
                            
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
                                                # ลดการ log เพื่อเพิ่มความเร็ว
                                                # self.log_message(f"New weight from buffer: {parsed_value}")
                                    except Exception as e:
                                        continue
                        except Exception as e:
                            pass  # ไม่ log error สำหรับการประมวลผลข้อมูลใหม่
                        
                        # Log raw data for debugging (ลดความถี่)
                        if len(new_bytes) > 20:  # เพิ่มเงื่อนไขเพื่อลด log
                            self.log_message(f"Buffer data: {len(new_bytes)} bytes")
                except Exception as e:
                    self.log_message(f"Error reading buffer: {e}")

# ... existing code ...
            
            # ลองอ่านข้อมูลใหม่ (non-blocking read)
            try:
                # ใช้ timeout สั้นๆ เพื่อไม่ให้ block นาน
                original_timeout = ser.timeout
                ser.timeout = 0.01  # ลด timeout เป็น 10ms
                new_bytes = ser.read(100)  # เพิ่มจำนวน bytes ที่อ่าน
                if new_bytes:
                    self.read_buffer += new_bytes
                    
                    # ส่งข้อมูลไปยัง real-time display
                    if self.realtime_monitoring_active:
                        self.add_realtime_data(new_bytes)
                    
                    # ประมวลผลข้อมูลใหม่ทันที
                    try:
                        decoded_new = new_bytes.decode('latin-1', errors='ignore')
                        lines = []
                        for line in decoded_new.split('\r\n'):
                            lines.extend(line.split('\n'))
                        
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
                                            # ลดการ log เพื่อเพิ่มความเร็ว
                                            # self.log_message(f"New weight from timeout read: {parsed_value}")
                                except Exception as e:
                                    continue
                    except Exception as e:
                        pass  # ไม่ log error สำหรับการประมวลผลข้อมูลใหม่
                    
                    # Log raw data for debugging (ลดความถี่)
                    if len(new_bytes) > 5:
                        self.log_message(f"New data: {len(new_bytes)} bytes")
                ser.timeout = original_timeout
            except Exception as e:
                # ไม่มีข้อมูลใหม่ ไม่เป็นไร
                pass
            
            # Process buffer for complete messages
            if self.read_buffer:
                try:
                    decoded_message = self.read_buffer.decode('latin-1', errors='ignore')
                    
                    # แยกข้อมูลตามบรรทัด
                    lines = []
                    for line in decoded_message.split('\r\n'):
                        lines.extend(line.split('\n'))
                    
                    processed_lines = 0
                    last_processed_index = 0
                    
                    for i, line in enumerate(lines):
                        line = line.strip()
                        if line:  # ถ้ามีข้อมูลในบรรทัด
                            try:
                                parsed_value = self.parse_scale_data(line)
                                if parsed_value != "N/A":
                                    # ตรวจสอบว่าค่าใหม่แตกต่างจากค่าเดิมหรือไม่
                                    if parsed_value != self.last_weight:
                                        self.last_weight = parsed_value
                                        self.weight_label.config(text=f"⚖️ Weight: {parsed_value}")
                                        # ลดการ log เพื่อเพิ่มความเร็ว
                                        # self.log_message(f"New weight: {parsed_value} (from: {line})")
                                    processed_lines += 1
                                    last_processed_index = i
                            except Exception as e:
                                self.log_message(f"Error parsing line '{line}': {e}")
                    
                    # ล้าง buffer เฉพาะบรรทัดที่ประมวลผลแล้ว
                    if processed_lines > 0:
                        try:
                            # หาตำแหน่งของบรรทัดสุดท้ายที่ประมวลผล
                            processed_content = '\r\n'.join(lines[:last_processed_index + 1])
                            if processed_content:
                                # ลบข้อมูลที่ประมวลผลแล้วออกจาก buffer
                                remaining_content = decoded_message[len(processed_content):].lstrip('\r\n')
                                self.read_buffer = remaining_content.encode('latin-1', errors='ignore')
                                
                                # ตรวจสอบว่ามีข้อมูลใหม่เข้ามาหรือไม่
                                if len(self.read_buffer) > 0:
                                    self.log_message(f"Buffer cleared, remaining: {len(self.read_buffer)} bytes")
                        except Exception as e:
                            self.log_message(f"Error clearing buffer: {e}")
                            # ถ้าเกิดข้อผิดพลาด ให้ล้าง buffer ทั้งหมด
                            self.read_buffer = b''
                    
                    # ปรับปรุงการจัดการ buffer สำหรับข้อมูลที่ส่งมาอย่างต่อเนื่อง
                    if len(self.read_buffer) > 2000:  # เพิ่มขนาด buffer limit
                        # เก็บข้อมูลล่าสุด 1000 bytes แทนที่จะเป็น 500
                        self.read_buffer = self.read_buffer[-1000:]
                        self.log_message("Buffer trimmed due to size (increased limit)")
                        
                        # หลังจาก trim buffer แล้ว ให้ประมวลผลข้อมูลใหม่
                        try:
                            decoded_message = self.read_buffer.decode('latin-1', errors='ignore')
                            lines = []
                            for line in decoded_message.split('\r\n'):
                                lines.extend(line.split('\n'))
                            
                            # ประมวลผลบรรทัดสุดท้ายเพื่อหาน้ำหนักล่าสุด
                            for line in reversed(lines):
                                line = line.strip()
                                if line:
                                    try:
                                        parsed_value = self.parse_scale_data(line)
                                        if parsed_value != "N/A":
                                            # ตรวจสอบว่าน้ำหนักเป็น 0 หรือไม่
                                            if parsed_value != "0" and parsed_value != "0.0":
                                                self.last_weight = parsed_value
                                                self.weight_label.config(text=f"⚖️ Weight: {parsed_value}")
                                                # ลดการ log เพื่อเพิ่มความเร็ว
                                                # self.log_message(f"Updated weight after buffer trim: {parsed_value}")
                                                break
                                    except Exception as e:
                                        continue
                        except Exception as e:
                            self.log_message(f"Error processing trimmed buffer: {e}")
                        
                except Exception as e:
                    self.log_message(f"Buffer decode error: {e}")
                    # ถ้า decode ไม่ได้ ให้ล้าง buffer
                    self.read_buffer = b''
            
            return self.last_weight
        except Exception as e:
            self.log_message(f"Serial read error: {e}")
            # ถ้าเกิดข้อผิดพลาด ให้รีเซ็ตการเชื่อมต่อ
            try:
                if ser and ser.is_open:
                    ser.reset_input_buffer()
                    ser.reset_output_buffer()
                    self.read_buffer = b''
                    self.log_message("Serial buffers reset due to error")
            except Exception as reset_error:
                self.log_message(f"Error resetting serial buffers: {reset_error}")
            return "Error"

# ... existing code ...
    def start_client(self):
        """เริ่ม client"""
        try:
            # ตรวจสอบการเชื่อมต่อ Serial ก่อนเริ่ม
            if not self.test_connection_status():
                messagebox.showwarning("Warning", "Serial port is not available!\nPlease check your connection and settings.")
                return
                
            self.is_running = True
            self.start_btn.config(state='disabled')
            self.stop_btn.config(state='normal')
            
            # ลบ Local Web Server และ Local API Server
            
            # เริ่มเชื่อมต่อ WebSocket ไปยัง server ที่กำหนด
            try:
                server_url = self.server_url_var.get().strip()
                if not server_url:
                    messagebox.showerror("Error", "Please enter server URL!")
                    return
                    
                self.log_message(f"Connecting to WebSocket server: {server_url}")
                
                # เริ่ม thread สำหรับการทำงาน
                self.client_thread = threading.Thread(target=self.run_client_async, daemon=True)
                self.client_thread.start()
                
                self.log_message("Client started and connecting to server...")
                
            except Exception as e:
                self.log_message(f"Error starting client: {e}")
                messagebox.showerror("Error", f"Failed to start client: {e}")
                self.stop_client()
                
        except Exception as e:
            self.log_message(f"Start client error: {e}")
            messagebox.showerror("Error", f"Failed to start client: {e}")
            self.stop_client()

        
    def test_raw_reading(self):
        """ทดสอบการอ่านข้อมูล Raw"""
        try:
            self.log_message("=== Testing Raw Reading ===")
            
            ser = self.get_serial_connection()
            if not ser:
                self.log_message("❌ Serial connection not available!")
                return
            
            # ล้าง buffer
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            self.read_buffer = b''
            
            # อ่านข้อมูล 10 ครั้ง
            for i in range(10):
                try:
                    original_timeout = ser.timeout
                    ser.timeout = 0.5
                    
                    data = ser.read(100)
                    if data:
                        # ลบการแสดง Hex และ ASCII
                        self.log_message(f"Read {i+1}: {data.decode('latin-1', errors='ignore')}")
                        self.read_buffer += data
                    else:
                        self.log_message(f"Read {i+1}: No data")
                    
                    ser.timeout = original_timeout
                    time.sleep(0.2)
                    
                except Exception as e:
                    self.log_message(f"Read {i+1} error: {e}")
            
            self.log_message("=== Raw Reading Test Complete ===")
            
        except Exception as e:
            self.log_message(f"Raw reading test error: {e}")
                
    # ... existing code ...

    def stop_client(self):
        """หยุด client"""
        try:
            self.log_message("Stopping client...")
            
            self.is_running = False
            self.is_connected = False
            
            # ลบ Local Web Server และ Local API Server
            
            # หยุด real-time monitoring
            if self.realtime_monitoring_active:
                self.toggle_realtime_monitoring()
            
            # ปิดการเชื่อมต่อ Serial
            if self.serial_connection and self.serial_connection.is_open:
                try:
                    self.serial_connection.close()
                    self.log_message("Serial connection closed")
                except Exception as e:
                    self.log_message(f"Error closing serial connection: {e}")
                
            # ปิด WebSocket
            if self.websocket and self.loop:
                try:
                    # ส่ง task ไปยัง event loop เพื่อปิด WebSocket
                    future = asyncio.run_coroutine_threadsafe(self.close_websocket(), self.loop)
                    # รอให้ปิดเสร็จ (timeout 5 วินาที)
                    future.result(timeout=5)
                    self.log_message("WebSocket connection closed")
                except Exception as e:
                    self.log_message(f"WebSocket close error: {e}")
            
            # อัปเดต UI
            self.start_btn.config(state='normal')
            self.stop_btn.config(state='disabled')
            self.serial_status_label.config(text="🔴 Serial: Disconnected")
            self.server_status_label.config(text="🔴 Server: Disconnected", foreground='red')
            
            # ล้าง buffer
            self.read_buffer = b''
            
            self.log_message("Client stopped successfully")
        except Exception as e:
            self.log_message(f"Stop client error: {e}")
            # แม้เกิดข้อผิดพลาด ก็ต้องอัปเดตสถานะ
            self.is_running = False
            self.is_connected = False
            self.start_btn.config(state='normal')
            self.stop_btn.config(state='disabled')

# ... existing code ...
    
    def load_additional_config(self):
        """โหลด config เพิ่มเติมหลังจากสร้าง GUI แล้ว"""
        try:
            if hasattr(self, 'config_data'):
                # โหลด branch configuration
                if 'branch' in self.config_data:
                    try:
                        self.branch_var.set(self.config_data['branch'])
                        self.log_message(f"Loaded branch: {self.config_data['branch']}")
                    except Exception as e:
                        self.log_message(f"Error loading branch config: {e}")
                
                # โหลด scale pattern configuration
                if 'scale_pattern' in self.config_data:
                    try:
                        self.scale_pattern_var.set(self.config_data['scale_pattern'])
                        self.log_message(f"Loaded scale pattern: {self.config_data['scale_pattern']}")
                    except Exception as e:
                        self.log_message(f"Error loading scale pattern config: {e}")
                
                # โหลด custom pattern 3 configuration
                if 'custom_prefix' in self.config_data:
                    try:
                        self.custom_pattern_prefix_var.set(self.config_data['custom_prefix'])
                    except Exception as e:
                        self.log_message(f"Error loading custom prefix config: {e}")
                        
                if 'custom_regex' in self.config_data:
                    try:
                        self.custom_pattern_regex_var.set(self.config_data['custom_regex'])
                    except Exception as e:
                        self.log_message(f"Error loading custom regex config: {e}")
                        
                if 'custom_iszero' in self.config_data:
                    try:
                        self.custom_pattern_is_zero_var.set(self.config_data['custom_iszero'])
                    except Exception as e:
                        self.log_message(f"Error loading custom iszero config: {e}")
                
                self.log_message("Additional config loaded successfully")
                
                # อัปเดตการแสดงผล
                try:
                    self.update_branch_prefix_display()
                    self.update_scale_pattern_info()
                except Exception as e:
                    self.log_message(f"Error updating displays: {e}")
                
        except Exception as e:
            self.log_message(f"Error loading additional config: {e}")
    
    async def close_websocket(self):
        """ปิด WebSocket connection อย่างปลอดภัย"""
        try:
            if self.websocket and not self.websocket.closed:
                await self.websocket.close()
                self.websocket = None
        except Exception as e:
            self.log_message(f"Error in close_websocket: {e}")
            self.websocket = None
        
    def run_client_async(self):
        """รัน client ใน async loop"""
        try:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.loop.run_until_complete(self.client_main())
        except Exception as e:
            self.log_message(f"Client async error: {e}")
        
    async def client_main(self):
        """ฟังก์ชันหลักของ client"""
        reconnect_delay = 5  # เริ่มต้นรอ 5 วินาที
        max_reconnect_delay = 60  # สูงสุดรอ 60 วินาที
        
        while self.is_running:
            try:
                server_url = self.server_url_var.get()
                client_id = self.client_id_var.get()
                
                # ... existing code ...

                self.log_message(f"Connecting to server {server_url}")
                
                # สร้าง WebSocket connection
                websocket = await websockets.connect(server_url)
                self.websocket = websocket
                self.is_connected = True
                self.server_status_label.config(text="🟢 Server: Connected", foreground='green')
                self.log_message("Connected to server")
                
                # รีเซ็ต reconnect delay เมื่อเชื่อมต่อสำเร็จ
                reconnect_delay = 5
                
                # ล้าง buffer เก่าเมื่อ reconnect เพื่อไม่ให้ส่งข้อมูลเก่า
                if len(self.read_buffer) > 0:
                    self.log_message("Clearing old buffer after reconnect")
                    self.read_buffer = b''
                
                try:
                    # เริ่มการส่งข้อมูล
                    await self.send_weight_loop(client_id)
                except websockets.exceptions.ConnectionClosed:
                    self.log_message("WebSocket connection closed by server")
                except websockets.exceptions.ConnectionClosedOK:
                    self.log_message("WebSocket connection closed normally")
                except Exception as e:
                    self.log_message(f"Error in send_weight_loop: {e}")
                finally:
                    # ปิด WebSocket connection อย่างถูกต้อง
                    try:
                        await websocket.close()
                        self.log_message("WebSocket connection closed properly")
                    except Exception as e:
                        self.log_message(f"Error closing websocket: {e}")
                    
                    self.websocket = None
                    self.is_connected = False
                    self.server_status_label.config(text="🔴 Server: Disconnected", foreground='red')
                    
            except websockets.exceptions.InvalidURI:
                self.log_message(f"Invalid server URL: {server_url}")
                self.is_connected = False
                self.server_status_label.config(text="🔴 Server: Invalid URL", foreground='red')
                await asyncio.sleep(10)  # รอนานขึ้นสำหรับ URL ที่ผิด
                continue
                    
            except Exception as e:
                self.log_message(f"Connection error: {e}")
                self.is_connected = False
                self.server_status_label.config(text="🔴 Server: Disconnected", foreground='red')
            
            # รอก่อน reconnect
            if self.is_running:
                self.log_message(f"Reconnecting in {reconnect_delay} seconds...")
                await asyncio.sleep(reconnect_delay)
                
                # เพิ่ม delay แบบ exponential backoff
                reconnect_delay = min(reconnect_delay * 1.5, max_reconnect_delay)

# ... existing code ...
                
    async def send_weight_loop(self, client_id):
        """ลูปสำหรับส่งข้อมูลน้ำหนัก"""
        consecutive_errors = 0
        max_consecutive_errors = 5
        
        while self.is_running and self.is_connected:
            try:
                # ตรวจสอบว่า WebSocket ยังเชื่อมต่ออยู่หรือไม่
                if not self.websocket or self.websocket.closed:
                    self.log_message("WebSocket connection lost, breaking loop")
                    break
                
                weight = self.read_weight_from_rs232()
                
                # ตรวจสอบว่าค่าน้ำหนักถูกต้องหรือไม่
                if weight == "Error" or weight == "N/A":
                    consecutive_errors += 1
                    if consecutive_errors >= max_consecutive_errors:
                        self.log_message(f"Too many consecutive errors ({consecutive_errors}), reconnecting...")
                        break
                    await asyncio.sleep(1.0)  # รอเวลานานขึ้นเมื่อเกิด error
                    continue
                
                # รีเซ็ต error counter เมื่อได้ข้อมูลที่ถูกต้อง (รวมถึง 0)
                consecutive_errors = 0
                
                # ส่งข้อมูลเพิ่มเติมรวมถึง branch prefix และ scale pattern
                message = {
                    "client_id": client_id,
                    "weight": weight,
                    "timestamp": time.time(),
                    "branch": self.branch_var.get(),
                    "branch_prefix": self.get_branch_prefix(self.branch_var.get()),
                    "scale_pattern": self.scale_pattern_var.get()
                }
                
                # ส่งข้อมูลไปยัง Server โดยตรง
                try:
                    # ตรวจสอบ WebSocket state ก่อนส่ง
                    if self.websocket and not self.websocket.closed:
                        await self.websocket.send(json.dumps(message))
                        self.log_message(f"Sent weight {weight} to server (Branch: {self.branch_var.get()}, Pattern: {self.scale_pattern_var.get()})")
                    else:
                        self.log_message("WebSocket not available for sending")
                        break
                        
                except websockets.exceptions.ConnectionClosed:
                    self.log_message("WebSocket connection closed during send")
                    break
                except websockets.exceptions.ConnectionClosedOK:
                    self.log_message("WebSocket connection closed normally during send")
                    break
                except Exception as send_error:
                    self.log_message(f"Error sending to websocket: {send_error}")
                    consecutive_errors += 1
                    if consecutive_errors >= max_consecutive_errors:
                        self.log_message(f"Too many send errors ({consecutive_errors}), reconnecting...")
                        break
                
                await asyncio.sleep(0.1)  # ลด delay จาก 0.5 เป็น 0.1 วินาที
                
            except websockets.exceptions.ConnectionClosed:
                self.log_message("WebSocket connection closed in main loop")
                break
            except websockets.exceptions.ConnectionClosedOK:
                self.log_message("WebSocket connection closed normally in main loop")
                break
            except Exception as e:
                consecutive_errors += 1
                self.log_message(f"Error in send_weight_loop: {e}")
                
                if consecutive_errors >= max_consecutive_errors:
                    self.log_message(f"Too many consecutive errors ({consecutive_errors}), stopping client...")
                    break
                
                await asyncio.sleep(1.0)  # รอเวลานานขึ้นเมื่อเกิด error

# ... existing code ...

        
    def test_raw_data_display(self):
        """ทดสอบการแสดงข้อมูล Raw Data"""
        try:
            ser = self.get_serial_connection()
            if not ser:
                messagebox.showerror("Error", "Serial connection not available!")
                return
            
            self.log_message("=== Testing Raw Data Display ===")
            
            # ล้าง buffer ก่อน
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            self.read_buffer = b''
            
            # อ่านข้อมูล 5 ครั้ง
            for i in range(5):
                try:
                    # ตั้ง timeout สั้นๆ
                    original_timeout = ser.timeout
                    ser.timeout = 0.5
                    
                    # อ่านข้อมูล
                    data = ser.read(100)
                    if data:
                        # ลบการแสดง Hex และ ASCII
                        self.log_message(f"Read {i+1}: {data.decode('latin-1', errors='ignore')}")
                        
                        # เพิ่มข้อมูลลงใน buffer
                        self.read_buffer += data
                        
                        # ลอง decode และ parse
                        try:
                            decoded = self.read_buffer.decode('latin-1', errors='ignore')
                            self.log_message(f"Decoded: '{decoded}'")
                            
                            # แยกข้อมูลตามบรรทัด
                            lines = decoded.split('\r\n') + decoded.split('\n')
                            for line in lines:
                                line = line.strip()
                                if line:
                                    self.log_message(f"Processing line: '{line}'")
                                    parsed_value = self.parse_scale_data(line)
                                    self.log_message(f"Parsed result: {parsed_value}")
                                    
                                    # อัปเดต weight label
                                    if parsed_value != "N/A":
                                        self.last_weight = parsed_value
                                        self.weight_label.config(text=f"⚖️ Weight: {parsed_value}")
                                        self.log_message(f"Updated weight: {parsed_value}")
                        except Exception as e:
                            self.log_message(f"Parse error: {e}")
                    else:
                        self.log_message(f"Read {i+1}: No data")
                    
                    ser.timeout = original_timeout
                    time.sleep(0.2)  # รอ 200ms
                    
                except Exception as e:
                    self.log_message(f"Read {i+1} error: {e}")
            
            self.log_message("=== Raw Data Display Test Complete ===")
            
        except Exception as e:
            self.log_message(f"Test raw data display error: {e}")
            messagebox.showerror("Error", f"Test failed: {e}")

    def run(self):
        """เริ่มต้น GUI"""
        try:
            # ตั้งค่า protocol สำหรับการปิดโปรแกรม
            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
            
            self.log_message("RS232 Scale Client GUI started")
            self.root.mainloop()
        except Exception as e:
            print(f"GUI error: {e}")
    
    # ... existing code ...

    def on_closing(self):
        """เมื่อปิดโปรแกรม"""
        try:
            self.log_message("Shutting down application...")
            
            # หยุด client
            if self.is_running:
                self.stop_client()
            
            # หยุด tray icon
            if self.tray_icon:
                try:
                    self.tray_icon.stop()
                except Exception as e:
                    print(f"Error stopping tray icon: {e}")
            
            # ปิดการเชื่อมต่อ Serial
            if self.serial_connection:
                try:
                    self.serial_connection.close()
                except Exception as e:
                    print(f"Error closing serial connection: {e}")
            
            # ล้าง buffer
            self.read_buffer = b''
            
            # ปิดโปรแกรม
            try:
                self.root.destroy()
            except Exception as e:
                print(f"Error destroying root: {e}")
        except Exception as e:
            print(f"Closing error: {e}")
            try:
                self.root.destroy()
            except:
                pass

# ... existing code ...

    def open_frontend(self):
        """เปิดหน้าเว็บ Frontend"""
        try:
            # เปิด Frontend ปกติ
            self.log_message(f"Opening frontend: {FRONTEND_URL}")
            webbrowser.open(FRONTEND_URL)
            messagebox.showinfo("Frontend", f"Opening frontend in browser:\n{FRONTEND_URL}")
        except Exception as e:
            self.log_message(f"Error opening frontend: {e}")
            messagebox.showerror("Error", f"Failed to open frontend: {e}")
    
    def minimize_to_tray(self):
        """ซ่อนโปรแกรมลงใน Tray"""
        try:
            if not self.is_minimized_to_tray:
                # สร้าง icon สำหรับ tray
                self.create_tray_icon()
                
                # ซ่อนหน้าต่างหลัก
                self.root.withdraw()
                self.is_minimized_to_tray = True
                self.tray_btn.config(text="📌 Show Window")
                
                self.log_message("Application minimized to system tray")
                messagebox.showinfo("Tray", "Application minimized to system tray.\nRight-click tray icon to show window.")
            else:
                # แสดงหน้าต่างหลัก
                self.show_from_tray()
                
        except Exception as e:
            self.log_message(f"Error minimizing to tray: {e}")
            messagebox.showerror("Error", f"Failed to minimize to tray: {e}")
    
    def create_tray_icon(self):
        """สร้าง icon สำหรับ system tray"""
        try:
            # สร้าง icon ง่ายๆ จากข้อความ
            icon_image = Image.new('RGB', (64, 64), color='blue')
            
            # สร้าง menu สำหรับ tray
            menu = (
                item('Show Window', self.show_from_tray),
                item('Open Frontend', self.open_frontend),
                item('Start Client', self.start_client),
                item('Stop Client', self.stop_client),
                item('Exit', self.quit_application)
            )
            
            # สร้าง tray icon
            self.tray_icon = pystray.Icon("RS232 Scale Client", icon_image, "RS232 Scale Client", menu)
            
            # เริ่ม tray icon ใน thread แยก
            tray_thread = threading.Thread(target=self.tray_icon.run, daemon=True)
            tray_thread.start()
            
        except Exception as e:
            self.log_message(f"Error creating tray icon: {e}")
    
    def show_from_tray(self):
        """แสดงหน้าต่างหลักจาก tray"""
        try:
            if self.is_minimized_to_tray:
                self.root.deiconify()
                self.root.lift()
                self.root.focus_force()
                self.is_minimized_to_tray = False
                self.tray_btn.config(text="📌 Hide to Tray")
                
                # หยุด tray icon
                if self.tray_icon:
                    self.tray_icon.stop()
                    self.tray_icon = None
                
                self.log_message("Application restored from system tray")
        except Exception as e:
            self.log_message(f"Error showing from tray: {e}")
    
    def quit_application(self):
        """ปิดโปรแกรม"""
        try:
            # หยุด tray icon
            if self.tray_icon:
                try:
                    self.tray_icon.stop()
                except Exception as e:
                    print(f"Error stopping tray icon: {e}")
            
            # ปิดโปรแกรม
            self.on_closing()
        except Exception as e:
            self.log_message(f"Error quitting application: {e}")
            try:
                self.root.destroy()
            except:
                pass

    def show_main_help(self):
        """แสดงหน้าต่าง Help หลัก"""
        help_window = tk.Toplevel(self.root)
        help_window.title("❓ Help - RS232 Scale Client")
        help_window.geometry("700x500")
        help_window.configure(bg='#f0f0f0')
        
        # Make window modal
        help_window.transient(self.root)
        help_window.grab_set()
        
        # Main frame
        main_frame = ttk.Frame(help_window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="❓ วิธีใช้งาน RS232 Scale Client", 
                               font=('Tahoma', 14, 'bold'))
        title_label.pack(pady=(0, 15))
        
        # Help text
        help_text = scrolledtext.ScrolledText(main_frame, height=25, width=80, font=('Tahoma', 9))
        help_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        help_content = """❓ คู่มือการใช้งาน RS232 Scale Client

📋 ขั้นตอนการใช้งาน:

1️⃣ การตั้งค่า Serial Port:
   • Port: เลือกพอร์ตที่เชื่อมต่อกับตาชั่ง (COM1, COM2, etc.)
   •  Refresh: อัปเดตรายการพอร์ตที่ใช้งานได้
   • 🔍 Check: ตรวจสอบรายละเอียดพอร์ตทั้งหมด
   • Baud Rate: ความเร็วในการส่งข้อมูล (1200, 9600, etc.)
   • Parity: การตรวจสอบความถูกต้อง (N, E, O)
   • Stop Bits: บิตหยุด (1, 1.5, 2)
   • Byte Size: ขนาดข้อมูล (5, 6, 7, 8)
   • Timeout: เวลารอข้อมูล (วินาที)
   • Sensitivity: ความไวในการอ่านน้ำหนัก (kg)

2️⃣ การตั้งค่า Scale Pattern:
   • เลือก Pattern ที่ตรงกับรุ่นตาชั่ง
   • Default: สำหรับตาชั่งทั่วไป
   • CAS Scale: สำหรับตาชั่ง CAS
   • Mettler Toledo: สำหรับตาชั่ง Mettler Toledo
   • Sartorius: สำหรับตาชั่ง Sartorius
   • Custom Pattern 1-3: สำหรับ Pattern ที่กำหนดเอง

3️⃣ การตั้งค่า Custom Pattern 3:
   • Pattern Prefix: ชื่อของ Pattern (เช่น "1@H")
   • Regex Pattern: รูปแบบข้อมูล (เช่น "1@H\\s+(\\d+)")
   • Is Zero Indicator: ติ๊กถ้าเป็นสัญญาณน้ำหนัก 0
   • Update Custom Pattern: อัปเดต Pattern ที่กำหนดเอง
   • ❓ Help: ดูรายละเอียดการใช้งาน Custom Pattern

4️⃣ การตั้งค่าสาขา:
   • เลือกสาขาที่ใช้งาน
   • ระบบจะแสดง Prefix ที่ใช้ (Z1, Z2, etc.)
   • สาขาลพบุรีจะใช้ปี พ.ศ. 2 ตัวสุดท้าย

5️⃣ การตั้งค่า Server:
   • Server URL: ที่อยู่เซิร์ฟเวอร์ (ws://localhost:8765)
   • Client ID: รหัสประจำตัว Client

🔧 ปุ่มควบคุม:

• Test: ทดสอบการเชื่อมต่อ Serial Port
• Save: บันทึกการตั้งค่าทั้งหมด
• Start: เริ่มต้นการทำงาน Client
• Stop: หยุดการทำงาน Client
• 🌐 OPEN FRONTEND: เปิดหน้าเว็บ Frontend
• 📌 Hide to Tray: ซ่อนโปรแกรมลงใน System Tray
• ❓ Help: แสดงคู่มือการใช้งาน

🔍 Real-time RS232 Data Monitoring:

• ▶️ Start Monitoring: เริ่มการ monitor ข้อมูล real-time
• ⏸️ Stop Monitoring: หยุดการ monitor ข้อมูล real-time
• 🗑️ Clear Data: ล้างข้อมูล real-time
• Auto-scroll: เลื่อนหน้าจออัตโนมัติ
• Max lines: จำกัดจำนวนบรรทัดที่แสดง

📊 ข้อมูลที่แสดงใน Real-time:
• Timestamp: เวลาที่รับข้อมูล (แสดง milliseconds)
• HEX: ข้อมูลในรูปแบบ Hexadecimal
• ASCII: ข้อมูลในรูปแบบ ASCII (แสดง . สำหรับตัวอักษรที่ไม่แสดงผล)
• DEC: ข้อมูลในรูปแบบ Decimal
• Length: จำนวน bytes ที่รับได้

 การตรวจสอบสถานะ:

• 🔴 Serial: Disconnected - ไม่เชื่อมต่อ Serial
• 🟢 Serial: Connected - เชื่อมต่อ Serial แล้ว
• 🔴 Server: Disconnected - ไม่เชื่อมต่อ Server
• 🟢 Server: Connected - เชื่อมต่อ Server แล้ว
• ⚖️ Weight: แสดงน้ำหนักปัจจุบัน

📝 Activity Log:
• แสดงข้อมูลการทำงานทั้งหมด
• Raw data: ข้อมูลดิบจาก Serial
• Decoded message: ข้อมูลที่ถอดรหัสแล้ว
• Sent weight: น้ำหนักที่ส่งไป Server

⚠️ ข้อควรระวัง:
• ต้องรันเป็น Administrator หากมีปัญหา Permission
• ปิดโปรแกรมอื่นที่ใช้ Serial Port เดียวกัน
• ตรวจสอบการเชื่อมต่อ USB to Serial adapter
• ทดสอบการเชื่อมต่อก่อนใช้งานจริง

💡 เคล็ดลับ:
• ใช้ปุ่ม  Check เพื่อดูรายละเอียดพอร์ต
• ใช้ Real-time monitoring เพื่อดูข้อมูลดิบจากตาชั่ง
• ใช้ข้อมูล real-time เพื่อปรับแต่ง Scale Pattern
• บันทึกการตั้งค่าหลังจากทดสอบแล้ว
• ใช้ Custom Pattern 3 สำหรับตาชั่งที่ไม่รองรับ
• ใช้ Sensitivity เพื่อปรับความไวในการอ่านน้ำหนัก

🔗 การเชื่อมต่อ:
• Serial Port → ตาชั่ง
• WebSocket → Server
• ข้อมูลน้ำหนักจะถูกส่งไปยัง Server ทุก 0.5 วินาที
• Real-time monitoring อัปเดตทุก 100ms

🌐 System Tray:
• คลิกขวาที่ tray icon เพื่อดูเมนู
• เลือก "Show Window" เพื่อแสดงหน้าต่างหลัก
• เลือก "Open Frontend" เพื่อเปิดหน้าเว็บ
• เลือก "Exit" เพื่อปิดโปรแกรม"""
        
        help_text.insert(tk.END, help_content)
        help_text.config(state=tk.DISABLED)
        
        # Close button
        close_btn = ttk.Button(main_frame, text="ปิด", command=help_window.destroy, width=10)
        close_btn.pack(pady=(0, 5))
        
        # Center window
        help_window.update_idletasks()
        x = (help_window.winfo_screenwidth() // 2) - (help_window.winfo_width() // 2)
        y = (help_window.winfo_screenheight() // 2) - (help_window.winfo_height() // 2)
        help_window.geometry(f"+{x}+{y}")

# Class ที่เกี่ยวข้องกับ Offline Mode ถูกลบออกแล้ว - ตอนนี้ระบบทำงานแบบ Online เท่านั้น

if __name__ == '__main__':
    try:
        app = RS232ClientGUI()
        app.run()
    except Exception as e:
        print(f"Application error: {e}")