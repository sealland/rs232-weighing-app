# agent_websocket.py
import asyncio
import websockets
import json
import time
from collections import defaultdict

# Global variables
CONNECTED_CLIENTS = set()
CONNECTED_SCALE_CLIENTS = {}  # เก็บข้อมูลจาก scale clients
WEIGHT_DATA = defaultdict(dict)  # เก็บข้อมูลน้ำหนักจากแต่ละ client

async def register_client(websocket, path):
    """รับการเชื่อมต่อจาก client"""
    CONNECTED_CLIENTS.add(websocket)
    print(f"Client connected: {websocket.remote_address}. Total clients: {len(CONNECTED_CLIENTS)}")
    
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                
                # ตรวจสอบว่าเป็นข้อมูลจาก scale client หรือไม่
                if "client_id" in data and "weight" in data:
                    # ข้อมูลจาก scale client
                    client_id = data["client_id"]
                    weight = data["weight"]
                    timestamp = data.get("timestamp", time.time())
                    branch = data.get("branch", "Unknown")
                    branch_prefix = data.get("branch_prefix", "Z1")
                    
                    WEIGHT_DATA[client_id] = {
                        "weight": weight,
                        "timestamp": timestamp,
                        "last_update": time.time(),
                        "branch": branch,
                        "branch_prefix": branch_prefix
                    }
                    
                    print(f"Received weight from {client_id} ({branch}): {weight} (Prefix: {branch_prefix})")
                    
                    # Broadcast ข้อมูลไปยัง web clients
                    await broadcast_weight_data()
                    
                else:
                    # ข้อมูลจาก web client (อาจเป็นคำสั่งหรือข้อมูลอื่นๆ)
                    print(f"Received from web client: {data}")
                    
            except json.JSONDecodeError:
                print(f"Invalid JSON received: {message}")
                
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        CONNECTED_CLIENTS.remove(websocket)
        print(f"Client disconnected: {websocket.remote_address}. Total clients: {len(CONNECTED_CLIENTS)}")

async def broadcast_weight_data():
    """ส่งข้อมูลน้ำหนักไปยัง web clients"""
    if CONNECTED_CLIENTS:
        # สร้างข้อมูลที่จะส่งไปยัง web clients
        # ใช้ข้อมูลน้ำหนักล่าสุดจาก scale แรกที่เชื่อมต่อ
        latest_weight = 0
        if WEIGHT_DATA:
            # ใช้ข้อมูลจาก scale แรก (หรือ scale ที่อัปเดตล่าสุด)
            first_scale_data = next(iter(WEIGHT_DATA.values()))
            latest_weight = first_scale_data.get("weight", 0)
        
        weight_summary = {
            "weight": latest_weight,  # เพิ่ม property 'weight' ที่ frontend คาดหวัง
            "timestamp": time.time(),
            "scales": dict(WEIGHT_DATA)
        }
        
        message = json.dumps(weight_summary)
        
        # ส่งข้อมูลให้ web clients ทุกคน
        await asyncio.gather(
            *[client.send(message) for client in CONNECTED_CLIENTS],
            return_exceptions=True
        )

async def cleanup_old_data():
    """ลบข้อมูลเก่าที่ไม่ได้อัปเดตแล้ว"""
    current_time = time.time()
    timeout = 30  # ลบข้อมูลที่เก่ากว่า 30 วินาที
    
    to_remove = []
    for client_id, data in WEIGHT_DATA.items():
        if current_time - data.get("last_update", 0) > timeout:
            to_remove.append(client_id)
    
    for client_id in to_remove:
        del WEIGHT_DATA[client_id]
        print(f"Removed stale data from {client_id}")

async def main():
    """ฟังก์ชันหลัก"""
    print("Starting WebSocket Server for RS232 Scale System")
    print("Server will accept connections from scale clients and web clients")
    
    # เริ่ม WebSocket server
    async with websockets.serve(register_client, "0.0.0.0", 8765):
        print("WebSocket Server started at ws://0.0.0.0:8765")
        print("Waiting for scale clients and web clients to connect...")
        
        # Loop หลักสำหรับการทำงาน
        while True:
            await cleanup_old_data()
            await asyncio.sleep(10)  # ตรวจสอบทุก 10 วินาที

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Server stopped.")