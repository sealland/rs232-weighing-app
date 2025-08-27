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

# Configuration
CLIENT_CONFIG_FILE = "client_config.ini"
SERVER_WEBSOCKET_URL = "ws://localhost:8765"
CLIENT_ID = "scale_001"

# Serial Configuration
DEFAULT_SERIAL_PORT = "COM1"
DEFAULT_BAUD_RATE = 1200
DEFAULT_PARITY = "N"
DEFAULT_STOP_BITS = "1"
DEFAULT_BYTE_SIZE = "8"
DEFAULT_READ_TIMEOUT = 0.05

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
    ]
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
        self.root.geometry("900x700")  # เพิ่มความสูงเพื่อรองรับ Scale Pattern
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
        
        # GUI variables
        self.port_var = tk.StringVar(value=self.serial_config['port'])
        self.baudrate_var = tk.StringVar(value=str(self.serial_config['baudrate']))
        self.parity_var = tk.StringVar(value=self.get_parity_key())
        self.stopbits_var = tk.StringVar(value=self.get_stopbits_key())
        self.bytesize_var = tk.StringVar(value=self.get_bytesize_key())
        self.timeout_var = tk.StringVar(value=str(self.serial_config['timeout']))
        self.server_url_var = tk.StringVar(value=SERVER_WEBSOCKET_URL)
        self.client_id_var = tk.StringVar(value=CLIENT_ID)
        self.branch_var = tk.StringVar(value='สำนักงานใหญ่ P8')  # Default branch
        self.scale_pattern_var = tk.StringVar(value='Default')  # Default scale pattern
        
        self.setup_ui()
        self.update_available_ports()
        
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
        
        # Parity
        ttk.Label(config_frame, text="Parity:", font=('Tahoma', 8)).grid(row=2, column=0, sticky=tk.W, padx=(0, 8))
        parity_combo = ttk.Combobox(config_frame, textvariable=self.parity_var, 
                                   values=['N', 'E', 'O', 'M', 'S'],
                                   width=12, font=('Tahoma', 8))
        parity_combo.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=3)
        
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
        
        # Timeout
        ttk.Label(config_frame, text="Timeout (sec):", font=('Tahoma', 8)).grid(row=5, column=0, sticky=tk.W, padx=(0, 8))
        timeout_entry = ttk.Entry(config_frame, textvariable=self.timeout_var, width=12, font=('Tahoma', 8))
        timeout_entry.grid(row=5, column=1, sticky=(tk.W, tk.E), pady=3)
        
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
        
        # Branch Configuration Frame
        branch_frame = ttk.LabelFrame(left_panel, text="Branch Configuration", padding="8")
        branch_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 8))
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
        server_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 8))
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
        control_frame.grid(row=4, column=0, columnspan=2, pady=(0, 8))
        
        self.test_btn = ttk.Button(control_frame, text="Test", command=self.test_serial_connection, width=8)
        self.test_btn.grid(row=0, column=0, padx=(0, 5))
        
        self.save_btn = ttk.Button(control_frame, text="Save", command=self.save_configuration, width=8)
        self.save_btn.grid(row=0, column=1, padx=(0, 5))
        
        self.start_btn = ttk.Button(control_frame, text="Start", command=self.start_client, width=8)
        self.start_btn.grid(row=0, column=2, padx=(0, 5))
        
        self.stop_btn = ttk.Button(control_frame, text="Stop", command=self.stop_client, state='disabled', width=8)
        self.stop_btn.grid(row=0, column=3)
        
        # Config Path Note
        config_abs_path = os.path.abspath(CLIENT_CONFIG_FILE)
        config_note_label = ttk.Label(left_panel, 
                                     text=f"Config: {os.path.basename(config_abs_path)}", 
                                     font=('Tahoma', 7), 
                                     foreground='gray')
        config_note_label.grid(row=5, column=0, columnspan=2, sticky=tk.W, pady=(0, 5))
        
        # Right Panel - Status & Monitoring
        right_panel = ttk.Frame(main_frame)
        right_panel.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(5, 0))
        right_panel.columnconfigure(0, weight=1)
        right_panel.rowconfigure(1, weight=1)
        main_frame.rowconfigure(1, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # Status Frame
        status_frame = ttk.LabelFrame(right_panel, text="Status & Monitoring", padding="8")
        status_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
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
        
        # Update displays
        self.update_branch_prefix_display()
        self.update_scale_pattern_info()
        
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
            pattern_names = [pattern[0] for pattern in patterns]
            self.scale_pattern_info_label.config(text=f"Patterns: {', '.join(pattern_names)}")
        
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
                        
                    # Load branch configuration
                    if 'BranchConfig' in config:
                        branch_section = config['BranchConfig']
                        self.branch_var.set(branch_section.get('Branch', 'สำนักงานใหญ่ P8'))
                        
                    # Load scale pattern configuration
                    if 'ScaleConfig' in config:
                        scale_section = config['ScaleConfig']
                        self.scale_pattern_var.set(scale_section.get('Pattern', 'Default'))
                        
                except Exception as e:
                    print(f"Error loading config: {e}. Using defaults.")
            else:
                print("Config file not found. Using defaults.")
                
            return {
                'port': loaded_settings['port'],
                'baudrate': loaded_settings['baudrate'],
                'parity': parity_map.get(loaded_settings['parity_key'], serial.PARITY_NONE),
                'stopbits': stop_bits_map.get(loaded_settings['stopbits_key'], serial.STOPBITS_ONE),
                'bytesize': byte_size_map.get(loaded_settings['bytesize_key'], serial.EIGHTBITS),
                'timeout': loaded_settings['timeout']
            }
        except Exception as e:
            print(f"Load config error: {e}")
            return {
                'port': DEFAULT_SERIAL_PORT,
                'baudrate': DEFAULT_BAUD_RATE,
                'parity': serial.PARITY_NONE,
                'stopbits': serial.STOPBITS_ONE,
                'bytesize': serial.EIGHTBITS,
                'timeout': DEFAULT_READ_TIMEOUT
            }
        
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
                'ReadTimeout': self.timeout_var.get()
            }
            
            # Save branch configuration
            config['BranchConfig'] = {
                'Branch': self.branch_var.get()
            }
            
            # Save scale pattern configuration
            config['ScaleConfig'] = {
                'Pattern': self.scale_pattern_var.get()
            }
            
            with open(CLIENT_CONFIG_FILE, 'w') as configfile:
                config.write(configfile)
                
            config_abs_path = os.path.abspath(CLIENT_CONFIG_FILE)
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
            
            with serial.Serial(**test_config) as test_ser:
                if test_ser.is_open:
                    self.log_message("Serial connection test successful!")
                    messagebox.showinfo("Success", "Serial connection test successful!")
                else:
                    self.log_message("Serial connection test failed!")
                    messagebox.showerror("Error", "Serial connection test failed!")
                    
        except serial.SerialException as e:
            self.log_message(f"Serial connection test error: {e}")
            messagebox.showerror("Error", f"Serial connection test failed: {e}")
        except PermissionError as e:
            self.log_message(f"Permission Error: {e}")
            messagebox.showerror("Permission Error", 
                               "Cannot access the serial port.\n\n"
                               "Possible solutions:\n"
                               "1. Run as Administrator\n"
                               "2. Close other applications using this port\n"
                               "3. Check Device Manager for port conflicts\n"
                               "4. Reconnect USB to Serial adapter")
        except Exception as e:
            self.log_message(f"Unexpected error: {e}")
            messagebox.showerror("Error", f"Unexpected error: {e}")
            
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
                
            known_weight_indicators = SCALE_PATTERNS[selected_pattern]
            
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
        except Exception as e:
            self.log_message(f"Parse error: {e}")
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
                
                # Log raw data for debugging
                if new_bytes:
                    self.log_message(f"Raw data: {new_bytes.hex()}")
            
            while True:
                stx_index = self.read_buffer.find(self.STX)
                if stx_index != -1:
                    etx_index = self.read_buffer.find(self.ETX, stx_index + 1)
                    if etx_index != -1:
                        complete_message_bytes = self.read_buffer[stx_index + 1: etx_index]
                        try:
                            decoded_message = complete_message_bytes.decode('latin-1').strip()
                            self.log_message(f"Decoded message: {decoded_message}")
                            parsed_value = self.parse_scale_data(decoded_message)
                            if parsed_value != "N/A":
                                self.last_weight = parsed_value
                                self.weight_label.config(text=f"⚖️ Weight: {parsed_value} kg")
                        except Exception as e:
                            self.log_message(f"Parse error: {e}")
                        self.read_buffer = self.read_buffer[etx_index + 1:]
                    else:
                        break
                else:
                    break
            
            return self.last_weight
        except Exception as e:
            self.log_message(f"Serial read error: {e}")
            return "Error"
            
    def start_client(self):
        """เริ่มต้น client"""
        if self.is_running:
            return
            
        self.is_running = True
        self.start_btn.config(state='disabled')
        self.stop_btn.config(state='normal')
        
        # เริ่ม thread สำหรับการทำงาน
        self.client_thread = threading.Thread(target=self.run_client_async, daemon=True)
        self.client_thread.start()
        
        self.log_message("Client started")
        
    def stop_client(self):
        """หยุด client"""
        try:
            self.is_running = False
            self.is_connected = False
            
            if self.serial_connection and self.serial_connection.is_open:
                self.serial_connection.close()
                
            if self.websocket and self.loop:
                try:
                    asyncio.run_coroutine_threadsafe(self.websocket.close(), self.loop)
                except Exception as e:
                    print(f"WebSocket close error: {e}")
                    
            self.start_btn.config(state='normal')
            self.stop_btn.config(state='disabled')
            self.serial_status_label.config(text="🔴 Serial: Disconnected")
            self.server_status_label.config(text="🔴 Server: Disconnected")
            
            self.log_message("Client stopped")
        except Exception as e:
            self.log_message(f"Stop client error: {e}")
        
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
        while self.is_running:
            try:
                server_url = self.server_url_var.get()
                client_id = self.client_id_var.get()
                
                self.log_message(f"Connecting to server {server_url}")
                
                async with websockets.connect(server_url) as websocket:
                    self.websocket = websocket
                    self.is_connected = True
                    self.server_status_label.config(text="🟢 Server: Connected")
                    self.log_message("Connected to server")
                    
                    # เริ่มการส่งข้อมูล
                    await self.send_weight_loop(client_id)
                    
            except Exception as e:
                self.log_message(f"Connection error: {e}")
                self.is_connected = False
                self.server_status_label.config(text="🔴 Server: Disconnected")
                await asyncio.sleep(5)
                
    async def send_weight_loop(self, client_id):
        """ลูปสำหรับส่งข้อมูลน้ำหนัก"""
        while self.is_running and self.is_connected:
            try:
                weight = self.read_weight_from_rs232()
                
                # ส่งข้อมูลเพิ่มเติมรวมถึง branch prefix และ scale pattern
                message = {
                    "client_id": client_id,
                    "weight": weight,
                    "timestamp": time.time(),
                    "branch": self.branch_var.get(),
                    "branch_prefix": self.get_branch_prefix(self.branch_var.get()),
                    "scale_pattern": self.scale_pattern_var.get()
                }
                await self.websocket.send(json.dumps(message))
                self.log_message(f"Sent weight: {weight} (Branch: {self.branch_var.get()}, Pattern: {self.scale_pattern_var.get()})")
                await asyncio.sleep(0.5)
            except Exception as e:
                self.log_message(f"Error sending data: {e}")
                break
                
    def run(self):
        """เริ่มต้น GUI"""
        try:
            self.log_message("RS232 Scale Client GUI started")
            self.root.mainloop()
        except Exception as e:
            print(f"GUI error: {e}")

if __name__ == '__main__':
    try:
        app = RS232ClientGUI()
        app.run()
    except Exception as e:
        print(f"Application error: {e}")
