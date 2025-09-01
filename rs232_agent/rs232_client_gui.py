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
import sqlite3  # เพิ่ม import สำหรับ SQLite
import csv  # เพิ่ม import สำหรับ CSV export
from http.server import HTTPServer, BaseHTTPRequestHandler
import uuid  # เพิ่ม uuid สำหรับสร้าง ID ชั่วคราว

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
        self.root.geometry("1000x800")  # เพิ่มขนาดเพื่อรองรับ Offline Mode
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
        
        # เพิ่ม Local Data Manager
        self.local_data_manager = LocalDataManager()
        
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
        
        # เพิ่ม Local Web Server
        self.local_web_server = LocalWebServer(self)
        
        # สร้าง UI ก่อน
        self.setup_ui()
        self.update_available_ports()
        
        # เพิ่ม Offline Mode UI
        self.offline_ui = OfflineModeUI(self.root)
        
        # เพิ่ม Connection Monitor
        self.connection_monitor = ConnectionMonitor(self)
        
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
        
        refresh_btn = ttk.Button(port_frame, text="��", width=3, command=self.update_available_ports)
        refresh_btn.grid(row=0, column=1, padx=(0, 5))
        
        check_btn = ttk.Button(port_frame, text="��", width=3, command=self.check_ports)
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
        
        # Scale pattern info
        self.scale_pattern_info_label = ttk.Label(scale_frame, text="Patterns: 1CH, H, 1Rh, 1BH, 1@H", 
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
        
        # Client ID
        ttk.Label(server_frame, text="Client ID:", font=('Tahoma', 8)).grid(row=1, column=0, sticky=tk.W, padx=(0, 8))
        client_id_entry = ttk.Entry(server_frame, textvariable=self.client_id_var, width=15, font=('Tahoma', 8))
        client_id_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=3)
        
        # Control Buttons Frame
        control_frame = ttk.Frame(left_panel)
        control_frame.grid(row=5, column=0, columnspan=2, pady=(0, 8))
        
        self.test_btn = ttk.Button(control_frame, text="�� Test All", command=self.test_all_functions, width=10)
        self.test_btn.grid(row=0, column=0, padx=(0, 5))
        
        self.save_btn = ttk.Button(control_frame, text="Save", command=self.save_configuration, width=8)
        self.save_btn.grid(row=0, column=1, padx=(0, 5))
        
        self.start_btn = ttk.Button(control_frame, text="Start", command=self.start_client, width=8)
        self.start_btn.grid(row=0, column=2, padx=(0, 5))
        
        self.stop_btn = ttk.Button(control_frame, text="Stop", command=self.stop_client, state='disabled', width=8)
        self.stop_btn.grid(row=0, column=3)
        
        # Help Button
        help_btn = ttk.Button(control_frame, text="❓ Help", command=self.show_main_help, width=8)
        help_btn.grid(row=0, column=4, padx=(5, 0))

        debug_btn = ttk.Button(control_frame, text="🐛 Debug", command=self.debug_serial_reading, width=8)
        debug_btn.grid(row=0, column=5, padx=(5, 0))
        
        pattern_test_btn = ttk.Button(control_frame, text="🔍 Test Pattern", command=self.test_pattern_parsing, width=10)
        pattern_test_btn.grid(row=0, column=6, padx=(5, 0))
        
        # Frontend and Tray Buttons Frame
        frontend_tray_frame = ttk.Frame(left_panel)
        frontend_tray_frame.grid(row=6, column=0, columnspan=2, pady=(0, 8))
        
        # Frontend Button - ใหญ่และชัดเจน
        self.frontend_btn = ttk.Button(frontend_tray_frame, text="🌐 OPEN FRONTEND", 
                                      command=self.open_frontend, width=20, 
                                      style='Accent.TButton')
        self.frontend_btn.grid(row=0, column=0, padx=(0, 10))
        
        # Tray Button
        self.tray_btn = ttk.Button(frontend_tray_frame, text="📌 Hide to Tray", 
                                  command=self.minimize_to_tray, width=12)
        self.tray_btn.grid(row=0, column=1)

        # Config Path Note
        config_abs_path = os.path.abspath(CLIENT_CONFIG_FILE)
        config_note_label = ttk.Label(left_panel, 
                                     text=f"Config: {os.path.basename(config_abs_path)}", 
                                     font=('Tahoma', 7), 
                                     foreground='gray')
        config_note_label.grid(row=7, column=0, columnspan=2, sticky=tk.W, pady=(0, 5))
        
        # Right Panel - Status & Monitoring
        right_panel = ttk.Frame(main_frame)
        right_panel.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(5, 0))
        right_panel.columnconfigure(0, weight=1)
        right_panel.rowconfigure(1, weight=1)
        right_panel.rowconfigure(2, weight=1)  # เพิ่ม weight สำหรับ real-time frame
        main_frame.rowconfigure(1, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # Status Frame
        status_frame = ttk.LabelFrame(right_panel, text="Status & Monitoring", padding="8")
        status_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 8))
        status_frame.columnconfigure(0, weight=1)
        status_frame.rowconfigure(1, weight=1)
        
        # Status indicators
        status_indicators_frame = ttk.Frame(status_frame)
        status_indicators_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 8))
        
        # Serial status
        self.serial_status_label = ttk.Label(status_indicators_frame, text="🔴 Serial: Disconnected", 
                                            font=('Tahoma', 9, 'bold'))
        self.serial_status_label.grid(row=0, column=0, padx=(0, 15))
        
        # Server status
        self.server_status_label = ttk.Label(status_indicators_frame, text="🔴 Server: Disconnected", 
                                            font=('Tahoma', 9, 'bold'))
        self.server_status_label.grid(row=0, column=1, padx=(0, 15))
        
        # Current weight
        self.weight_label = ttk.Label(status_indicators_frame, text="⚖️ Weight: 0 kg", 
                                    font=('Tahoma', 11, 'bold'))
        self.weight_label.grid(row=0, column=2)
        
        # Log area
        log_frame = ttk.Frame(status_frame)
        log_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
        ttk.Label(log_frame, text="Activity Log:", font=('Tahoma', 8)).grid(row=0, column=0, sticky=tk.W, pady=(0, 3))
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=12, width=50, font=('Tahoma', 8))
        self.log_text.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Clear log button
        clear_log_btn = ttk.Button(log_frame, text="Clear Log", command=self.clear_log, width=10)
        clear_log_btn.grid(row=2, column=0, pady=(3, 0))
        
        # Real-time RS232 Data Display Frame
        realtime_frame = ttk.LabelFrame(status_frame, text="🔍 Real-time RS232 Data", padding="8")
        realtime_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(8, 0))
        realtime_frame.columnconfigure(0, weight=1)
        realtime_frame.rowconfigure(1, weight=1)
        realtime_frame.rowconfigure(2, weight=0)  # info label ไม่ขยาย
        
        # Real-time data controls
        realtime_controls_frame = ttk.Frame(realtime_frame)
        realtime_controls_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        
        # Start/Stop real-time monitoring button
        self.realtime_monitor_var = tk.BooleanVar(value=False)
        self.realtime_monitor_btn = ttk.Button(realtime_controls_frame, text="▶️ Start Monitoring", 
                                             command=self.toggle_realtime_monitoring, width=10)
        self.realtime_monitor_btn.grid(row=0, column=0, padx=(0, 3))
        
        # Clear real-time data button
        clear_realtime_btn = ttk.Button(realtime_controls_frame, text="🗑️ Clear Data", 
                                      command=self.clear_realtime_data, width=12)
        clear_realtime_btn.grid(row=0, column=1, padx=(0, 5))
        
        # Auto-scroll checkbox
        self.auto_scroll_var = tk.BooleanVar(value=True)
        auto_scroll_check = ttk.Checkbutton(realtime_controls_frame, text="Auto-scroll", 
                                           variable=self.auto_scroll_var)
        auto_scroll_check.grid(row=0, column=2, padx=(0, 5))
        
        # Max lines display
        ttk.Label(realtime_controls_frame, text="Max lines:", font=('Tahoma', 7)).grid(row=0, column=3, padx=(0, 2))
        self.max_lines_var = tk.StringVar(value="100")
        max_lines_spinbox = ttk.Spinbox(realtime_controls_frame, from_=10, to=1000, 
                                       textvariable=self.max_lines_var, width=8, font=('Tahoma', 7))
        max_lines_spinbox.grid(row=0, column=4, padx=(0, 5))
        
        # Export button
        export_btn = ttk.Button(realtime_controls_frame, text="📁 Export", 
                               command=self.export_realtime_data, width=10)
        export_btn.grid(row=0, column=5)
        
        # Bind events
        max_lines_spinbox.bind('<KeyRelease>', self.on_max_lines_change)
        max_lines_spinbox.bind('<<Increment>>', self.on_max_lines_change)
        max_lines_spinbox.bind('<<Decrement>>', self.on_max_lines_change)
        auto_scroll_check.bind('<Button-1>', self.on_auto_scroll_change)
        
        # Real-time data display
        self.realtime_text = scrolledtext.ScrolledText(realtime_frame, height=23, width=50, 
                                                     font=('Consolas', 8), bg='#1e1e1e', fg='#00ff00')
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
        """อัปเดตการแสดงข้อมูล Scale Pattern"""
        selected_pattern = self.scale_pattern_var.get()
        if selected_pattern in SCALE_PATTERNS:
            patterns = SCALE_PATTERNS[selected_pattern]
            if patterns:
                pattern_names = [pattern[0] for pattern in patterns]
                self.scale_pattern_info_label.config(text=f"Patterns: {', '.join(pattern_names)}")
            else:
                self.scale_pattern_info_label.config(text="Patterns: None (Custom Pattern 3)")
        
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
                # ตรวจสอบการเชื่อมต่อ Serial ก่อน
                ser = self.get_serial_connection()
                if not ser:
                    messagebox.showwarning("Warning", "Serial connection not available!\nPlease check your connection first.")
                    return
                
                # เริ่มการ monitor
                self.realtime_monitoring_active = True
                self.realtime_monitor_var.set(True)
                self.realtime_monitor_btn.config(text="⏸️ Stop Monitoring")
                self.realtime_info_label.config(text="📊 Monitoring RS232 data in real-time...", foreground='green')
                self.log_message("Real-time monitoring started")
                
                # เริ่ม timer สำหรับอ่านข้อมูลและอัปเดตการแสดงผล
                self.start_realtime_reading()
            else:
                # หยุดการ monitor
                self.realtime_monitoring_active = False
                self.realtime_monitor_var.set(False)
                self.realtime_monitor_btn.config(text="▶️ Start Monitoring")
                self.realtime_info_label.config(text="📊 Real-time monitoring stopped", foreground='gray')
                self.log_message("Real-time monitoring stopped")
                
                # หยุด timer
                if self.realtime_update_timer:
                    self.root.after_cancel(self.realtime_update_timer)
                    self.realtime_update_timer = None
        except Exception as e:
            self.log_message(f"Toggle real-time monitoring error: {e}")

    def start_realtime_reading(self):
        """เริ่มการอ่านข้อมูล real-time"""
        try:
            if not self.realtime_monitoring_active:
                return
                
            ser = self.get_serial_connection()
            if ser:
                # อ่านข้อมูลที่มีอยู่ใน buffer
                if ser.in_waiting > 0:
                    new_bytes = ser.read(ser.in_waiting)
                    if new_bytes:
                        self.add_realtime_data(new_bytes)
                        # ลบการแสดง Hex และ ASCII
                        self.log_message(f"Real-time data: {new_bytes.decode('latin-1', errors='ignore')}")
                
                # ลองอ่านข้อมูลใหม่
                try:
                    original_timeout = ser.timeout
                    ser.timeout = 0.1  # 100ms timeout
                    new_bytes = ser.read(100)
                    if new_bytes:
                        self.add_realtime_data(new_bytes)
                        # ลบการแสดง Hex และ ASCII
                        self.log_message(f"New real-time data: {new_bytes.decode('latin-1', errors='ignore')}")
                    ser.timeout = original_timeout
                except Exception as e:
                    # ไม่มีข้อมูลใหม่ ไม่เป็นไร
                    pass
            
            # ตั้งเวลาเรียกฟังก์ชันนี้อีกครั้ง (ทุก 200ms)
            self.realtime_update_timer = self.root.after(200, self.start_realtime_reading)
            
        except Exception as e:
            self.log_message(f"Real-time reading error: {e}")
            # ตั้งเวลาเรียกฟังก์ชันนี้อีกครั้งแม้เกิดข้อผิดพลาด
            self.realtime_update_timer = self.root.after(200, self.start_realtime_reading)

        
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
                                
                                # จัดการค่าติดลบ - ถ้าเป็นค่าติดลบเล็กน้อย ให้ถือเป็น 0
                                if weight_val < 0:
                                    if abs(weight_val) < 0.1:  # ค่าติดลบน้อยกว่า 0.1 kg
                                        weight_val = 0.0
                                    else:
                                        # ค่าติดลบที่มากกว่า ให้ใช้ค่าสัมบูรณ์
                                        weight_val = abs(weight_val)
                                
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
                    # บันทึกใน Local Database
                    self.save_weight_locally(weight_result)
                    return weight_result
                elif "0" in extracted_weight_values or "0.0" in extracted_weight_values:
                    weight_result = "0"
                    # บันทึกใน Local Database
                    self.save_weight_locally(weight_result)
                    return weight_result
            return "N/A"
        except Exception as e:
            self.log_message(f"Parse error: {e}")
            return "N/A"

    def save_weight_locally(self, weight):
        """บันทึกน้ำหนักใน Local Database"""
        try:
            record_id = self.local_data_manager.save_weight_locally(
                weight, 
                "local",
                self.branch_var.get(),
                self.scale_pattern_var.get()
            )
            if record_id:
                # อัปเดต Local UI
                self.offline_ui.update_local_data_display()
        except Exception as e:
            self.log_message(f"Error saving weight locally: {e}")

    def send_offline_data_to_server(self, record):
        """ส่งข้อมูลจาก Local ไป Server"""
        try:
            if self.websocket and not self.websocket.closed:
                message = {
                    "client_id": self.client_id_var.get(),
                    "weight": str(record[1]),  # weight
                    "timestamp": time.time(),
                    "branch": record[4] if record[4] else self.branch_var.get(),
                    "branch_prefix": self.get_branch_prefix(record[4] if record[4] else self.branch_var.get()),
                    "scale_pattern": record[5] if record[5] else self.scale_pattern_var.get(),
                    "offline_sync": True  # แสดงว่าเป็นข้อมูลจาก offline sync
                }
                
                # ส่งข้อมูลแบบ async
                asyncio.run_coroutine_threadsafe(
                    self.websocket.send(json.dumps(message)), 
                    self.loop
                )
                
                # ทำเครื่องหมายว่า sync แล้ว
                self.local_data_manager.mark_as_synced(record[0])
                
                # อัปเดต Local UI
                self.offline_ui.update_local_data_display()
                
                self.log_message(f"Synced offline data: {record[1]} kg")
                
        except Exception as e:
            self.log_message(f"Error syncing offline data: {e}")

    def show_local_data_window(self):
        """แสดงหน้าต่างข้อมูล Local"""
        try:
            # สร้างหน้าต่างใหม่
            local_window = tk.Toplevel(self.root)
            local_window.title("Local Weight Data")
            local_window.geometry("800x600")
            
            # สร้าง Treeview สำหรับแสดงข้อมูล
            columns = ('ID', 'Weight', 'Timestamp', 'Status', 'Branch', 'Scale Pattern', 'Synced')
            tree = ttk.Treeview(local_window, columns=columns, show='headings')
            
            # กำหนดหัวข้อคอลัมน์
            for col in columns:
                tree.heading(col, text=col)
                tree.column(col, width=100)
            
            # ดึงข้อมูลจาก Local Database
            conn = sqlite3.connect(self.local_data_manager.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, weight, timestamp, status, branch, scale_pattern, synced
                FROM weight_records
                ORDER BY timestamp DESC
                LIMIT 100
            ''')
            
            data = cursor.fetchall()
            conn.close()
            
            # เพิ่มข้อมูลใน Treeview
            for row in data:
                synced_text = "Yes" if row[6] else "No"
                tree.insert('', 'end', values=(row[0], row[1], row[2], row[3], row[4], row[5], synced_text))
            
            # เพิ่ม Scrollbar
            scrollbar = ttk.Scrollbar(local_window, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)
            
            # จัดวาง
            tree.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            
            # แสดงจำนวนข้อมูล
            info_label = ttk.Label(local_window, text=f"Showing {len(data)} records")
            info_label.pack(pady=5)
            
        except Exception as e:
            self.log_message(f"Error showing local data window: {e}")
            messagebox.showerror("Error", f"Error showing local data: {e}")

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
                    
                    # ถ้า buffer ใหญ่เกินไป ให้ล้างบางส่วน
                    if len(self.read_buffer) > 1500:
                        # เก็บข้อมูลล่าสุด 500 bytes
                        self.read_buffer = self.read_buffer[-500:]
                        self.log_message("Buffer trimmed due to size")
                        
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
        """เริ่มต้น client"""
        if self.is_running:
            return
            
        # ตรวจสอบการเชื่อมต่อ Serial ก่อนเริ่ม
        if not self.test_connection_status():
            messagebox.showwarning("Warning", "Serial port is not available!\nPlease check your connection and settings.")
            return
            
        self.is_running = True
        self.start_btn.config(state='disabled')
        self.stop_btn.config(state='normal')
        
        # เริ่ม Local Web Server
        self.local_web_server.start_server()
        
        # เริ่ม Local API Server
        self.local_api_server.start_server()
        
        # เริ่ม thread สำหรับการทำงาน
        self.client_thread = threading.Thread(target=self.run_client_async, daemon=True)
        self.client_thread.start()
        
        self.log_message("Client started")

        
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
            
            # หยุด Local Web Server
            self.local_web_server.stop_server()
            
            # หยุด Local API Server
            self.local_api_server.stop_server()
            
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
            self.server_status_label.config(text="🔴 Server: Disconnected")
            
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
                self.server_status_label.config(text="🟢 Server: Connected")
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
                    self.server_status_label.config(text="🔴 Server: Disconnected")
                    
            except websockets.exceptions.InvalidURI:
                self.log_message(f"Invalid server URL: {server_url}")
                self.is_connected = False
                self.server_status_label.config(text="🔴 Server: Invalid URL")
                await asyncio.sleep(10)  # รอนานขึ้นสำหรับ URL ที่ผิด
                continue
                    
            except Exception as e:
                self.log_message(f"Connection error: {e}")
                self.is_connected = False
                self.server_status_label.config(text="🔴 Server: Disconnected")
            
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
                
                # ตรวจสอบว่าน้ำหนักเป็น 0 หรือไม่ และไม่ส่งซ้ำ
                if weight == "0" or weight == "0.0":
                    # ถ้าน้ำหนักเป็น 0 ให้รอข้อมูลใหม่
                    await asyncio.sleep(0.1)  # ลด delay จาก 0.5 เป็น 0.1 วินาที
                    continue
                
                # รีเซ็ต error counter เมื่อสำเร็จ
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
                
                # ... existing code ...

                try:
                    # ตรวจสอบ WebSocket state ก่อนส่ง
                    if self.websocket and not self.websocket.closed:
                        await self.websocket.send(json.dumps(message))
                        self.log_message(f"Sent weight: {weight} (Branch: {self.branch_var.get()}, Pattern: {self.scale_pattern_var.get()})")
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
            # ตรวจสอบสถานะการเชื่อมต่อ
            if self.is_offline_mode:
                # เปิด Local Dashboard
                local_url = f"http://localhost:{self.local_web_server.port}"
                self.log_message(f"Opening local dashboard: {local_url}")
                webbrowser.open(local_url)
                messagebox.showinfo("Local Dashboard", f"Opening local dashboard:\n{local_url}\n\nThis shows data from local storage.")
            else:
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

# เพิ่ม Local Data Manager Class
class LocalDataManager:
    def __init__(self, db_path='local_weight_data.db'):
        self.db_path = db_path
        self.conn = None
        self.connect()
        self.create_tables()

    def connect(self):
        """เชื่อมต่อฐานข้อมูล SQLite"""
        try:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row # ทำให้เข้าถึงคอลัมน์ด้วยชื่อได้
        except Exception as e:
            print(f"Error connecting to local DB: {e}")

    def create_tables(self):
        """สร้างตารางถ้ายังไม่มี"""
        try:
            cursor = self.conn.cursor()
            # ตารางสำหรับเก็บข้อมูลน้ำหนัก (ตารางเดิม)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS weight_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    weight TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    status TEXT,
                    branch TEXT,
                    scale_pattern TEXT,
                    synced BOOLEAN DEFAULT 0
                )
            ''')
            
            # --- เพิ่มตารางใหม่สำหรับ Tickets ---
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tickets (
                    WE_ID TEXT PRIMARY KEY,
                    WE_LICENSE TEXT,
                    WE_WEIGHTIN REAL,
                    WE_WEIGHTOUT REAL,
                    WE_TIMEIN TEXT,
                    WE_TIMEOUT TEXT,
                    WE_DATE TEXT,
                    WE_VENDOR_CD TEXT,
                    WE_VENDOR TEXT,
                    WE_DIREF TEXT,
                    WE_MAT_CD TEXT,
                    WE_MAT TEXT,
                    WE_QTY REAL,
                    WE_UOM TEXT,
                    WE_DRIVER TEXT,
                    WE_TRUCK_CHAR TEXT,
                    WE_WEIGHTMINUS REAL,
                    WE_WEIGHTIN_ORI REAL,
                    WE_WEIGHTOUT_ORI REAL,
                    WE_WEIGHTTOT REAL,
                    WE_WEIGHTNET REAL,
                    sync_status TEXT DEFAULT 'new', -- 'new', 'updated', 'synced'
                    server_id TEXT -- เอาไว้เก็บ ID จริงจาก Server หลัง Sync
                )
            ''')

            # --- เพิ่มตารางใหม่สำหรับ Ticket Items ---
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ticket_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_id TEXT,
                    VBELN TEXT,
                    POSNR TEXT,
                    WE_MAT_CD TEXT,
                    WE_MAT TEXT,
                    WE_QTY REAL,
                    WE_UOM TEXT,
                    FOREIGN KEY(ticket_id) REFERENCES tickets(WE_ID)
                )
            ''')

            self.conn.commit()
        except Exception as e:
            print(f"Error creating tables: {e}")

    def save_weight_locally(self, weight, status="local", branch="", scale_pattern=""):
        """บันทึกน้ำหนักใน Local Database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO weight_records (weight, status, synced, branch, scale_pattern)
                VALUES (?, ?, 0, ?, ?)
            ''', (weight, status, branch, scale_pattern))
            conn.commit()
            conn.close()
            return cursor.lastrowid
        except Exception as e:
            print(f"Error saving weight locally: {e}")
            return None
    
    def get_unsynced_data(self):
        """ดึงข้อมูลที่ยังไม่ได้ sync"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, weight, timestamp, status, branch, scale_pattern
                FROM weight_records 
                WHERE synced = 0 
                ORDER BY timestamp
            ''')
            data = cursor.fetchall()
            conn.close()
            return data
        except Exception as e:
            print(f"Error getting unsynced data: {e}")
            return []
    
    def mark_as_synced(self, record_id):
        """ทำเครื่องหมายว่า sync แล้ว"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE weight_records 
                SET synced = 1 
                WHERE id = ?
            ''', (record_id,))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error marking as synced: {e}")
    
    def get_local_stats(self):
        """ดึงสถิติข้อมูล Local"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # นับจำนวนทั้งหมด
            cursor.execute('SELECT COUNT(*) FROM weight_records')
            total_records = cursor.fetchone()[0]
            
            # นับจำนวนที่ sync แล้ว
            cursor.execute('SELECT COUNT(*) FROM weight_records WHERE synced = 1')
            synced_records = cursor.fetchone()[0]
            
            # นับจำนวนที่ยังไม่ได้ sync
            cursor.execute('SELECT COUNT(*) FROM weight_records WHERE synced = 0')
            unsynced_records = cursor.fetchone()[0]
            
            conn.close()
            
            return {
                'total': total_records,
                'synced': synced_records,
                'unsynced': unsynced_records
            }
        except Exception as e:
            print(f"Error getting local stats: {e}")
            return {'total': 0, 'synced': 0, 'unsynced': 0}
    
    def export_to_csv(self, filename, start_date=None, end_date=None):
        """Export ข้อมูลเป็น CSV"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if start_date and end_date:
                cursor.execute('''
                    SELECT weight, timestamp, status, branch, scale_pattern
                    FROM weight_records
                    WHERE timestamp BETWEEN ? AND ?
                    ORDER BY timestamp
                ''', (start_date, end_date))
            else:
                cursor.execute('''
                    SELECT weight, timestamp, status, branch, scale_pattern
                    FROM weight_records
                    ORDER BY timestamp
                ''')
            
            data = cursor.fetchall()
            conn.close()
            
            with open(filename, 'w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow(['Weight', 'Timestamp', 'Status', 'Branch', 'Scale Pattern'])
                writer.writerows(data)
            
            return len(data)
        except Exception as e:
            print(f"Error exporting to CSV: {e}")
            return 0

    # --- START: ฟังก์ชันใหม่สำหรับจัดการ Ticket ใน Local DB ---
    def generate_local_ticket_id(self):
        """สร้าง ID ชั่วคราวสำหรับบัตรชั่งที่สร้างตอน Offline"""
        return f"LOCAL-{uuid.uuid4()}"

    def dict_factory(self, cursor, row):
        """แปลงผลลัพธ์จาก DB เป็น Dictionary"""
        d = {}
        for idx, col in enumerate(cursor.description):
            d[col[0]] = row[idx]
        return d

    def get_local_tickets(self, completed=False):
        """ดึงข้อมูลบัตรชั่งจาก Local DB"""
        tickets_list = []
        try:
            # self.conn.row_factory = self.dict_factory # ใช้ row_factory ที่ตั้งไว้ตอน connect แล้ว
            cursor = self.conn.cursor()
            
            if completed:
                cursor.execute("SELECT * FROM tickets WHERE WE_WEIGHTOUT IS NOT NULL AND WE_WEIGHTOUT > 0 ORDER BY WE_TIMEOUT DESC")
            else:
                cursor.execute("SELECT * FROM tickets WHERE WE_WEIGHTOUT IS NULL OR WE_WEIGHTOUT = 0 ORDER BY WE_TIMEIN DESC")
            
            tickets = cursor.fetchall()
            
            for ticket_row in tickets:
                ticket_dict = dict(ticket_row)
                
                # ดึงรายการ items ของแต่ละ ticket
                item_cursor = self.conn.cursor()
                item_cursor.execute("SELECT * FROM ticket_items WHERE ticket_id = ?", (ticket_dict['WE_ID'],))
                items = item_cursor.fetchall()
                ticket_dict['items'] = [dict(item) for item in items]
                tickets_list.append(ticket_dict)
                
        except Exception as e:
            print(f"Error getting local tickets: {e}")
        return tickets_list

    def create_local_ticket(self, ticket_data):
        """สร้างบัตรชั่งใหม่ใน Local DB"""
        local_id = self.generate_local_ticket_id()
        try:
            cursor = self.conn.cursor()
            
            query = """
                INSERT INTO tickets (
                    WE_ID, WE_LICENSE, WE_WEIGHTIN, WE_TIMEIN, WE_DATE,
                    WE_VENDOR_CD, WE_VENDOR, WE_DIREF, WE_MAT_CD, WE_MAT, WE_QTY, WE_UOM,
                    WE_DRIVER, WE_TRUCK_CHAR, WE_WEIGHTMINUS, WE_WEIGHTIN_ORI, sync_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            current_time = datetime.now()
            
            params = (
                local_id,
                ticket_data.get('WE_LICENSE'),
                ticket_data.get('WE_WEIGHTIN'),
                current_time.strftime("%Y-%m-%d %H:%M:%S"),
                current_time.strftime("%Y-%m-%d"),
                ticket_data.get('WE_VENDOR_CD'),
                ticket_data.get('WE_VENDOR'),
                ticket_data.get('WE_DIREF'),
                ticket_data.get('WE_MAT_CD'),
                ticket_data.get('WE_MAT'),
                ticket_data.get('WE_QTY'),
                ticket_data.get('WE_UOM'),
                ticket_data.get('WE_DRIVER'),
                ticket_data.get('WE_TRUCK_CHAR'),
                ticket_data.get('WE_WEIGHTMINUS'),
                ticket_data.get('WE_WEIGHTIN_ORI'),
                'new'
            )
            
            cursor.execute(query, params)
            
            # จัดการ items ถ้ามี
            items = ticket_data.get('items', [])
            if items:
                for item in items:
                    item_query = """
                        INSERT INTO ticket_items (ticket_id, VBELN, POSNR, WE_MAT_CD, WE_MAT, WE_QTY, WE_UOM)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """
                    item_params = (
                        local_id,
                        item.get('VBELN'),
                        item.get('POSNR'),
                        item.get('WE_MAT_CD'),
                        item.get('WE_MAT'),
                        item.get('WE_QTY'),
                        item.get('WE_UOM')
                    )
                    cursor.execute(item_query, item_params)
            
            self.conn.commit()
            return self.get_local_ticket_by_id(local_id)
        except Exception as e:
            print(f"Error creating local ticket: {e}")
            return None

    def update_local_ticket_weigh_out(self, ticket_id, weigh_out_data):
        """อัปเดตการชั่งออกใน Local DB"""
        try:
            cursor = self.conn.cursor()

            # 1. ดึงข้อมูลน้ำหนักเข้ามาก่อน
            cursor.execute("SELECT WE_WEIGHTIN, WE_WEIGHTMINUS FROM tickets WHERE WE_ID = ?", (ticket_id,))
            ticket = cursor.fetchone()
            if not ticket:
                return None

            weight_in = ticket['WE_WEIGHTIN']
            weight_out = weigh_out_data.get('WE_WEIGHTOUT')
            
            # 2. คำนวณค่าน้ำหนักต่างๆ
            weight_before_deduction = abs(weight_in - weight_out)
            weight_deduction = ticket['WE_WEIGHTMINUS'] or 0
            net_weight = weight_before_deduction - weight_deduction

            # 3. อัปเดตข้อมูล
            query = """
                UPDATE tickets SET
                    WE_WEIGHTOUT = ?,
                    WE_TIMEOUT = ?,
                    WE_WEIGHTOUT_ORI = ?,
                    WE_WEIGHTTOT = ?,
                    WE_WEIGHTNET = ?,
                    sync_status = 'updated'
                WHERE WE_ID = ? AND (sync_status = 'synced' OR sync_status = 'updated')
            """ # อัปเดตเฉพาะอันที่เคย sync แล้ว
            
            params = (
                weight_out,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                weight_out, # WE_WEIGHTOUT_ORI
                weight_before_deduction, # WE_WEIGHTTOT
                net_weight, # WE_WEIGHTNET
                ticket_id
            )
            
            cursor.execute(query, params)
            self.conn.commit()
            
            return self.get_local_ticket_by_id(ticket_id)
        except Exception as e:
            print(f"Error updating local ticket weigh out: {e}")
            return None

    def get_local_ticket_by_id(self, ticket_id):
        """ดึงข้อมูลบัตรชั่งใบเดียวจาก Local DB"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM tickets WHERE WE_ID = ?", (ticket_id,))
            ticket_row = cursor.fetchone()
            if not ticket_row:
                return None
            
            ticket_dict = dict(ticket_row)
            
            # ดึง items
            item_cursor = self.conn.cursor()
            item_cursor.execute("SELECT * FROM ticket_items WHERE ticket_id = ?", (ticket_id,))
            items = item_cursor.fetchall()
            ticket_dict['items'] = [dict(item) for item in items]
            
            return ticket_dict
        except Exception as e:
            print(f"Error getting local ticket by id: {e}")
            return None

    def mark_ticket_as_synced(self, local_id, server_id):
        """อัปเดตสถานะบัตรชั่งใน Local DB ว่า Sync แล้ว"""
        try:
            cursor = self.conn.cursor()
            query = """
                UPDATE tickets 
                SET sync_status = 'synced', server_id = ?
                WHERE WE_ID = ?
            """
            params = (server_id, local_id)
            cursor.execute(query, params)
            self.conn.commit()
            return {"status": "success", "local_id": local_id, "server_id": server_id}
        except Exception as e:
            print(f"Error marking ticket as synced: {e}")
            return None
    # --- END: ฟังก์ชันใหม่สำหรับจัดการ Ticket ใน Local DB ---

    def send_offline_data_to_server(self, record):
        """ส่งข้อมูลจาก Local ไป Server"""
        try:
            if self.websocket and not self.websocket.closed:
                message = {
                    "client_id": self.client_id_var.get(),
                    "weight": str(record[1]),  # weight
                    "timestamp": time.time(),
                    "branch": record[4] if record[4] else self.branch_var.get(),
                    "branch_prefix": self.get_branch_prefix(record[4] if record[4] else self.branch_var.get()),
                    "scale_pattern": record[5] if record[5] else self.scale_pattern_var.get(),
                    "offline_sync": True  # แสดงว่าเป็นข้อมูลจาก offline sync
                }
                
                # ส่งข้อมูลแบบ async
                asyncio.run_coroutine_threadsafe(
                    self.websocket.send(json.dumps(message)), 
                    self.loop
                )
                
                # ทำเครื่องหมายว่า sync แล้ว
                self.local_data_manager.mark_as_synced(record[0])
                
                # อัปเดต Local UI
                self.offline_ui.update_local_data_display()
                
                self.log_message(f"Synced offline data: {record[1]} kg")
                
        except Exception as e:
            self.log_message(f"Error syncing offline data: {e}")

    def show_local_data_window(self):
        """แสดงหน้าต่างข้อมูล Local"""
        try:
            # สร้างหน้าต่างใหม่
            local_window = tk.Toplevel(self.root)
            local_window.title("Local Weight Data")
            local_window.geometry("800x600")
            
            # สร้าง Treeview สำหรับแสดงข้อมูล
            columns = ('ID', 'Weight', 'Timestamp', 'Status', 'Branch', 'Scale Pattern', 'Synced')
            tree = ttk.Treeview(local_window, columns=columns, show='headings')
            
            # กำหนดหัวข้อคอลัมน์
            for col in columns:
                tree.heading(col, text=col)
                tree.column(col, width=100)
            
            # ดึงข้อมูลจาก Local Database
            conn = sqlite3.connect(self.local_data_manager.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, weight, timestamp, status, branch, scale_pattern, synced
                FROM weight_records
                ORDER BY timestamp DESC
                LIMIT 100
            ''')
            
            data = cursor.fetchall()
            conn.close()
            
            # เพิ่มข้อมูลใน Treeview
            for row in data:
                synced_text = "Yes" if row[6] else "No"
                tree.insert('', 'end', values=(row[0], row[1], row[2], row[3], row[4], row[5], synced_text))
            
            # เพิ่ม Scrollbar
            scrollbar = ttk.Scrollbar(local_window, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)
            
            # จัดวาง
            tree.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            
            # แสดงจำนวนข้อมูล
            info_label = ttk.Label(local_window, text=f"Showing {len(data)} records")
            info_label.pack(pady=5)
            
        except Exception as e:
            self.log_message(f"Error showing local data window: {e}")
            messagebox.showerror("Error", f"Error showing local data: {e}")

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
                    
                    # ถ้า buffer ใหญ่เกินไป ให้ล้างบางส่วน
                    if len(self.read_buffer) > 1500:
                        # เก็บข้อมูลล่าสุด 500 bytes
                        self.read_buffer = self.read_buffer[-500:]
                        self.log_message("Buffer trimmed due to size")
                        
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
        """เริ่มต้น client"""
        if self.is_running:
            return
            
        # ตรวจสอบการเชื่อมต่อ Serial ก่อนเริ่ม
        if not self.test_connection_status():
            messagebox.showwarning("Warning", "Serial port is not available!\nPlease check your connection and settings.")
            return
            
        self.is_running = True
        self.start_btn.config(state='disabled')
        self.stop_btn.config(state='normal')
        
        # เริ่ม Local Web Server
        self.local_web_server.start_server()
        
        # เริ่ม Local API Server
        self.local_api_server.start_server()
        
        # เริ่ม thread สำหรับการทำงาน
        self.client_thread = threading.Thread(target=self.run_client_async, daemon=True)
        self.client_thread.start()
        
        self.log_message("Client started")

        
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
            
            # หยุด Local Web Server
            self.local_web_server.stop_server()
            
            # หยุด Local API Server
            self.local_api_server.stop_server()
            
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
            self.server_status_label.config(text="🔴 Server: Disconnected")
            
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
                self.server_status_label.config(text="🟢 Server: Connected")
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
                    self.server_status_label.config(text="🔴 Server: Disconnected")
                    
            except websockets.exceptions.InvalidURI:
                self.log_message(f"Invalid server URL: {server_url}")
                self.is_connected = False
                self.server_status_label.config(text="🔴 Server: Invalid URL")
                await asyncio.sleep(10)  # รอนานขึ้นสำหรับ URL ที่ผิด
                continue
                    
            except Exception as e:
                self.log_message(f"Connection error: {e}")
                self.is_connected = False
                self.server_status_label.config(text="🔴 Server: Disconnected")
            
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
                
                # ตรวจสอบว่าน้ำหนักเป็น 0 หรือไม่ และไม่ส่งซ้ำ
                if weight == "0" or weight == "0.0":
                    # ถ้าน้ำหนักเป็น 0 ให้รอข้อมูลใหม่
                    await asyncio.sleep(0.1)  # ลด delay จาก 0.5 เป็น 0.1 วินาที
                    continue
                
                # รีเซ็ต error counter เมื่อสำเร็จ
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
                
                # ... existing code ...

                try:
                    # ตรวจสอบ WebSocket state ก่อนส่ง
                    if self.websocket and not self.websocket.closed:
                        await self.websocket.send(json.dumps(message))
                        self.log_message(f"Sent weight: {weight} (Branch: {self.branch_var.get()}, Pattern: {self.scale_pattern_var.get()})")
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
            # ตรวจสอบสถานะการเชื่อมต่อ
            if self.is_offline_mode:
                # เปิด Local Dashboard
                local_url = f"http://localhost:{self.local_web_server.port}"
                self.log_message(f"Opening local dashboard: {local_url}")
                webbrowser.open(local_url)
                messagebox.showinfo("Local Dashboard", f"Opening local dashboard:\n{local_url}\n\nThis shows data from local storage.")
            else:
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

# เพิ่ม Connection Monitor Class
class ConnectionMonitor:
    def __init__(self, client):
        self.client = client
        self.is_online = False
        self.monitor_thread = threading.Thread(target=self.monitor_connection)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
    
    def monitor_connection(self):
        """ตรวจสอบการเชื่อมต่ออย่างต่อเนื่อง"""
        while True:
            try:
                # ตรวจสอบ WebSocket connection
                if (self.client.websocket and 
                    not self.client.websocket.closed):
                    self.is_online = True
                    if hasattr(self.client, 'offline_ui'):
                        self.client.offline_ui.update_connection_status(True)
                else:
                    self.is_online = False
                    if hasattr(self.client, 'offline_ui'):
                        self.client.offline_ui.update_connection_status(False)
                
                time.sleep(5)  # ตรวจสอบทุก 5 วินาที
                
            except Exception as e:
                self.is_online = False
                if hasattr(self.client, 'offline_ui'):
                    self.client.offline_ui.update_connection_status(False)
                time.sleep(5)

# เพิ่ม Offline Mode UI Class
class OfflineModeUI:
    def __init__(self, parent):
        self.parent = parent
        self.setup_offline_ui()
    
    def setup_offline_ui(self):
        """สร้าง UI สำหรับ Offline Mode"""
        # ใช้ grid แทน pack เพื่อให้เข้ากับ layout หลัก
        self.offline_frame = ttk.LabelFrame(self.parent, text="🔄 Offline Mode & Local Storage")
        self.offline_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), padx=10, pady=5)
        self.offline_frame.columnconfigure(1, weight=1)
        
        # สถานะการเชื่อมต่อ
        self.connection_status = ttk.Label(
            self.offline_frame, 
            text="🔴 Offline - Local Mode Active",
            foreground="red",
            font=("Arial", 10, "bold")
        )
        self.connection_status.grid(row=0, column=0, columnspan=2, pady=5)
        
        # แสดงข้อมูล Local
        self.local_data_label = ttk.Label(
            self.offline_frame,
            text="Local Records: 0 | Synced: 0 | Unsynced: 0"
        )
        self.local_data_label.grid(row=1, column=0, columnspan=2, pady=5)
        
        # Frame สำหรับปุ่มต่างๆ
        button_frame = ttk.Frame(self.offline_frame)
        button_frame.grid(row=2, column=0, columnspan=2, pady=5)
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=1)
        button_frame.columnconfigure(2, weight=1)
        
        # ปุ่ม Sync ข้อมูล
        self.sync_button = ttk.Button(
            button_frame,
            text="🔄 Sync Data to Server",
            command=self.sync_data,
            style="Accent.TButton"
        )
        self.sync_button.grid(row=0, column=0, padx=5)
        
        # ปุ่ม Export CSV
        self.export_button = ttk.Button(
            button_frame,
            text="📊 Export to CSV",
            command=self.export_data
        )
        self.export_button.grid(row=0, column=1, padx=5)
        
        # ปุ่ม View Local Data
        self.view_button = ttk.Button(
            button_frame,
            text="👁️ View Local Data",
            command=self.view_local_data
        )
        self.view_button.grid(row=0, column=2, padx=5)
    
    def update_connection_status(self, is_online):
        """อัปเดตสถานะการเชื่อมต่อ"""
        if is_online:
            self.connection_status.config(
                text=" Online - Connected to Server",
                foreground="green"
            )
        else:
            self.connection_status.config(
                text="🔴 Offline - Local Mode Active",
                foreground="red"
            )
    
    def update_local_data_display(self):
        """อัปเดตการแสดงข้อมูล Local"""
        if hasattr(self.parent, 'local_data_manager'):
            stats = self.parent.local_data_manager.get_local_stats()
            self.local_data_label.config(
                text=f"Local Records: {stats['total']} | Synced: {stats['synced']} | Unsynced: {stats['unsynced']}"
            )
    
    def sync_data(self):
        """Sync ข้อมูลจาก Local ไป Server"""
        if hasattr(self.parent, 'local_data_manager'):
            unsynced_data = self.parent.local_data_manager.get_unsynced_data()
            if unsynced_data:
                self.parent.log_message(f"Syncing {len(unsynced_data)} records...")
                # ส่งข้อมูลไป Server
                for record in unsynced_data:
                    self.parent.send_offline_data_to_server(record)
            else:
                self.parent.log_message("No data to sync")
    
    def export_data(self):
        """Export ข้อมูลเป็น CSV"""
        if hasattr(self.parent, 'local_data_manager'):
            filename = f"weight_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            count = self.parent.local_data_manager.export_to_csv(filename)
            if count > 0:
                self.parent.log_message(f"Exported {count} records to {filename}")
                messagebox.showinfo("Export Success", f"Exported {count} records to {filename}")
            else:
                messagebox.showerror("Export Error", "No data to export")
    
    def view_local_data(self):
        """แสดงข้อมูล Local ในหน้าต่างใหม่"""
        if hasattr(self.parent, 'local_data_manager'):
            self.parent.show_local_data_window()

class LocalWebServer:
    def __init__(self, client_gui):
        self.client_gui = client_gui
        self.server = None
        self.server_thread = None
        self.port = 8080
        
    def start_server(self):
        """เริ่ม Local Web Server"""
        try:
            class LocalHandler(BaseHTTPRequestHandler):
                def __init__(self, *args, **kwargs):
                    self.client_gui = self.server.client_gui
                    super().__init__(*args, **kwargs)
                
                def do_GET(self):
                    """จัดการ GET requests"""
                    if self.path == '/':
                        self.send_response(200)
                        self.send_header('Content-type', 'text/html')
                        self.end_headers()
                        
                        # ส่งหน้า HTML ง่ายๆ
                        html = self.get_local_dashboard()
                        self.wfile.write(html.encode('utf-8'))
                        
                    elif self.path == '/api/weight':
                        self.send_response(200)
                        self.send_header('Content-type', 'application/json')
                        self.send_header('Access-Control-Allow-Origin', '*')
                        self.end_headers()
                        
                        # ส่งข้อมูลน้ำหนักปัจจุบัน
                        weight_data = {
                            'weight': self.client_gui.last_weight,
                            'timestamp': time.time(),
                            'status': 'local' if self.client_gui.is_offline_mode else 'online'
                        }
                        self.wfile.write(json.dumps(weight_data).encode('utf-8'))
                        
                    elif self.path == '/api/local-data':
                        self.send_response(200)
                        self.send_header('Content-type', 'application/json')
                        self.send_header('Access-Control-Allow-Origin', '*')
                        self.end_headers()
                        
                        # ส่งข้อมูลจาก Local Database
                        if hasattr(self.client_gui, 'local_data_manager'):
                            stats = self.client_gui.local_data_manager.get_local_stats()
                            self.wfile.write(json.dumps(stats).encode('utf-8'))
                        else:
                            self.wfile.write(json.dumps({'error': 'No local data'}).encode('utf-8'))
                    
                    elif self.path == '/api/tickets/':
                        tickets = self.data_manager.get_local_tickets(completed=False)
                        self._send_response(200, tickets)
                    elif self.path == '/api/tickets/completed':
                        tickets = self.data_manager.get_local_tickets(completed=True)
                        self._send_response(200, tickets)
                    elif self.path == '/api/tickets/mark-synced':
                        content_length = int(self.headers['Content-Length'])
                        post_data = json.loads(self.rfile.read(content_length))
                        local_id = post_data.get('local_id')
                        server_id = post_data.get('server_id')
                        
                        if not local_id or not server_id:
                            self._send_response(400, {"error": "Missing local_id or server_id"})
                            return
                        
                        result = self.data_manager.mark_ticket_as_synced(local_id, server_id)
                        if result:
                            self._send_response(200, result)
                        else:
                            self._send_response(500, {"error": "Failed to mark ticket as synced"})
                    else:
                        self._send_response(404, {"error": "Not Found"})
                
                def get_local_dashboard(self):
                    """สร้างหน้า Dashboard ง่ายๆ"""
                    return f"""
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <title>RS232 Scale Client - Local Mode</title>
                        <meta charset="utf-8">
                        <style>
                            body {{ font-family: Arial, sans-serif; margin: 20px; }}
                            .status {{ padding: 10px; margin: 10px 0; border-radius: 5px; }}
                            .online {{ background-color: #d4edda; color: #155724; }}
                            .offline {{ background-color: #f8d7da; color: #721c24; }}
                            .weight {{ font-size: 48px; font-weight: bold; text-align: center; margin: 20px; }}
                            .data {{ background-color: #f8f9fa; padding: 15px; border-radius: 5px; }}
                        </style>
                    </head>
                    <body>
                        <h1>⚖️ RS232 Scale Client - Local Mode</h1>
                        
                        <div class="status {'offline' if self.client_gui.is_offline_mode else 'online'}">
                            Status: {'🔴 Offline Mode' if self.client_gui.is_offline_mode else '🟢 Online Mode'}
                        </div>
                        
                        <div class="weight">
                            {self.client_gui.last_weight} kg
                        </div>
                        
                        <div class="data">
                            <h3>Local Data Statistics</h3>
                            <div id="stats">Loading...</div>
                        </div>
                        
                        <script>
                            // อัปเดตข้อมูลทุก 2 วินาที
                            setInterval(async () => {{
                                try {{
                                    const response = await fetch('/api/weight');
                                    const data = await response.json();
                                    document.querySelector('.weight').textContent = data.weight + ' kg';
                                }} catch (e) {{
                                    console.log('Error fetching weight:', e);
                                }}
                            }}, 2000);
                            
                            // โหลดสถิติ
                            async function loadStats() {{
                                try {{
                                    const response = await fetch('/api/local-data');
                                    const stats = await response.json();
                                    document.getElementById('stats').innerHTML = `
                                        <p>Total Records: ${{stats.total}}</p>
                                        <p>Synced: ${{stats.synced}}</p>
                                        <p>Pending: ${{stats.unsynced}}</p>
                                    `;
                                }} catch (e) {{
                                    console.log('Error fetching stats:', e);
                                }}
                            }}
                            
                            loadStats();
                            setInterval(loadStats, 5000);
                        </script>
                    </body>
                    </html>
                    """
                
                def log_message(self, format, *args):
                    """Override เพื่อไม่ให้ log ข้อความ HTTP"""
                    pass
            
            # สร้าง server
            self.server = HTTPServer(('localhost', self.port), LocalHandler)
            self.server.client_gui = self.client_gui
            
            # เริ่ม server ใน thread แยก
            self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.server_thread.start()
            
            self.client_gui.log_message(f"Local web server started on http://localhost:{self.port}")
            
        except Exception as e:
            self.client_gui.log_message(f"Error starting local web server: {e}")
    
    def stop_server(self):
        """หยุด Local Web Server"""
        try:
            if self.server:
                self.server.shutdown()
                self.server.server_close()
                self.client_gui.log_message("Local web server stopped")
        except Exception as e:
            self.client_gui.log_message(f"Error stopping local web server: {e}")

class LocalAPIServer:
    def __init__(self, data_manager, host='localhost', port=8080):
        self.data_manager = data_manager
        self.host = host
        self.port = port
        self.server = None
        self.thread = None

    def start_server(self):
        if self.thread and self.thread.is_alive():
            print("Local API server is already running.")
            return

        handler = self.create_handler()
        self.server = HTTPServer((self.host, self.port), handler)
        
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        print(f"Local API server started at http://{self.host}:{self.port}")

    def stop_server(self):
        if self.server:
            self.server.shutdown()
            self.thread.join()
            print("Local API server stopped.")

    def create_handler(self):
        data_manager = self.data_manager
        
        class LocalAPIHandler(BaseHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                self.data_manager = data_manager
                super().__init__(*args, **kwargs)

            def _send_cors_headers(self):
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Access-Control-Allow-Methods', 'GET, POST, PATCH, OPTIONS')
                self.send_header('Access-Control-Allow-Headers', 'Content-Type')

            def do_OPTIONS(self):
                self.send_response(204)
                self._send_cors_headers()
                self.end_headers()

            def _send_response(self, status_code, data=None):
                self.send_response(status_code)
                self.send_header('Content-type', 'application/json')
                self._send_cors_headers()
                self.end_headers()
                if data:
                    self.wfile.write(json.dumps(data, indent=4).encode('utf-8'))

            def do_GET(self):
                if self.path == '/api/tickets/':
                    tickets = self.data_manager.get_local_tickets(completed=False)
                    self._send_response(200, tickets)
                elif self.path == '/api/tickets/completed':
                    tickets = self.data_manager.get_local_tickets(completed=True)
                    self._send_response(200, tickets)
                else:
                    self._send_response(404, {"error": "Not Found"})
            
            def do_POST(self):
                if self.path == '/api/tickets/':
                    content_length = int(self.headers['Content-Length'])
                    post_data = json.loads(self.rfile.read(content_length))
                    
                    new_ticket = self.data_manager.create_local_ticket(post_data)
                    if new_ticket:
                        self._send_response(201, new_ticket)
                    else:
                        self._send_response(500, {"error": "Failed to create local ticket"})

                elif self.path == '/api/tickets/mark-synced':
                    content_length = int(self.headers['Content-Length'])
                    post_data = json.loads(self.rfile.read(content_length))
                    local_id = post_data.get('local_id')
                    server_id = post_data.get('server_id')
                    
                    if not local_id or not server_id:
                        self._send_response(400, {"error": "Missing local_id or server_id"})
                        return
                        
                    result = self.data_manager.mark_ticket_as_synced(local_id, server_id)
                    if result:
                        self._send_response(200, result)
                    else:
                        self._send_response(500, {"error": "Failed to mark ticket as synced"})
                
                else:
                    self._send_response(404, {"error": "Not Found"})

            def do_PATCH(self):
                path_parts = self.path.split('/')
                if len(path_parts) == 4 and path_parts[1] == 'api' and path_parts[2] == 'tickets':
                    ticket_id = path_parts[3]
                    content_length = int(self.headers['Content-Length'])
                    patch_data = json.loads(self.rfile.read(content_length))
                    
                    updated_ticket = self.data_manager.update_local_ticket_weigh_out(ticket_id, patch_data)
                    
                    if updated_ticket:
                        self._send_response(200, updated_ticket)
                    else:
                        self._send_response(404, {"error": f"Ticket with id {ticket_id} not found or could not be updated."})
                else:
                    self._send_response(404, {"error": "Not Found"})

        return LocalAPIHandler

# ... existing code ...

if __name__ == '__main__':
    try:
        app = RS232ClientGUI()
        app.run()
    except Exception as e:
        print(f"Application error: {e}")