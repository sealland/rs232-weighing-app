"""
Hybrid Lightweight Manager for RS232 Scale Client
จัดการการทำงานแบบ hybrid ระหว่าง online และ offline mode
โดยไม่กระทบระบบ online เดิม
"""

import time
import json
import asyncio
import threading
from datetime import datetime
from typing import Dict, List, Optional, Any

class HybridLightweightManager:
    """
    จัดการการทำงานแบบ hybrid ระหว่าง online และ offline mode
    - Online: ส่งข้อมูลทันที + เก็บใน local
    - Offline: เก็บข้อมูลใน local เท่านั้น
    - Sync: อัตโนมัติเมื่อกลับ online
    """
    
    def __init__(self, client_gui):
        """
        เริ่มต้น Hybrid Manager
        
        Args:
            client_gui: อ้างอิงไปยัง GUI หลัก
        """
        self.client_gui = client_gui
        self.is_hybrid_mode = True  # เปิดใช้งาน hybrid mode เสมอ
        self.sync_interval = 5  # sync ทุก 5 วินาที
        self.last_sync_time = 0
        self.sync_running = False
        
        # เริ่ม sync timer
        self.start_sync_timer()
    
    def start_sync_timer(self):
        """เริ่ม timer สำหรับ sync อัตโนมัติ"""
        def sync_timer():
            if self.client_gui.is_running and not self.sync_running:
                self.auto_sync_when_online()
            # ตั้งเวลาเรียกฟังก์ชันนี้อีกครั้ง
            if hasattr(self.client_gui, 'root'):
                self.client_gui.root.after(self.sync_interval * 1000, sync_timer)
        
        # เริ่ม timer ครั้งแรก
        if hasattr(self.client_gui, 'root'):
            self.client_gui.root.after(self.sync_interval * 1000, sync_timer)
    
    def process_weight_data(self, weight: str, context: Dict[str, Any]) -> bool:
        """
        ประมวลผลข้อมูลน้ำหนักแบบ hybrid
        
        Args:
            weight: น้ำหนักที่อ่านได้
            context: ข้อมูลเพิ่มเติม (branch, scale_pattern, etc.)
            
        Returns:
            bool: True ถ้าสำเร็จ, False ถ้าล้มเหลว
        """
        try:
            # สร้างข้อมูลสำหรับบันทึก
            weight_data = {
                'weight': weight,
                'timestamp': datetime.now(),
                'context': context,
                'synced': False
            }
            
            if self.client_gui.is_connected:
                # Online Mode: ส่งข้อมูลทันที + เก็บใน Local
                success = self.send_to_server_immediately(weight_data)
                if success:
                    # สำเร็จ: เก็บใน local database เป็น backup
                    self.save_to_local_database(weight_data, synced=True)
                    self.client_gui.log_message(f"✅ Online Mode: ส่งข้อมูล {weight} kg สำเร็จ")
                    return True
                else:
                    # ล้มเหลว: เก็บใน local database แบบไม่ sync
                    self.save_to_local_database(weight_data, synced=False)
                    self.client_gui.log_message(f"⚠️ Online Mode: ส่งข้อมูลล้มเหลว เก็บใน local")
                    return False
            else:
                # Offline Mode: เก็บใน local database เท่านั้น
                self.save_to_local_database(weight_data, synced=False)
                self.client_gui.log_message(f"📱 Offline Mode: เก็บข้อมูล {weight} kg ใน local")
                return True
                
        except Exception as e:
            self.client_gui.log_message(f"❌ Error processing weight data: {e}")
            return False
    
    def send_to_server_immediately(self, weight_data: Dict[str, Any]) -> bool:
        """
        ส่งข้อมูลไปยัง server ทันที
        
        Args:
            weight_data: ข้อมูลน้ำหนัก
            
        Returns:
            bool: True ถ้าสำเร็จ, False ถ้าล้มเหลว
        """
        try:
            if not self.client_gui.websocket or self.client_gui.websocket.closed:
                return False
            
            # สร้าง message สำหรับส่งไป server
            message = {
                "client_id": self.client_gui.client_id_var.get(),
                "weight": weight_data['weight'],
                "timestamp": time.time(),
                "branch": weight_data['context'].get('branch', ''),
                "branch_prefix": self.client_gui.get_branch_prefix(
                    weight_data['context'].get('branch', '')
                ),
                "scale_pattern": weight_data['context'].get('scale_pattern', ''),
                "hybrid_sync": True  # แสดงว่าเป็นข้อมูลจาก hybrid mode
            }
            
            # ส่งข้อมูลแบบ async
            if hasattr(self.client_gui, 'loop') and self.client_gui.loop:
                asyncio.run_coroutine_threadsafe(
                    self.client_gui.websocket.send(json.dumps(message)),
                    self.client_gui.loop
                )
                return True
            else:
                return False
                
        except Exception as e:
            self.client_gui.log_message(f"Error sending to server: {e}")
            return False
    
    def save_to_local_database(self, weight_data: Dict[str, Any], synced: bool = False):
        """
        บันทึกข้อมูลใน local database
        
        Args:
            weight_data: ข้อมูลน้ำหนัก
            synced: สถานะการ sync
        """
        try:
            if hasattr(self.client_gui, 'local_data_manager'):
                record_id = self.client_gui.local_data_manager.add_weight_record(
                    weight=weight_data['weight'],
                    branch=weight_data['context'].get('branch', ''),
                    scale_pattern=weight_data['context'].get('scale_pattern', ''),
                    synced=synced
                )
                
                if record_id:
                    self.client_gui.log_message(f"💾 บันทึกข้อมูลใน local database: ID {record_id}")
                else:
                    self.client_gui.log_message("❌ ไม่สามารถบันทึกข้อมูลใน local database ได้")
                    
        except Exception as e:
            self.client_gui.log_message(f"Error saving to local database: {e}")
    
    def auto_sync_when_online(self):
        """Sync ข้อมูลอัตโนมัติเมื่อกลับ online"""
        try:
            if not self.client_gui.is_connected:
                return
            
            current_time = time.time()
            if current_time - self.last_sync_time < self.sync_interval:
                return
            
            self.sync_running = True
            
            # ดึงข้อมูลที่ยังไม่ได้ sync
            if hasattr(self.client_gui, 'local_data_manager'):
                unsynced_data = self.client_gui.local_data_manager.get_unsynced_data()
                
                if unsynced_data:
                    self.client_gui.log_message(f"🔄 เริ่ม sync ข้อมูล {len(unsynced_data)} รายการ...")
                    
                    synced_count = 0
                    for record in unsynced_data:
                        if self.sync_single_record(record):
                            synced_count += 1
                    
                    if synced_count > 0:
                        self.client_gui.log_message(f"✅ Sync สำเร็จ {synced_count} รายการ")
                        self.last_sync_time = current_time
                    else:
                        self.client_gui.log_message("⚠️ ไม่มีข้อมูลที่ sync สำเร็จ")
                else:
                    # ไม่มีข้อมูลที่ต้อง sync
                    pass
            
            self.sync_running = False
            
        except Exception as e:
            self.client_gui.log_message(f"Error in auto sync: {e}")
            self.sync_running = False
    
    def sync_single_record(self, record: tuple) -> bool:
        """
        Sync ข้อมูลเดี่ยว
        
        Args:
            record: ข้อมูลจาก local database
            
        Returns:
            bool: True ถ้าสำเร็จ, False ถ้าล้มเหลว
        """
        try:
            # สร้าง message สำหรับ sync
            message = {
                "client_id": self.client_gui.client_id_var.get(),
                "weight": str(record[1]),  # weight
                "timestamp": time.time(),
                "branch": record[4] if record[4] else self.client_gui.branch_var.get(),
                "branch_prefix": self.client_gui.get_branch_prefix(
                    record[4] if record[4] else self.client_gui.branch_var.get()
                ),
                "scale_pattern": record[5] if record[5] else self.client_gui.scale_pattern_var.get(),
                "offline_sync": True,  # แสดงว่าเป็นข้อมูลจาก offline sync
                "original_timestamp": record[2]  # timestamp เดิมจาก local
            }
            
            # ส่งข้อมูล
            if self.send_to_server_immediately({'weight': message['weight'], 'context': message}):
                # ทำเครื่องหมายว่า sync แล้ว
                if hasattr(self.client_gui, 'local_data_manager'):
                    self.client_gui.local_data_manager.mark_as_synced(record[0])
                return True
            else:
                return False
                
        except Exception as e:
            self.client_gui.log_message(f"Error syncing record {record[0]}: {e}")
            return False
    
    def force_sync(self) -> bool:
        """
        บังคับให้ sync ข้อมูลทันที
        
        Returns:
            bool: True ถ้าสำเร็จ, False ถ้าล้มเหลว
        """
        try:
            if not self.client_gui.is_connected:
                self.client_gui.log_message("❌ ไม่สามารถ sync ได้เมื่อ offline")
                return False
            
            self.client_gui.log_message("🔄 เริ่ม force sync...")
            self.auto_sync_when_online()
            return True
            
        except Exception as e:
            self.client_gui.log_message(f"Error in force sync: {e}")
            return False
    
    def get_hybrid_status(self) -> Dict[str, Any]:
        """
        ดึงสถานะ hybrid mode
        
        Returns:
            Dict: สถานะต่างๆ
        """
        try:
            if hasattr(self.client_gui, 'local_data_manager'):
                stats = self.client_gui.local_data_manager.get_local_stats()
                
                return {
                    'hybrid_mode': self.is_hybrid_mode,
                    'is_online': self.client_gui.is_connected,
                    'last_sync': self.last_sync_time,
                    'sync_running': self.sync_running,
                    'local_stats': stats
                }
            else:
                return {
                    'hybrid_mode': self.is_hybrid_mode,
                    'is_online': self.client_gui.is_connected,
                    'last_sync': self.last_sync_time,
                    'sync_running': self.sync_running,
                    'local_stats': {'total': 0, 'synced': 0, 'unsynced': 0}
                }
                
        except Exception as e:
            self.client_gui.log_message(f"Error getting hybrid status: {e}")
            return {
                'hybrid_mode': False,
                'is_online': False,
                'last_sync': 0,
                'sync_running': False,
                'local_stats': {'total': 0, 'synced': 0, 'unsynced': 0}
            }
