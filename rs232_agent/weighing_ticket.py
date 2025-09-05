"""
Weighing Ticket Manager for RS232 Scale Client
จัดการบัตรชั่งแบบ offline และ online
รองรับการสร้างบัตรชั่ง, เสร็จสิ้นบัตรชั่ง, และ sync ข้อมูล
"""

import time
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

class WeighingTicketManager:
    """
    จัดการบัตรชั่งแบบ offline และ online
    - สร้างบัตรชั่งใหม่
    - เสร็จสิ้นบัตรชั่ง
    - เก็บข้อมูลใน local database
    - sync ข้อมูลไปยัง server
    """
    
    def __init__(self, db_path='local_weight_data.db'):
        """
        เริ่มต้น Weighing Ticket Manager
        
        Args:
            db_path: path ของฐานข้อมูล SQLite
        """
        self.db_path = db_path
        self.conn = None
        self.connect()
        self.create_tables()
    
    def connect(self):
        """เชื่อมต่อฐานข้อมูล SQLite"""
        try:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row  # ทำให้เข้าถึงคอลัมน์ด้วยชื่อได้
        except Exception as e:
            print(f"Error connecting to weighing ticket DB: {e}")
    
    def create_tables(self):
        """สร้างตารางสำหรับบัตรชั่ง"""
        try:
            cursor = self.conn.cursor()
            
            # ตารางสำหรับเก็บบัตรชั่ง
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS weighing_tickets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    local_ticket_id TEXT UNIQUE,           -- เลขที่บัตรชั่งชั่วคราว (L001, L002, ...)
                    vehicle_number TEXT,                   -- เลขทะเบียนรถ
                    driver_name TEXT,                      -- ชื่อคนขับ
                    product TEXT,                          -- รายการสินค้า
                    weight_in REAL,                        -- น้ำหนักชั่งเข้า
                    weight_out REAL,                       -- น้ำหนักชั่งออก
                    net_weight REAL,                       -- น้ำหนักสุทธิ
                    weigh_in_time DATETIME,                -- เวลาชั่งเข้า
                    weigh_out_time DATETIME,               -- เวลาชั่งออก
                    status TEXT DEFAULT 'active',          -- สถานะ (active, completed, synced)
                    synced BOOLEAN DEFAULT 0,              -- สถานะการ sync
                    server_ticket_id TEXT,                 -- เลขที่บัตรชั่งจาก Server (เมื่อ sync แล้ว)
                    branch TEXT,                           -- สาขา
                    branch_prefix TEXT,                    -- Prefix ของสาขา
                    scale_pattern TEXT,                    -- Scale pattern ที่ใช้
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # สร้าง index สำหรับการค้นหา
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_local_ticket_id 
                ON weighing_tickets(local_ticket_id)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_status 
                ON weighing_tickets(status)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_synced 
                ON weighing_tickets(synced)
            ''')
            
            self.conn.commit()
            
        except Exception as e:
            print(f"Error creating weighing ticket tables: {e}")
    
    def generate_local_ticket_id(self) -> str:
        """
        สร้างเลขที่บัตรชั่งชั่วคราว
        
        Returns:
            str: เลขที่บัตรชั่งชั่วคราว (L001, L002, ...)
        """
        try:
            cursor = self.conn.cursor()
            
            # นับจำนวนบัตรชั่งทั้งหมด
            cursor.execute('SELECT COUNT(*) FROM weighing_tickets')
            count = cursor.fetchone()[0]
            
            # สร้างเลขที่บัตรชั่งใหม่
            new_id = f"L{count + 1:03d}"
            
            # ตรวจสอบว่าเลขที่ซ้ำหรือไม่
            while self.ticket_id_exists(new_id):
                count += 1
                new_id = f"L{count + 1:03d}"
            
            return new_id
            
        except Exception as e:
            print(f"Error generating ticket ID: {e}")
            # ใช้ timestamp เป็น fallback
            return f"L{int(time.time())}"
    
    def ticket_id_exists(self, ticket_id: str) -> bool:
        """
        ตรวจสอบว่าเลขที่บัตรชั่งมีอยู่แล้วหรือไม่
        
        Args:
            ticket_id: เลขที่บัตรชั่ง
            
        Returns:
            bool: True ถ้ามีอยู่แล้ว, False ถ้าไม่มี
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute('SELECT 1 FROM weighing_tickets WHERE local_ticket_id = ?', (ticket_id,))
            return cursor.fetchone() is not None
        except Exception as e:
            print(f"Error checking ticket ID existence: {e}")
            return False
    
    def create_weighing_ticket(self, vehicle_number: str, driver_name: str, product: str, 
                              weight_in: float, branch: str = "", branch_prefix: str = "", 
                              scale_pattern: str = "") -> Optional[str]:
        """
        สร้างบัตรชั่งใหม่
        
        Args:
            vehicle_number: เลขทะเบียนรถ
            driver_name: ชื่อคนขับ
            product: รายการสินค้า
            weight_in: น้ำหนักชั่งเข้า
            branch: สาขา
            branch_prefix: Prefix ของสาขา
            scale_pattern: Scale pattern ที่ใช้
            
        Returns:
            str: เลขที่บัตรชั่งที่สร้าง หรือ None ถ้าล้มเหลว
        """
        try:
            cursor = self.conn.cursor()
            
            # สร้างเลขที่บัตรชั่งใหม่
            local_ticket_id = self.generate_local_ticket_id()
            
            # บันทึกข้อมูลบัตรชั่ง
            cursor.execute('''
                INSERT INTO weighing_tickets 
                (local_ticket_id, vehicle_number, driver_name, product, weight_in, 
                 weigh_in_time, status, branch, branch_prefix, scale_pattern)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                local_ticket_id, vehicle_number, driver_name, product, weight_in,
                datetime.now(), 'active', branch, branch_prefix, scale_pattern
            ))
            
            self.conn.commit()
            
            print(f"✅ สร้างบัตรชั่งใหม่สำเร็จ: {local_ticket_id}")
            return local_ticket_id
            
        except Exception as e:
            print(f"Error creating weighing ticket: {e}")
            return None
    
    def complete_weighing_ticket(self, local_ticket_id: str, weight_out: float) -> bool:
        """
        เสร็จสิ้นบัตรชั่ง (ชั่งออก)
        
        Args:
            local_ticket_id: เลขที่บัตรชั่ง
            weight_out: น้ำหนักชั่งออก
            
        Returns:
            bool: True ถ้าสำเร็จ, False ถ้าล้มเหลว
        """
        try:
            cursor = self.conn.cursor()
            
            # ดึงข้อมูลบัตรชั่ง
            cursor.execute('SELECT weight_in FROM weighing_tickets WHERE local_ticket_id = ?', (local_ticket_id,))
            result = cursor.fetchone()
            
            if not result:
                print(f"❌ ไม่พบบัตรชั่ง: {local_ticket_id}")
                return False
            
            weight_in = float(result[0])
            net_weight = weight_in - weight_out
            
            # อัปเดตข้อมูล
            cursor.execute('''
                UPDATE weighing_tickets 
                SET weight_out = ?, net_weight = ?, weigh_out_time = ?, 
                    status = 'completed', updated_at = CURRENT_TIMESTAMP
                WHERE local_ticket_id = ?
            ''', (weight_out, net_weight, datetime.now(), local_ticket_id))
            
            self.conn.commit()
            
            print(f"✅ เสร็จสิ้นบัตรชั่ง: {local_ticket_id}, น้ำหนักสุทธิ: {net_weight} kg")
            return True
            
        except Exception as e:
            print(f"Error completing weighing ticket: {e}")
            return False
    
    def get_ticket(self, local_ticket_id: str) -> Optional[Dict[str, Any]]:
        """
        ดึงข้อมูลบัตรชั่ง
        
        Args:
            local_ticket_id: เลขที่บัตรชั่ง
            
        Returns:
            Dict: ข้อมูลบัตรชั่ง หรือ None ถ้าไม่พบ
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT * FROM weighing_tickets 
                WHERE local_ticket_id = ?
            ''', (local_ticket_id,))
            
            result = cursor.fetchone()
            if result:
                return dict(result)
            else:
                return None
                
        except Exception as e:
            print(f"Error getting ticket: {e}")
            return None
    
    def get_active_tickets(self) -> List[Dict[str, Any]]:
        """
        ดึงรายการบัตรชั่งที่ยังไม่เสร็จสิ้น
        
        Returns:
            List: รายการบัตรชั่งที่ active
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT * FROM weighing_tickets 
                WHERE status = 'active' 
                ORDER BY created_at DESC
            ''')
            
            tickets = []
            for row in cursor.fetchall():
                tickets.append(dict(row))
            
            return tickets
            
        except Exception as e:
            print(f"Error getting active tickets: {e}")
            return []
    
    def get_completed_tickets(self) -> List[Dict[str, Any]]:
        """
        ดึงรายการบัตรชั่งที่เสร็จสิ้นแล้ว
        
        Returns:
            List: รายการบัตรชั่งที่เสร็จสิ้น
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT * FROM weighing_tickets 
                WHERE status = 'completed' 
                ORDER BY weigh_out_time DESC
            ''')
            
            tickets = []
            for row in cursor.fetchall():
                tickets.append(dict(row))
            
            return tickets
            
        except Exception as e:
            print(f"Error getting completed tickets: {e}")
            return []
    
    def get_unsynced_tickets(self) -> List[Dict[str, Any]]:
        """
        ดึงรายการบัตรชั่งที่ยังไม่ได้ sync
        
        Returns:
            List: รายการบัตรชั่งที่ยังไม่ได้ sync
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT * FROM weighing_tickets 
                WHERE synced = 0 
                ORDER BY created_at
            ''')
            
            tickets = []
            for row in cursor.fetchall():
                tickets.append(dict(row))
            
            return tickets
            
        except Exception as e:
            print(f"Error getting unsynced tickets: {e}")
            return []
    
    def mark_ticket_as_synced(self, local_ticket_id: str, server_ticket_id: str) -> bool:
        """
        ทำเครื่องหมายว่าบัตรชั่ง sync แล้ว
        
        Args:
            local_ticket_id: เลขที่บัตรชั่งใน local
            server_ticket_id: เลขที่บัตรชั่งจาก server
            
        Returns:
            bool: True ถ้าสำเร็จ, False ถ้าล้มเหลว
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                UPDATE weighing_tickets 
                SET synced = 1, server_ticket_id = ?, updated_at = CURRENT_TIMESTAMP
                WHERE local_ticket_id = ?
            ''', (server_ticket_id, local_ticket_id))
            
            self.conn.commit()
            
            print(f"✅ บัตรชั่ง {local_ticket_id} sync แล้ว: {server_ticket_id}")
            return True
            
        except Exception as e:
            print(f"Error marking ticket as synced: {e}")
            return False
    
    def get_ticket_statistics(self) -> Dict[str, Any]:
        """
        ดึงสถิติบัตรชั่ง
        
        Returns:
            Dict: สถิติต่างๆ
        """
        try:
            cursor = self.conn.cursor()
            
            # นับจำนวนทั้งหมด
            cursor.execute('SELECT COUNT(*) FROM weighing_tickets')
            total_tickets = cursor.fetchone()[0]
            
            # นับจำนวนที่ active
            cursor.execute('SELECT COUNT(*) FROM weighing_tickets WHERE status = "active"')
            active_tickets = cursor.fetchone()[0]
            
            # นับจำนวนที่เสร็จสิ้น
            cursor.execute('SELECT COUNT(*) FROM weighing_tickets WHERE status = "completed"')
            completed_tickets = cursor.fetchone()[0]
            
            # นับจำนวนที่ sync แล้ว
            cursor.execute('SELECT COUNT(*) FROM weighing_tickets WHERE synced = 1')
            synced_tickets = cursor.fetchone()[0]
            
            # นับจำนวนที่ยังไม่ได้ sync
            cursor.execute('SELECT COUNT(*) FROM weighing_tickets WHERE synced = 0')
            unsynced_tickets = cursor.fetchone()[0]
            
            return {
                'total_tickets': total_tickets,
                'active_tickets': active_tickets,
                'completed_tickets': completed_tickets,
                'synced_tickets': synced_tickets,
                'unsynced_tickets': unsynced_tickets
            }
            
        except Exception as e:
            print(f"Error getting ticket statistics: {e}")
            return {
                'total_tickets': 0,
                'active_tickets': 0,
                'completed_tickets': 0,
                'synced_tickets': 0,
                'unsynced_tickets': 0
            }
    
    def search_tickets(self, search_term: str, search_type: str = 'all') -> List[Dict[str, Any]]:
        """
        ค้นหาบัตรชั่ง
        
        Args:
            search_term: คำค้นหา
            search_type: ประเภทการค้นหา (all, vehicle, driver, product)
            
        Returns:
            List: รายการบัตรชั่งที่ตรงกับคำค้นหา
        """
        try:
            cursor = self.conn.cursor()
            
            if search_type == 'vehicle':
                cursor.execute('''
                    SELECT * FROM weighing_tickets 
                    WHERE vehicle_number LIKE ? 
                    ORDER BY created_at DESC
                ''', (f'%{search_term}%',))
            elif search_type == 'driver':
                cursor.execute('''
                    SELECT * FROM weighing_tickets 
                    WHERE driver_name LIKE ? 
                    ORDER BY created_at DESC
                ''', (f'%{search_term}%',))
            elif search_type == 'product':
                cursor.execute('''
                    SELECT * FROM weighing_tickets 
                    WHERE product LIKE ? 
                    ORDER BY created_at DESC
                ''', (f'%{search_term}%',))
            else:
                # ค้นหาทุกฟิลด์
                cursor.execute('''
                    SELECT * FROM weighing_tickets 
                    WHERE vehicle_number LIKE ? 
                       OR driver_name LIKE ? 
                       OR product LIKE ? 
                       OR local_ticket_id LIKE ?
                    ORDER BY created_at DESC
                ''', (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))
            
            tickets = []
            for row in cursor.fetchall():
                tickets.append(dict(row))
            
            return tickets
            
        except Exception as e:
            print(f"Error searching tickets: {e}")
            return []
    
    def delete_ticket(self, local_ticket_id: str) -> bool:
        """
        ลบบัตรชั่ง
        
        Args:
            local_ticket_id: เลขที่บัตรชั่ง
            
        Returns:
            bool: True ถ้าสำเร็จ, False ถ้าล้มเหลว
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute('DELETE FROM weighing_tickets WHERE local_ticket_id = ?', (local_ticket_id,))
            self.conn.commit()
            
            print(f"✅ ลบบัตรชั่งสำเร็จ: {local_ticket_id}")
            return True
            
        except Exception as e:
            print(f"Error deleting ticket: {e}")
            return False
    
    def close_connection(self):
        """ปิดการเชื่อมต่อฐานข้อมูล"""
        try:
            if self.conn:
                self.conn.close()
        except Exception as e:
            print(f"Error closing connection: {e}")
