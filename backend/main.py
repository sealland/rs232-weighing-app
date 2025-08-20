from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import date, timedelta

from fastapi.middleware.cors import CORSMiddleware

import crud, models, schemas
from database import SessionLocal_scale
from database_pp import SessionLocal_pp

#models.Base.metadata.create_all(bind=engine) # บรรทัดนี้อาจจะไม่จำเป็นถ้าตารางมีอยู่แล้ว

app = FastAPI()

origins = [
    "http://localhost:5173", # URL ของ Vue dev server
    # คุณอาจจะเพิ่ม URL อื่นๆ ในอนาคต เช่น "http://your-production-domain.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    # ระบุ Methods ทั้งหมดที่เราใช้ลงไปตรงๆ
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Dependency สำหรับการจัดการ Database Session
# --- Dependency สำหรับแต่ละ Database ---
def get_db_scale():
    db = SessionLocal_scale()
    try:
        yield db
    finally:
        db.close()

def get_db_pp():
    db = SessionLocal_pp()
    try:
        yield db
    finally:
        db.close()
# ------------------------------------

# ควรวางไว้ก่อน Endpoint ที่มี Path Parameter เพื่อความเป็นระเบียบ
@app.post("/api/tickets/", response_model=schemas.WeightTicket)
def create_new_ticket(ticket: schemas.WeightTicketCreate, db: Session = Depends(get_db_scale)):
    """
    API Endpoint สำหรับสร้างบัตรชั่งใหม่
    """
    return crud.create_ticket(db=db, ticket=ticket)


@app.get("/api/tickets/", response_model=List[schemas.WeightTicket])
def read_open_tickets(target_date: date | None = None, db: Session = Depends(get_db_scale)):
    """
    API Endpoint สำหรับดึงรายการบัตรชั่งที่ยังไม่เสร็จ
    สามารถรับ query parameter 'target_date' (YYYY-MM-DD)
    ถ้าไม่ระบุ จะใช้ 'วันนี้' เป็นค่าเริ่มต้น
    """
    if target_date is None:
        target_date = date.today() # ถ้าไม่ส่งวันที่มา ให้ใช้วันนี้
        
    # เรียกใช้ฟังก์ชันใหม่ที่แก้ไขแล้ว
    tickets = crud.get_open_tickets_by_date(db, target_date=target_date)
    return tickets

# --- API Endpoint ใหม่ ---
@app.get("/api/tickets/completed", response_model=List[schemas.WeightTicket])
def read_completed_tickets(target_date: date | None = None, db: Session = Depends(get_db_scale)):
    """
    API Endpoint สำหรับดึงรายการบัตรชั่งที่ชั่งเสร็จแล้ว
    สามารถรับ query parameter 'target_date' (YYYY-MM-DD)
    ถ้าไม่ระบุ จะใช้ 'วันนี้' เป็นค่าเริ่มต้น
    """
    if target_date is None:
        target_date = date.today() # ถ้าไม่ส่งวันที่มา ให้ใช้วันนี้
        
    tickets = crud.get_completed_tickets_by_date(db, target_date=target_date)
    return tickets

@app.patch("/api/tickets/{ticket_id}", response_model=schemas.WeightTicket)
def edit_ticket(ticket_id: str, ticket_data: schemas.WeightTicketUpdate, db: Session = Depends(get_db_scale)):
    """
    API Endpoint สำหรับแก้ไขข้อมูลบัตรชั่ง
    """
    updated_ticket = crud.update_ticket(db, ticket_id=ticket_id, ticket_data=ticket_data)
    if updated_ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return updated_ticket
# -----------------------------------------

# --- เพิ่ม Endpoint ใหม่สำหรับยกเลิกบัตรชั่ง ---
@app.delete("/api/tickets/{ticket_id}/cancel", response_model=schemas.WeightTicket)
def cancel_a_ticket(ticket_id: str, db: Session = Depends(get_db_scale)):
    """
    API Endpoint สำหรับยกเลิกบัตรชั่ง
    """
    cancelled_ticket = crud.cancel_ticket(db, ticket_id=ticket_id)
    if cancelled_ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return cancelled_ticket
# -----------------------------------------

# --- เพิ่ม Endpoint ใหม่สำหรับอัปเดต (ชั่งออก) ---
@app.patch("/api/tickets/{ticket_id}/weigh-out", response_model=schemas.WeightTicket)
def update_ticket_weigh_out(
    ticket_id: str, 
    weigh_out_data: schemas.WeightTicketUpdateWeighOut, 
    db: Session = Depends(get_db_scale)
):
    """
    API Endpoint สำหรับบันทึกน้ำหนักชั่งออก
    """
    updated_ticket = crud.update_weigh_out(db, ticket_id=ticket_id, weigh_out_data=weigh_out_data)
    if updated_ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return updated_ticket
# -----------------------------------------
# --- API Endpoint ใหม่สำหรับดึงข้อมูลใบเดียว ---
@app.get("/api/tickets/{ticket_id}", response_model=schemas.WeightTicketDetails)
def read_ticket_details(ticket_id: str, db: Session = Depends(get_db_scale)):
    """
    API Endpoint สำหรับดึงข้อมูลบัตรชั่งใบเดียวแบบละเอียด
    """
    db_ticket = crud.get_ticket_by_id(db, ticket_id=ticket_id)
    if db_ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return db_ticket

    # --- เพิ่ม Endpoint ใหม่สำหรับค้นหา Shipment Plan ---
@app.get("/api/shipment-plans/{plan_id}", response_model=List[schemas.ShipmentPlanItem])
def read_shipment_plan(plan_id: str, db: Session = Depends(get_db_pp)):
    plan_items = crud.get_shipment_plan_by_id(db, plan_id=plan_id)
    return plan_items
# -------------------------------------------------
# --- เพิ่ม Endpoint ใหม่สำหรับดึงคิวรถ ---
@app.get("/api/car-queue/", response_model=List[schemas.CarVisit])
def read_car_queue(db: Session = Depends(get_db_pp)):
    car_queue = crud.get_available_car_queue(db)
    return car_queue
# ---------------------------------------
# --- เพิ่ม Endpoint ใหม่สำหรับ "แทนที่" รายการสินค้า ---
@app.put("/api/tickets/{ticket_id}/items", response_model=schemas.WeightTicketDetails)
def replace_items_in_a_ticket(
    ticket_id: str,
    items: List[schemas.WeightTicketItemCreate], # <-- รับ List ของ Items ใหม่จาก Body
    db: Session = Depends(get_db_scale)
):
    """
    API Endpoint สำหรับแทนที่รายการสินค้าทั้งหมดในบัตรชั่ง
    (ใช้สำหรับโหมดแก้ไขชั่งรวม)
    """
    updated_ticket = crud.replace_ticket_items(db, ticket_id=ticket_id, items=items)
    if updated_ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return updated_ticket
# ------------------------------------------------

# --- เพิ่ม Endpoint ใหม่สำหรับเพิ่มรายการสินค้า ---
@app.post("/api/tickets/{ticket_id}/items", response_model=schemas.WeightTicketDetails)
def add_items_to_a_ticket(
    ticket_id: str,
    items: List[schemas.WeightTicketItemCreate], # <-- รับ List ของ Items จาก Body
    db: Session = Depends(get_db_scale)
):
    """
    API Endpoint สำหรับเพิ่มรายการสินค้า (จาก Shipment Plan) เข้าไปในบัตรชั่ง
    """
    updated_ticket = crud.add_items_to_ticket(db, ticket_id=ticket_id, items=items)
    if updated_ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return updated_ticket
# ----------------------------------------------
