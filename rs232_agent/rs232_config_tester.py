import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import serial
import threading
import time
import re
import queue

# --- Default Configuration ---
DEFAULT_SERIAL_PORT = "COM1"
DEFAULT_BAUD_RATE = 1200
DEFAULT_PARITY = "N"
DEFAULT_STOP_BITS = 1
DEFAULT_BYTE_SIZE = 8
DEFAULT_READ_TIMEOUT = 1.5  # หรือค่าที่คุณต้องการ


class RS232TesterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("RS232 Scale Tester")
        self.root.geometry("650x550")

        self.ser = None
        self.is_reading = False
        self.read_thread = None  # จะถูกสร้างใน start_reading

        self.data_queue = queue.Queue()
        self.check_queue_interval = 50  # milliseconds

        # --- Configuration Frame ---
        config_frame = ttk.LabelFrame(root, text="Serial Port Configuration")
        config_frame.pack(padx=10, pady=10, fill="x")

        ttk.Label(config_frame, text="COM Port:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.com_port_var = tk.StringVar(value=DEFAULT_SERIAL_PORT)
        ttk.Entry(config_frame, textvariable=self.com_port_var, width=10).grid(row=0, column=1, padx=5, pady=5,
                                                                               sticky="w")

        ttk.Label(config_frame, text="Baud Rate:").grid(row=0, column=2, padx=5, pady=5, sticky="w")
        self.baud_rate_var = tk.StringVar(value=str(DEFAULT_BAUD_RATE))
        ttk.Entry(config_frame, textvariable=self.baud_rate_var, width=10).grid(row=0, column=3, padx=5, pady=5,
                                                                                sticky="w")

        ttk.Label(config_frame, text="Parity:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.parity_map = {"N": serial.PARITY_NONE, "E": serial.PARITY_EVEN, "O": serial.PARITY_ODD,
                           "M": serial.PARITY_MARK, "S": serial.PARITY_SPACE}
        self.parity_var = tk.StringVar(value=DEFAULT_PARITY)
        parity_options = list(self.parity_map.keys())
        ttk.Combobox(config_frame, textvariable=self.parity_var, values=parity_options, width=7, state="readonly").grid(
            row=1, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(config_frame, text="Stop Bits:").grid(row=1, column=2, padx=5, pady=5, sticky="w")
        self.stop_bits_map = {"1": serial.STOPBITS_ONE, "1.5": serial.STOPBITS_ONE_POINT_FIVE, "2": serial.STOPBITS_TWO}
        self.stop_bits_var = tk.StringVar(value=str(DEFAULT_STOP_BITS))
        stop_bits_options = list(self.stop_bits_map.keys())
        ttk.Combobox(config_frame, textvariable=self.stop_bits_var, values=stop_bits_options, width=7,
                     state="readonly").grid(row=1, column=3, padx=5, pady=5, sticky="w")

        ttk.Label(config_frame, text="Byte Size:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.byte_size_map = {"8": serial.EIGHTBITS, "7": serial.SEVENBITS, "6": serial.SIXBITS, "5": serial.FIVEBITS}
        self.byte_size_var = tk.StringVar(value=str(DEFAULT_BYTE_SIZE))
        byte_size_options = list(self.byte_size_map.keys())
        ttk.Combobox(config_frame, textvariable=self.byte_size_var, values=byte_size_options, width=7,
                     state="readonly").grid(row=2, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(config_frame, text="Read Timeout (s):").grid(row=2, column=2, padx=5, pady=5, sticky="w")
        self.timeout_var = tk.StringVar(value=str(DEFAULT_READ_TIMEOUT))
        ttk.Entry(config_frame, textvariable=self.timeout_var, width=10).grid(row=2, column=3, padx=5, pady=5,
                                                                              sticky="w")

        # --- Control Frame ---
        control_frame = ttk.Frame(root)
        control_frame.pack(padx=10, pady=5, fill="x")

        self.connect_button = ttk.Button(control_frame, text="Connect & Read", command=self.toggle_connection)
        self.connect_button.pack(side="left", padx=5)

        self.clear_log_button = ttk.Button(control_frame, text="Clear Log", command=self.clear_log)
        self.clear_log_button.pack(side="left", padx=5)

        # --- Live Weight Display ---
        current_weight_frame = ttk.Frame(root)
        current_weight_frame.pack(padx=10, pady=(5, 0), fill="x")

        ttk.Label(current_weight_frame, text="Live Weight:", font=("Arial", 12)).pack(side="left")
        self.current_weight_var = tk.StringVar(value="---")
        self.current_weight_label = ttk.Label(current_weight_frame, textvariable=self.current_weight_var,
                                              font=("Arial", 18, "bold"), foreground="blue", width=25,
                                              anchor="w")  # เพิ่ม width
        self.current_weight_label.pack(side="left", padx=10)

        # --- Log Area ---
        log_frame = ttk.LabelFrame(root, text="Log Output")
        log_frame.pack(padx=10, pady=10, fill="both", expand=True)

        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=10, width=70,
                                                  font=("Consolas", 9))  # เปลี่ยน font ให้ดูเหมือน console
        self.log_text.pack(fill="both", expand=True, padx=5, pady=5)
        self.log_text.configure(state='disabled')

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.log_message("DEBUG_INIT: Application initialized.")

    def log_message(self, message):
        # ตรวจสอบว่า self.log_text ถูกสร้างแล้วหรือยัง (ป้องกัน error ตอน init ถ้า log เร็วไป)
        if hasattr(self, 'log_text') and self.log_text:
            self.log_text.configure(state='normal')
            # เพิ่ม timestamp เพื่อให้แยกแยะ log ได้ง่ายขึ้น (optional)
            # timestamp = time.strftime("%H:%M:%S", time.localtime())
            # self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
            self.log_text.insert(tk.END, f"{message}\n")
            self.log_text.see(tk.END)
            self.log_text.configure(state='disabled')
        else:
            print(f"LOG_EARLY: {message}")  # ถ้า log_text ยังไม่พร้อม ให้ print ไป console

    def clear_log(self):
        self.log_message("DEBUG_CLEAR_LOG: Clearing log output.")
        self.log_text.configure(state='normal')
        self.log_text.delete(1.0, tk.END)
        self.log_text.configure(state='disabled')

    def parse_scale_data(self, raw_data_str):
        # self.log_message(f"DEBUG_PARSER_INPUT: '{raw_data_str}'") # อาจจะถี่ไป
        known_weight_indicators = [
            ("1BH", r"1BH\s+(\d+)"),
            ("1@H", r"1@H\s+(\d+)"),
            ("1CH", r"1CH\s+(0{3,})"),
            (" H ", r" H\s+(0{3,})")
        ]
        extracted_weight_strings = []
        for indicator_text, pattern_regex in known_weight_indicators:
            matches = re.findall(pattern_regex, raw_data_str)
            # self.log_message(f"DEBUG_PARSER_MATCH: Ind: {indicator_text}, Matches: {matches}")
            if matches:
                for num_str in matches:
                    if indicator_text == "1CH":
                        extracted_weight_strings.append("0")
                    else:
                        extracted_weight_strings.append(num_str)

        if extracted_weight_strings:
            final_num_str = extracted_weight_strings[-1]  # อาจจะต้องมี logic ที่ดีกว่านี้ถ้ามีหลาย match
            try:
                weight_value_int = int(final_num_str)
                parsed_result = str(weight_value_int)
                # self.log_message(f"DEBUG_PARSER_RETURN: '{parsed_result}' from final_num_str: '{final_num_str}'")
                return parsed_result
            except ValueError:
                # self.log_message(f"DEBUG_PARSER_ERROR: ValueError for '{final_num_str}'")
                return "Error: Invalid Number"
        # self.log_message("DEBUG_PARSER_RETURN: 'N/A' (No known indicator or values)")
        return "N/A"

    def update_live_weight_label(self, text_to_display):
        self.log_message(f"DEBUG_LIVE_WEIGHT_UPDATE: Setting Live Weight to '{text_to_display}'")  # <--- เพิ่ม Log นี้
        if text_to_display is not None and isinstance(text_to_display, str):
            self.current_weight_var.set(text_to_display)
        else:
            self.current_weight_var.set("---")

    def start_reading(self):
        self.log_message("DEBUG_START_READING: Called.")
        if self.is_reading:
            self.log_message("DEBUG_START_READING: Already reading. Disconnect first.")
            return

        com_port = self.com_port_var.get()
        try:
            baud_rate = int(self.baud_rate_var.get())
            parity_key = self.parity_var.get()
            parity = self.parity_map[parity_key]
            stop_bits_key = self.stop_bits_var.get()
            stop_bits = self.stop_bits_map[stop_bits_key]
            byte_size_key = self.byte_size_var.get()
            byte_size = self.byte_size_map[byte_size_key]
            timeout_val_ui = float(self.timeout_var.get())
            if timeout_val_ui <= 0:
                self.log_message("DEBUG_START_READING: Invalid timeout, using 1.0s.")
                messagebox.showwarning("Input Warning",
                                       "Read Timeout must be a positive number. Using 1.0s as default.")
                timeout_val_ui = 1.0
        except ValueError:
            self.log_message("DEBUG_START_READING: ValueError in config.")
            messagebox.showerror("Input Error", "Baud Rate and Read Timeout must be valid numbers.")
            self.update_button_state()
            return
        except KeyError:
            self.log_message("DEBUG_START_READING: KeyError in config selection.")
            messagebox.showerror("Input Error", "Invalid selection for Parity, Stop Bits, or Byte Size.")
            self.update_button_state()
            return

        try:
            self.log_message(
                f"DEBUG_START_READING: Attempting connect: {com_port}@{baud_rate}, Timeout:{timeout_val_ui}s")
            if self.ser and self.ser.is_open:
                self.log_message("DEBUG_START_READING: Closing previous open port.")
                self.ser.close()

            self.ser = serial.Serial(port=com_port, baudrate=baud_rate, parity=parity,
                                     stopbits=stop_bits, bytesize=byte_size, timeout=timeout_val_ui)

            if self.ser.is_open:
                self.log_message(f"DEBUG_START_READING: Successfully connected to {com_port}.")
                self.is_reading = True
                while not self.data_queue.empty():  # Clear queue
                    try:
                        self.data_queue.get_nowait()
                    except queue.Empty:
                        break
                self.log_message("DEBUG_START_READING: Data queue cleared.")

                self.read_thread = threading.Thread(target=self.read_serial_data, name="RS232ReadThread", daemon=True)
                self.read_thread.start()
                self.log_message(
                    f"DEBUG_START_READING: Thread '{self.read_thread.name}' started. Alive: {self.read_thread.is_alive()}")

                self.update_button_state()
                self.root.after(self.check_queue_interval, self.process_serial_data_queue)
                self.log_message("DEBUG_START_READING: Queue processor scheduled.")
            else:
                self.log_message(f"DEBUG_START_READING: Failed to open {com_port} (not open, no exception).")
                messagebox.showerror("Connection Error", f"Could not open serial port {com_port}.")
                self.is_reading = False
                self.update_button_state()
        except serial.SerialException as e:
            self.log_message(f"DEBUG_START_READING: SerialException: {e}")
            messagebox.showerror("Connection Error", f"Could not connect to {com_port}.\nError: {e}")
            self.is_reading = False
            self.ser = None
            self.update_button_state()
        except Exception as e_conn:
            self.log_message(f"DEBUG_START_READING: Unexpected connection error: {e_conn}")
            messagebox.showerror("Error", f"An unexpected error occurred during connection:\n{e_conn}")
            self.is_reading = False
            self.ser = None
            self.update_button_state()

    def read_serial_data(self):
        thread_name = threading.current_thread().name
        self.data_queue.put({"log_direct": f"DEBUG_THREAD ({thread_name}): ENTERING. is_reading: {self.is_reading}"})
        try:
            loop_count = 0
            consecutive_timeouts = 0
            max_consecutive_timeouts_to_log = 5  # หรือค่าที่เหมาะสม

            while self.is_reading and self.ser and self.ser.is_open:
                loop_count += 1
                raw_line_bytes = self.ser.readline()

                if raw_line_bytes:  # <--- **เฉพาะเมื่อมีข้อมูลเท่านั้นที่จะประมวลผลและ put data payload**
                    consecutive_timeouts = 0
                    # self.data_queue.put({"log_direct": f"DEBUG_THREAD ({thread_name}): Loop {loop_count}, Bytes Read: {len(raw_line_bytes)}, Data: {raw_line_bytes!r}"})

                    cleaned_text_for_display_and_parse = ""
                    try:
                        decoded_with_control_chars = raw_line_bytes.decode('latin-1', errors='replace')
                        cleaned_text_for_display_and_parse = decoded_with_control_chars.replace('\x02', '').replace(
                            '\x03', '').strip()
                    except Exception as decode_err:
                        self.data_queue.put(
                            {"error": f"Decode/Clean Error ({thread_name}): {decode_err} | Raw: {raw_line_bytes!r}"})
                        continue

                    parsed_numeric_str = self.parse_scale_data(cleaned_text_for_display_and_parse)

                    update_payload = {
                        "cleaned_data_for_live": cleaned_text_for_display_and_parse,
                        "parsed_numeric_str_for_live": parsed_numeric_str,
                        "cleaned_data_for_log": cleaned_text_for_display_and_parse,
                        "parsed_data_for_log": parsed_numeric_str
                    }
                    self.data_queue.put(update_payload)
                    # self.data_queue.put({"log_direct": f"DEBUG_THREAD ({thread_name}): Put DATA_PAYLOAD."})

                else:  # readline() timed out or returned empty bytes
                    consecutive_timeouts += 1
                    if consecutive_timeouts <= max_consecutive_timeouts_to_log or consecutive_timeouts % 50 == 0:
                        self.data_queue.put({
                                                "log_direct": f"DEBUG_THREAD ({thread_name}): Loop {loop_count}, Readline timeout/empty. (Timeout #{consecutive_timeouts})"})
                    # **ไม่มีการ put data payload ที่นี่**

                time.sleep(0.03)  # หรือค่าที่คุณต้องการ

            self.data_queue.put({"log_direct": f"DEBUG_THREAD ({thread_name}): Exited while loop."})
        except Exception as e_thread_main:
            self.data_queue.put({"error": f"UNHANDLED Thread Exc ({thread_name}): {e_thread_main}"})
        finally:
            self.data_queue.put({"log_direct": f"DEBUG_THREAD ({thread_name}): EXITING."})

    def parse_scale_data(self, cleaned_text):  # Parameter คือ cleaned_text
        # self.log_message(f"DEBUG_PARSER_INPUT: '{cleaned_text}'")

        # Pattern 1: "1CH" ตามด้วยกลุ่มของเลข 0 (อย่างน้อย 3 ตัว) -> ตีความเป็น "0"
        match_1ch_zero = re.search(r"1CH\s+(0{3,})", cleaned_text)
        if match_1ch_zero:
            # self.log_message(f"DEBUG_PARSER_MATCH: 1CH Zero: {match_1ch_zero.group(1)}")
            return "0"  # คืน "0" โดยตรง

        # Pattern 2: "1BH" หรือ "1@H" ตามด้วยตัวเลข (อาจจะมี 0 นำหน้า)
        known_weight_prefixes = [
            ("1BH", r"1BH\s+(\d+)"),
            ("1@H", r"1@H\s+(\d+)"),
            ("1CH", r"1CH\s+(0{3,})"),
            ("1Rh", r"1Rh\s+(0{3,})")
        ]

        # เราจะหา match จากท้ายสตริงขึ้นมา หรือหาทั้งหมดแล้วเลือกอันที่ "ดูดีที่สุด"
        # ตัวอย่างนี้จะหาทั้งหมด แล้วถ้ามี match จะเอาตัวเลขจาก match สุดท้าย
        all_numeric_matches = []
        for prefix_text, pattern_regex in known_weight_prefixes:
            matches = re.findall(pattern_regex, cleaned_text)
            if matches:
                for num_str in matches:
                    all_numeric_matches.append(num_str)

        if all_numeric_matches:
            last_num_str_candidate = all_numeric_matches[-1]
            try:
                weight_value_int = int(last_num_str_candidate)  # ตัดศูนย์นำหน้า
                parsed_result = str(weight_value_int)
                # self.log_message(f"DEBUG_PARSER_RETURN: '{parsed_result}' from '{last_num_str_candidate}'")
                return parsed_result
            except ValueError:
                # self.log_message(f"DEBUG_PARSER_ERROR: ValueError for '{last_num_str_candidate}'")
                return "Error: Invalid Number"

        # ถ้าไม่เข้าเงื่อนไขไหนเลย
        # self.log_message("DEBUG_PARSER_RETURN: 'N/A' (No specific pattern matched)")
        return "N/A"

    def process_serial_data_queue(self):
        # self.log_message(f"DEBUG_QUEUE_PROC: Called. Queue size: {self.data_queue.qsize()}")
        try:
            items_processed_this_cycle = 0
            max_items_per_cycle = 10  # หรือ 5

            while not self.data_queue.empty() and items_processed_this_cycle < max_items_per_cycle:
                payload = None
                try:
                    payload = self.data_queue.get_nowait()
                    if isinstance(payload, dict):
                        if "log_direct" in payload:
                            self.log_message(payload["log_direct"])
                        elif "error" in payload:  # <--- ใช้ elif เพื่อให้แน่ใจว่าประมวลผลทีละประเภท
                            error_msg = payload["error"]
                            self.log_message(f"ERROR_FROM_THREAD: {error_msg}")
                            if "Serial Read Error" in error_msg or "UNHANDLED Thread Exc" in error_msg or "Thread Execution Error" in error_msg:
                                self.log_message("DEBUG_QUEUE_PROC: Critical error from thread, stopping.")
                                self.stop_reading()
                                break  # ออกจาก while loop ของการประมวลผล queue
                        elif "cleaned_data_for_live" in payload and "parsed_numeric_str_for_live" in payload:
                            parsed_numeric_live_data = payload.get("parsed_numeric_str_for_live")

                            cleaned_log_data = payload.get("cleaned_data_for_log")
                            parsed_log_data = payload.get("parsed_data_for_log")

                            # --- อัปเดต Live Weight Label ---
                            if parsed_numeric_live_data not in ["N/A", None] and "Error" not in parsed_numeric_live_data:
                                self.update_live_weight_label(parsed_numeric_live_data)

                            # --- Log Cleaned และ Parsed Data ไปยัง Log Area ---
                            if cleaned_log_data is not None:
                                self.log_message(f"Cleaned Raw: '{cleaned_log_data}'")
                            if parsed_log_data is not None:
                                self.log_message(f"Parsed Value: '{parsed_log_data}'")

                        # else: # กรณี payload เป็น dict แต่ไม่ใช่ type ที่รู้จัก (ไม่ควรเกิด)
                        # self.log_message(f"DEBUG_QUEUE_PROC: Unknown dict payload: {payload}")

                    # else: # กรณี payload ไม่ใช่ dict เลย (เช่นถ้าเราเคยใส่ None เพื่อ signal thread end)
                    # self.log_message(f"DEBUG_QUEUE_PROC: Received non-dict payload: {payload}")

                    items_processed_this_cycle += 1

                except queue.Empty:
                    break

                except Exception as e_proc_item:  # Error ขณะประมวลผล item หนึ่งๆ
                    self.log_message(
                        f"DEBUG_QUEUE_PROC_ITEM_ERROR: {e_proc_item} with payload: {payload}")  # Log error พร้อม payload

        except Exception as e_outer_proc:
            self.log_message(f"DEBUG_QUEUE_PROC_OUTER_ERROR: {e_outer_proc}")

        finally:
            if self.is_reading:
                # self.log_message("DEBUG_QUEUE_PROC: Rescheduling self.")
                self.root.after(self.check_queue_interval, self.process_serial_data_queue)

    def stop_reading(self):
        self.log_message(f"DEBUG_STOP_READING: Called. Current is_reading: {self.is_reading}")
        # if not self.is_reading and not (self.read_thread and self.read_thread.is_alive()):
        #     self.log_message("DEBUG_STOP_READING: Already stopped or thread not active.")
        #     return # อาจจะทำให้กด disconnect ซ้ำๆ แล้วไม่อัปเดตปุ่ม

        was_reading = self.is_reading
        self.is_reading = False
        self.log_message(f"DEBUG_STOP_READING: Set is_reading to False.")

        if self.read_thread and self.read_thread.is_alive():
            self.log_message(f"DEBUG_STOP_READING: Waiting for thread {self.read_thread.name} to join (max 0.2s)...")
            self.read_thread.join(timeout=0.2)  # ให้โอกาส thread จบเอง
            if self.read_thread.is_alive():
                self.log_message(f"DEBUG_STOP_READING: Thread {self.read_thread.name} still alive after join timeout.")
            else:
                self.log_message(f"DEBUG_STOP_READING: Thread {self.read_thread.name} joined successfully.")
        # self.read_thread = None # เคลียร์เมื่อจบจริงๆ

        if self.ser and self.ser.is_open:
            try:
                self.ser.close()
                self.log_message("DEBUG_STOP_READING: Serial port closed.")
            except Exception as e_close:
                self.log_message(f"DEBUG_STOP_READING: Error closing port: {e_close}")

        if was_reading or (
                not self.read_thread or not self.read_thread.is_alive()):  # อัปเดตปุ่มถ้ามีการเปลี่ยนแปลงสถานะ
            self.update_button_state()

    def toggle_connection(self):
        self.log_message("DEBUG_TOGGLE_CONNECTION: Called.")
        if self.is_reading:
            self.stop_reading()
        else:
            # Reset live weight display before connecting
            self.current_weight_var.set("---")
            self.start_reading()

    def update_button_state(self):
        # self.log_message(f"DEBUG_UPDATE_BUTTON: is_reading: {self.is_reading}, thread: {self.read_thread.name if self.read_thread else 'None'}, alive: {self.read_thread.is_alive() if self.read_thread else 'N/A'}")
        if self.is_reading and self.read_thread and self.read_thread.is_alive():
            self.connect_button.config(text="Disconnect")
            # self.log_message("DEBUG_UPDATE_BUTTON: Set to Disconnect")
        else:
            # ถ้า is_reading เป็น true แต่ thread ตายไปแล้ว ควรจะตั้ง is_reading เป็น false
            if self.is_reading and (not self.read_thread or not self.read_thread.is_alive()):
                self.log_message("DEBUG_UPDATE_BUTTON: Thread died, resetting is_reading to False.")
                self.is_reading = False
            self.connect_button.config(text="Connect & Read")
            # self.log_message("DEBUG_UPDATE_BUTTON: Set to Connect & Read")

    def on_closing(self):
        self.log_message("DEBUG_ON_CLOSING: Application closing.")
        self.stop_reading()  # เรียก stop_reading เพื่อจัดการ thread และ port

        # ไม่จำเป็นต้อง join thread ที่นี่อีก ถ้า stop_reading จัดการแล้ว
        # if self.read_thread and self.read_thread.is_alive():
        #      self.log_message("DEBUG_ON_CLOSING: Joining read_thread...")
        #      self.read_thread.join(timeout=0.5)
        #      if self.read_thread.is_alive():
        #          self.log_message("DEBUG_ON_CLOSING: Warning - read_thread did not terminate cleanly.")
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = RS232TesterApp(root)
    root.mainloop()