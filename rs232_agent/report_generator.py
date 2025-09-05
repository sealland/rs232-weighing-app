"""
Report Generator for RS232 Scale Client
สร้างรายงานบัตรชั่งแบบง่าย สามารถพิมพ์และ export ได้
รองรับการทำงานแบบ offline และ online
"""

import os
import csv
from datetime import datetime
from typing import Dict, List, Optional, Any
from tkinter import messagebox

class ReportGenerator:
    """
    สร้างรายงานบัตรชั่งแบบง่าย
    - รายงานบัตรชั่งเดี่ยว
    - รายงานสรุป
    - Export เป็น CSV
    - พิมพ์รายงาน
    """
    
    def __init__(self, weighing_ticket_manager):
        """
        เริ่มต้น Report Generator
        
        Args:
            weighing_ticket_manager: อ้างอิงไปยัง WeighingTicketManager
        """
        self.weighing_ticket_manager = weighing_ticket_manager
        self.report_template_dir = "reports"
        self.ensure_report_directory()
    
    def ensure_report_directory(self):
        """สร้างโฟลเดอร์สำหรับเก็บรายงานถ้ายังไม่มี"""
        try:
            if not os.path.exists(self.report_template_dir):
                os.makedirs(self.report_template_dir)
        except Exception as e:
            print(f"Error creating report directory: {e}")
    
    def generate_single_ticket_report(self, local_ticket_id: str) -> Optional[str]:
        """
        สร้างรายงานบัตรชั่งเดี่ยว
        
        Args:
            local_ticket_id: เลขที่บัตรชั่ง
            
        Returns:
            str: เนื้อหารายงาน หรือ None ถ้าล้มเหลว
        """
        try:
            # ดึงข้อมูลบัตรชั่ง
            ticket = self.weighing_ticket_manager.get_ticket(local_ticket_id)
            if not ticket:
                return None
            
            # สร้างรายงาน
            report = self.create_ticket_report_content(ticket)
            
            # บันทึกรายงาน
            filename = f"ticket_{local_ticket_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            filepath = os.path.join(self.report_template_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(report)
            
            print(f"✅ สร้างรายงานบัตรชั่งสำเร็จ: {filepath}")
            return filepath
            
        except Exception as e:
            print(f"Error generating single ticket report: {e}")
            return None
    
    def create_ticket_report_content(self, ticket: Dict[str, Any]) -> str:
        """
        สร้างเนื้อหารายงานบัตรชั่ง
        
        Args:
            ticket: ข้อมูลบัตรชั่ง
            
        Returns:
            str: เนื้อหารายงาน
        """
        try:
            # จัดรูปแบบวันที่
            weigh_in_time = datetime.fromisoformat(ticket['weigh_in_time']) if ticket['weigh_in_time'] else None
            weigh_out_time = datetime.fromisoformat(ticket['weigh_out_time']) if ticket['weigh_out_time'] else None
            
            # สร้างรายงาน
            report = f"""
{'='*60}
                    รายงานบัตรชั่ง
{'='*60}

เลขที่บัตรชั่ง: {ticket['local_ticket_id']}
สถานะ: {self.get_status_thai(ticket['status'])}

ข้อมูลรถ:
  เลขทะเบียน: {ticket['vehicle_number']}
  คนขับ: {ticket['driver_name']}
  รายการ: {ticket['product']}

ข้อมูลการชั่ง:
  น้ำหนักชั่งเข้า: {ticket['weight_in']} kg
  เวลาชั่งเข้า: {weigh_in_time.strftime('%d/%m/%Y %H:%M:%S') if weigh_in_time else 'N/A'}
"""
            
            # เพิ่มข้อมูลชั่งออกถ้ามี
            if ticket['status'] == 'completed':
                report += f"""
  น้ำหนักชั่งออก: {ticket['weight_out']} kg
  เวลาชั่งออก: {weigh_out_time.strftime('%d/%m/%Y %H:%M:%S') if weigh_out_time else 'N/A'}
  น้ำหนักสุทธิ: {ticket['net_weight']} kg
"""
            
            report += f"""
ข้อมูลระบบ:
  สาขา: {ticket['branch']} ({ticket['branch_prefix']})
  Scale Pattern: {ticket['scale_pattern']}
  สถานะ Sync: {'✅ Sync แล้ว' if ticket['synced'] else '⏳ ยังไม่ได้ Sync'}
  เลขที่ Server: {ticket['server_ticket_id'] if ticket['server_ticket_id'] else 'N/A'}

สร้างเมื่อ: {datetime.fromisoformat(ticket['created_at']).strftime('%d/%m/%Y %H:%M:%S') if ticket['created_at'] else 'N/A'}
อัปเดตล่าสุด: {datetime.fromisoformat(ticket['updated_at']).strftime('%d/%m/%Y %H:%M:%S') if ticket['updated_at'] else 'N/A'}

{'='*60}
            """
            
            return report.strip()
            
        except Exception as e:
            print(f"Error creating ticket report content: {e}")
            return f"Error creating report: {e}"
    
    def get_status_thai(self, status: str) -> str:
        """
        แปลงสถานะเป็นภาษาไทย
        
        Args:
            status: สถานะภาษาอังกฤษ
            
        Returns:
            str: สถานะภาษาไทย
        """
        status_map = {
            'active': 'กำลังดำเนินการ',
            'completed': 'เสร็จสิ้น',
            'synced': 'Sync แล้ว'
        }
        return status_map.get(status, status)
    
    def generate_summary_report(self, start_date: Optional[str] = None, 
                               end_date: Optional[str] = None) -> Optional[str]:
        """
        สร้างรายงานสรุป
        
        Args:
            start_date: วันที่เริ่มต้น (YYYY-MM-DD)
            end_date: วันที่สิ้นสุด (YYYY-MM-DD)
            
        Returns:
            str: เนื้อหารายงาน หรือ None ถ้าล้มเหลว
        """
        try:
            # ดึงสถิติ
            stats = self.weighing_ticket_manager.get_ticket_statistics()
            
            # ดึงรายการบัตรชั่ง
            active_tickets = self.weighing_ticket_manager.get_active_tickets()
            completed_tickets = self.weighing_ticket_manager.get_completed_tickets()
            
            # สร้างรายงาน
            report = f"""
{'='*60}
                    รายงานสรุปบัตรชั่ง
{'='*60}

วันที่: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
ช่วงเวลา: {start_date if start_date else 'ทั้งหมด'} ถึง {end_date if end_date else 'ปัจจุบัน'}

สถิติโดยรวม:
  จำนวนบัตรชั่งทั้งหมด: {stats['total_tickets']}
  จำนวนที่กำลังดำเนินการ: {stats['active_tickets']}
  จำนวนที่เสร็จสิ้น: {stats['completed_tickets']}
  จำนวนที่ Sync แล้ว: {stats['synced_tickets']}
  จำนวนที่ยังไม่ได้ Sync: {stats['unsynced_tickets']}

รายการบัตรชั่งที่กำลังดำเนินการ:
"""
            
            if active_tickets:
                for ticket in active_tickets[:10]:  # แสดงแค่ 10 รายการแรก
                    report += f"""
  - {ticket['local_ticket_id']}: {ticket['vehicle_number']} ({ticket['driver_name']})
    รายการ: {ticket['product']} | น้ำหนักเข้า: {ticket['weight_in']} kg
"""
                if len(active_tickets) > 10:
                    report += f"  ... และอีก {len(active_tickets) - 10} รายการ\n"
            else:
                report += "  ไม่มีบัตรชั่งที่กำลังดำเนินการ\n"
            
            report += f"""
รายการบัตรชั่งที่เสร็จสิ้น (10 รายการล่าสุด):
"""
            
            if completed_tickets:
                for ticket in completed_tickets[:10]:  # แสดงแค่ 10 รายการล่าสุด
                    report += f"""
  - {ticket['local_ticket_id']}: {ticket['vehicle_number']} ({ticket['driver_name']})
    รายการ: {ticket['product']} | น้ำหนักสุทธิ: {ticket['net_weight']} kg
    เวลา: {datetime.fromisoformat(ticket['weigh_out_time']).strftime('%d/%m/%Y %H:%M') if ticket['weigh_out_time'] else 'N/A'}
"""
                if len(completed_tickets) > 10:
                    report += f"  ... และอีก {len(completed_tickets) - 10} รายการ\n"
            else:
                report += "  ไม่มีบัตรชั่งที่เสร็จสิ้น\n"
            
            report += f"""
{'='*60}
            """
            
            # บันทึกรายงาน
            filename = f"summary_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            filepath = os.path.join(self.report_template_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(report)
            
            print(f"✅ สร้างรายงานสรุปสำเร็จ: {filepath}")
            return filepath
            
        except Exception as e:
            print(f"Error generating summary report: {e}")
            return None
    
    def export_tickets_to_csv(self, filename: str, tickets: List[Dict[str, Any]]) -> bool:
        """
        Export ข้อมูลบัตรชั่งเป็น CSV
        
        Args:
            filename: ชื่อไฟล์ CSV
            tickets: รายการบัตรชั่ง
            
        Returns:
            bool: True ถ้าสำเร็จ, False ถ้าล้มเหลว
        """
        try:
            filepath = os.path.join(self.report_template_dir, filename)
            
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                # กำหนดหัวข้อคอลัมน์
                fieldnames = [
                    'เลขที่บัตรชั่ง', 'เลขทะเบียนรถ', 'ชื่อคนขับ', 'รายการสินค้า',
                    'น้ำหนักเข้า (kg)', 'น้ำหนักออก (kg)', 'น้ำหนักสุทธิ (kg)',
                    'เวลาชั่งเข้า', 'เวลาชั่งออก', 'สถานะ', 'Sync', 'เลขที่ Server',
                    'สาขา', 'Prefix', 'Scale Pattern', 'สร้างเมื่อ', 'อัปเดตล่าสุด'
                ]
                
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                # เขียนข้อมูล
                for ticket in tickets:
                    row = {
                        'เลขที่บัตรชั่ง': ticket['local_ticket_id'],
                        'เลขทะเบียนรถ': ticket['vehicle_number'],
                        'ชื่อคนขับ': ticket['driver_name'],
                        'รายการสินค้า': ticket['product'],
                        'น้ำหนักเข้า (kg)': ticket['weight_in'],
                        'น้ำหนักออก (kg)': ticket['weight_out'] if ticket['weight_out'] else '',
                        'น้ำหนักสุทธิ (kg)': ticket['net_weight'] if ticket['net_weight'] else '',
                        'เวลาชั่งเข้า': ticket['weigh_in_time'],
                        'เวลาชั่งออก': ticket['weigh_out_time'] if ticket['weigh_out_time'] else '',
                        'สถานะ': self.get_status_thai(ticket['status']),
                        'Sync': '✅' if ticket['synced'] else '⏳',
                        'เลขที่ Server': ticket['server_ticket_id'] if ticket['server_ticket_id'] else '',
                        'สาขา': ticket['branch'],
                        'Prefix': ticket['branch_prefix'],
                        'Scale Pattern': ticket['scale_pattern'],
                        'สร้างเมื่อ': ticket['created_at'],
                        'อัปเดตล่าสุด': ticket['updated_at']
                    }
                    writer.writerow(row)
            
            print(f"✅ Export CSV สำเร็จ: {filepath}")
            return True
            
        except Exception as e:
            print(f"Error exporting to CSV: {e}")
            return False
    
    def export_all_tickets_to_csv(self) -> bool:
        """
        Export บัตรชั่งทั้งหมดเป็น CSV
        
        Returns:
            bool: True ถ้าสำเร็จ, False ถ้าล้มเหลว
        """
        try:
            # ดึงบัตรชั่งทั้งหมด
            active_tickets = self.weighing_ticket_manager.get_active_tickets()
            completed_tickets = self.weighing_ticket_manager.get_completed_tickets()
            
            all_tickets = active_tickets + completed_tickets
            
            if not all_tickets:
                print("⚠️ ไม่มีข้อมูลบัตรชั่งสำหรับ export")
                return False
            
            # สร้างชื่อไฟล์
            filename = f"all_tickets_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            
            return self.export_tickets_to_csv(filename, all_tickets)
            
        except Exception as e:
            print(f"Error exporting all tickets: {e}")
            return False
    
    def export_completed_tickets_to_csv(self) -> bool:
        """
        Export บัตรชั่งที่เสร็จสิ้นแล้วเป็น CSV
        
        Returns:
            bool: True ถ้าสำเร็จ, False ถ้าล้มเหลว
        """
        try:
            completed_tickets = self.weighing_ticket_manager.get_completed_tickets()
            
            if not completed_tickets:
                print("⚠️ ไม่มีบัตรชั่งที่เสร็จสิ้นสำหรับ export")
                return False
            
            # สร้างชื่อไฟล์
            filename = f"completed_tickets_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            
            return self.export_tickets_to_csv(filename, completed_tickets)
            
        except Exception as e:
            print(f"Error exporting completed tickets: {e}")
            return False
    
    def print_report(self, report_content: str, title: str = "รายงาน") -> bool:
        """
        พิมพ์รายงาน (แสดงในหน้าต่างใหม่)
        
        Args:
            report_content: เนื้อหารายงาน
            title: ชื่อรายงาน
            
        Returns:
            bool: True ถ้าสำเร็จ, False ถ้าล้มเหลว
        """
        try:
            # สร้างหน้าต่างใหม่สำหรับแสดงรายงาน
            import tkinter as tk
            from tkinter import scrolledtext
            
            print_window = tk.Toplevel()
            print_window.title(f"พิมพ์รายงาน - {title}")
            print_window.geometry("800x600")
            
            # สร้าง text area
            text_area = scrolledtext.ScrolledText(print_window, wrap=tk.WORD, font=('Courier', 10))
            text_area.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            # แสดงเนื้อหารายงาน
            text_area.insert(tk.END, report_content)
            text_area.config(state=tk.DISABLED)
            
            # ปุ่มพิมพ์
            def print_report():
                try:
                    # ใช้ print dialog ของระบบ
                    print_window.update()
                    print_window.focus_force()
                    
                    # ส่งไปยัง printer
                    import subprocess
                    import tempfile
                    
                    # สร้างไฟล์ชั่วคราว
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', 
                                                   delete=False, encoding='utf-8') as f:
                        f.write(report_content)
                        temp_file = f.name
                    
                    # เปิดด้วย default text editor (สามารถพิมพ์ได้)
                    if os.name == 'nt':  # Windows
                        os.startfile(temp_file)
                    else:  # Linux/Mac
                        subprocess.run(['xdg-open', temp_file])
                    
                    messagebox.showinfo("พิมพ์รายงาน", 
                                      "รายงานถูกเปิดในโปรแกรมแก้ไขข้อความ\n"
                                      "ใช้เมนู File > Print เพื่อพิมพ์")
                    
                except Exception as e:
                    messagebox.showerror("ข้อผิดพลาด", f"ไม่สามารถพิมพ์รายงานได้: {e}")
            
            # ปุ่มปิด
            def close_window():
                print_window.destroy()
            
            # สร้างปุ่ม
            button_frame = tk.Frame(print_window)
            button_frame.pack(pady=10)
            
            print_btn = tk.Button(button_frame, text="🖨️ พิมพ์รายงาน", 
                                command=print_report, bg='#4CAF50', fg='white')
            print_btn.pack(side=tk.LEFT, padx=5)
            
            close_btn = tk.Button(button_frame, text="ปิด", 
                                command=close_window, bg='#f44336', fg='white')
            close_btn.pack(side=tk.LEFT, padx=5)
            
            return True
            
        except Exception as e:
            print(f"Error printing report: {e}")
            return False
    
    def get_report_list(self) -> List[str]:
        """
        ดึงรายการไฟล์รายงานที่มีอยู่
        
        Returns:
            List: รายการไฟล์รายงาน
        """
        try:
            if not os.path.exists(self.report_template_dir):
                return []
            
            files = []
            for filename in os.listdir(self.report_template_dir):
                if filename.endswith(('.txt', '.csv')):
                    filepath = os.path.join(self.report_template_dir, filename)
                    file_size = os.path.getsize(filepath)
                    file_time = os.path.getmtime(filepath)
                    
                    files.append({
                        'filename': filename,
                        'filepath': filepath,
                        'size': file_size,
                        'modified': datetime.fromtimestamp(file_time)
                    })
            
            # เรียงตามเวลาที่แก้ไขล่าสุด
            files.sort(key=lambda x: x['modified'], reverse=True)
            
            return files
            
        except Exception as e:
            print(f"Error getting report list: {e}")
            return []
