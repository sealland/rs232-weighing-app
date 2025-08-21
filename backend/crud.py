from sqlalchemy.orm import Session
from sqlalchemy import or_, func, Date, cast, Integer, String
from datetime import date, datetime
import random
from typing import List # <--- **ตรวจสอบให้แน่ใจว่าบรรทัดนี้มีอยู่**
import models
import schemas

def get_open_tickets_by_date(db: Session, target_date: date, skip: int = 0, limit: int = 100):
    """
    ดึงข้อมูลบัตรชั่งที่ยังไม่เสร็จ (กำลังดำเนินการ)
    ตามวันที่ที่ระบุ
    """
    return db.query(models.WeightTicket).filter(
        # เงื่อนไขเดิม: ยังไม่ชั่งออก
        or_(models.WeightTicket.WE_WEIGHTOUT == None, models.WeightTicket.WE_WEIGHTOUT == 0),
        
        # เงื่อนไขเดิม: ยังไม่ยกเลิก
        or_(models.WeightTicket.WE_CANCEL == None, models.WeightTicket.WE_CANCEL == ''),
        
        # เปลี่ยนจากการใช้ date.today() มาเป็น target_date ที่รับเข้ามา
        models.WeightTicket.WE_DATE == target_date

    ).order_by(models.WeightTicket.WE_TIMEIN.desc()).offset(skip).limit(limit).all()

def get_completed_tickets_by_date(db: Session, target_date: date, skip: int = 0, limit: int = 100):
    """
    ดึงข้อมูลบัตรชั่งที่เสร็จสมบูรณ์แล้ว (มีน้ำหนักชั่งออก)
    ตามวันที่ที่ระบุ (เปรียบเทียบเฉพาะส่วนวันที่ของ WE_TIMEIN)
    """
    return db.query(models.WeightTicket).filter(
        models.WeightTicket.WE_WEIGHTOUT != None,
        models.WeightTicket.WE_WEIGHTOUT > 0,
        
        # V V V V V V V V V V V V V V V V V V V V V V V V V V V V V V
        # จุดที่ 2: แก้ไขจาก models.Date เป็น "Date" เฉยๆ
        func.cast(models.WeightTicket.WE_TIMEIN, Date) == target_date
        # ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^

    ).order_by(models.WeightTicket.WE_TIMEOUT.desc()).offset(skip).limit(limit).all()

def get_ticket_by_id(db: Session, ticket_id: str):
    """
    ดึงข้อมูลบัตรชั่งใบเดียวแบบละเอียด (พร้อมรายการสินค้า) ตาม WE_ID
    """
    return db.query(models.WeightTicket).filter(models.WeightTicket.WE_ID == ticket_id).first()

def create_ticket(db: Session, ticket: schemas.WeightTicketCreate):
    """
    สร้างบัตรชั่งใหม่ในฐานข้อมูล และอัปเดตบัตรแม่หากเป็นการชั่งต่อเนื่อง
    """
    # 1. สร้าง WE_ID (Logic เดิมของคุณทั้งหมด)
    prefix = "Z1"
    today = datetime.now()
    buddhist_year_last_digit = str(today.year + 543)[-1] 
    date_format = f"{buddhist_year_last_digit}{today.strftime('%m%d')}"
    id_prefix_for_today = f"{prefix}{date_format}"
    
    last_three_digits_as_int = cast(func.right(models.WeightTicket.WE_ID, 3), Integer)
    last_running_number = db.query(func.max(last_three_digits_as_int)).filter(
        models.WeightTicket.WE_ID.like(f"{id_prefix_for_today}%")
    ).scalar()

    if last_running_number is None:
        new_running_number = 1
    else:
        new_running_number = last_running_number + 1
        
    new_ticket_id = f"{id_prefix_for_today}{str(new_running_number).zfill(3)}"
    
    # 2. สร้างบัตรหลัก (TBL_WEIGHT)
    # *** เพิ่ม WE_PARENT และ WE_SEQ เข้าไปใน object ที่จะสร้าง ***
    db_ticket = models.WeightTicket(
        WE_ID=new_ticket_id,
        WE_LICENSE=ticket.WE_LICENSE,
        WE_WEIGHTIN=ticket.WE_WEIGHTIN,
        WE_TIMEIN=datetime.now(),
        WE_DATE=datetime.now().date(),
        WE_TYPE='I',
        WE_VENDOR_CD=ticket.WE_VENDOR_CD,
        WE_VENDOR=ticket.WE_VENDOR,
        WE_DIREF=ticket.WE_DIREF,
        WE_MAT_CD=ticket.WE_MAT_CD,
        WE_MAT=ticket.WE_MAT,
        # --- เพิ่มการบันทึกเลขคิว ---
        WE_SEQ=ticket.WE_SEQ  # บันทึกเลขคิวจากข้อมูลที่ส่งมา
    )
    db.add(db_ticket)
    
    # 3. สร้างรายการ "ชั่งรวม" (items) (Logic เดิม)
    if ticket.items:
        new_db_items = []
        for item in ticket.items:
            db_item = models.WeightTicketItem(
                WE_ID=new_ticket_id,
                VBELN=item.VBELN,
                POSNR=item.POSNR,
                WE_MAT_CD=item.WE_MAT_CD,
                WE_MAT=item.WE_MAT,
                WE_QTY=item.WE_QTY,
                WE_UOM=item.WE_UOM,
            )
            new_db_items.append(db_item)
        db.add_all(new_db_items)

    # 4. Commit การสร้างบัตรใหม่และรายการสินค้า
    db.commit()
    db.refresh(db_ticket)
    
    # --- จุดสำคัญ: อัปเดตบัตรแม่เมื่อเป็นการชั่งต่อเนื่อง ---
    if ticket.parent_id:
        try:
            # ค้นหาบัตรแม่จาก parent_id
            parent_ticket = db.query(models.WeightTicket).filter(
                models.WeightTicket.WE_ID == ticket.parent_id
            ).first()

            if parent_ticket:
                # อัปเดต field WE_CONT ของบัตรแม่ ด้วย ID ของบัตรใหม่ (ชั่งต่อเนื่อง)
                parent_ticket.WE_CONT = new_ticket_id
                db.commit()
                db.refresh(parent_ticket)
                print(f"✅ Successfully updated parent ticket {ticket.parent_id} with child ID {new_ticket_id}")
                print(f"   - Parent WE_CONT field updated to: {new_ticket_id}")
            else:
                print(f"⚠️  Warning: Parent ticket with ID {ticket.parent_id} not found.")
                print(f"   - Cannot update WE_CONT field for parent ticket")

        except Exception as e:
            print(f"❌ Error updating parent ticket: {e}")
            # ไม่ rollback เพราะบัตรใหม่ถูกสร้างสำเร็จแล้ว
            # เราไม่ต้องการให้การสร้างบัตรใหม่ล้มเหลวเพราะการอัปเดตบัตรแม่มีปัญหา

    # 6. คืนค่าบัตรที่สร้างใหม่
    return db_ticket

# --- เพิ่มฟังก์ชันใหม่สำหรับอัปเดตการชั่งออก ---
def update_weigh_out(db: Session, ticket_id: str, weigh_out_data: schemas.WeightTicketUpdateWeighOut):
    """
    อัปเดตข้อมูลการชั่งออกสำหรับบัตรชั่งที่ระบุ
    """
    # 1. ค้นหาบัตรชั่งที่ต้องการอัปเดต
    db_ticket = db.query(models.WeightTicket).filter(models.WeightTicket.WE_ID == ticket_id).first()

    # ถ้าไม่เจอบัตร ให้ return None
    if not db_ticket:
        return None

    # 2. นำข้อมูลใหม่มาใส่ใน object
    weight_in = db_ticket.WE_WEIGHTIN
    weight_out = weigh_out_data.WE_WEIGHTOUT
    
    db_ticket.WE_WEIGHTOUT = weight_out
    db_ticket.WE_TIMEOUT = datetime.now()
    
    # 3. คำนวณน้ำหนักสุทธิและกำหนด WE_TYPE ตาม Logic
    net_weight = abs(weight_in - weight_out)
    db_ticket.WE_WEIGHTNET = net_weight
    
    # Logic: ถ้า น้ำหนักออก > น้ำหนักเข้า, WE_TYPE = 'O' (Outgoing)
    # มิฉะนั้น WE_TYPE = 'I' (Incoming)
    if weight_out > weight_in:
        db_ticket.WE_TYPE = 'O'
    else:
        db_ticket.WE_TYPE = 'I'
        
    # 4. บันทึกการเปลี่ยนแปลงลงฐานข้อมูล
    db.commit()
    db.refresh(db_ticket)
    
    return db_ticket
# ---------------------------------------------

# --- เพิ่มฟังก์ชันใหม่สำหรับยกเลิกบัตรชั่ง ---
def cancel_ticket(db: Session, ticket_id: str):
    """
    ค้นหาบัตรชั่งตาม ID และอัปเดตสถานะ WE_CANCEL เป็น 'X'
    """
    # 1. ค้นหาบัตรชั่งที่ต้องการยกเลิก
    db_ticket = db.query(models.WeightTicket).filter(models.WeightTicket.WE_ID == ticket_id).first()

    # ถ้าไม่เจอบัตร ให้ return None
    if not db_ticket:
        return None
        
    # 2. อัปเดต field ที่เกี่ยวข้อง
    db_ticket.WE_CANCEL = 'X'
    # หมายเหตุ: ในอนาคตเราอาจจะเพิ่มการบันทึกเหตุผลที่นี่
    # db_ticket.WE_REASON = reason 
    
    # 3. บันทึกการเปลี่ยนแปลงลงฐานข้อมูล
    db.commit()
    db.refresh(db_ticket)
    
    return db_ticket
# ---------------------------------------------

def update_ticket(db: Session, ticket_id: str, ticket_data: schemas.WeightTicketUpdate):
    """
    แก้ไขข้อมูลของบัตรชั่งตาม ID
    """
    # 1. ค้นหาบัตรชั่ง
    db_ticket = db.query(models.WeightTicket).filter(models.WeightTicket.WE_ID == ticket_id).first()

    if not db_ticket:
        return None
    
    # 2. อัปเดตข้อมูลจาก object ที่ส่งเข้ามา
    # เราจะอัปเดตเฉพาะ field ที่มีการส่งค่ามา (ไม่เป็น None)
    update_data = ticket_data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_ticket, key, value)

    # 3. บันทึกการเปลี่ยนแปลง
    db.commit()
    db.refresh(db_ticket)
    
    return db_ticket
# ---------------------------------------------

# --- เพิ่มฟังก์ชันใหม่สำหรับค้นหา Shipment Plan ---
def get_shipment_plan_by_id(db: Session, plan_id: str):
    """
    ค้นหารายการทั้งหมดใน Shipment Plan ตาม VBELN (plan_id)
    """
    # ค้นหาทุกรายการ (ทุก POSNR) ที่มี VBELN ตรงกับที่ระบุ
    return db.query(models.ShipmentPlan).filter(models.ShipmentPlan.VBELN == plan_id).all()
# ---------------------------------------------

def add_items_to_ticket(db: Session, ticket_id: str, items: List[schemas.WeightTicketItemCreate]):
    """
    เพิ่มรายการสินค้าหลายรายการเข้าไปในบัตรชั่งที่ระบุ
    """
    # 1. ค้นหาบัตรชั่งหลักก่อน เพื่อให้แน่ใจว่ามีอยู่จริง
    db_ticket = db.query(models.WeightTicket).filter(models.WeightTicket.WE_ID == ticket_id).first()
    if not db_ticket:
        return None # คืนค่า None ถ้าไม่เจอบัตรหลัก

    # 2. วนลูปสร้าง object ของ SQLAlchemy Model สำหรับแต่ละ item ที่ส่งมา
    new_db_items = []
    for item in items:
        db_item = models.WeightTicketItem(
            WE_ID=ticket_id, # <-- ใช้ ticket_id จาก URL
            VBELN=item.VBELN,
            POSNR=item.POSNR,
            WE_MAT_CD=item.WE_MAT_CD,
            WE_MAT=item.WE_MAT,
            WE_QTY=item.WE_QTY,
            WE_UOM=item.WE_UOM,
        )
        new_db_items.append(db_item)
        
    # 3. บันทึกรายการใหม่ทั้งหมดลงฐานข้อมูลในครั้งเดียว
    db.add_all(new_db_items)
    db.commit()
    
    # 4. คืนค่าบัตรชั่งที่อัปเดตแล้ว (เพื่อให้เห็นรายการใหม่)
    db.refresh(db_ticket)
    return db_ticket
# ------------------------------------------------
# --- เพิ่มฟังก์ชันใหม่สำหรับดึงคิวรถ ---
def get_available_car_queue(db: Session):
    """
    ดึงข้อมูลคิวรถของวันนี้ ที่ Ship_point = 'P8' และยังไม่มีการสร้างบัตรชั่ง (TICKET IS NULL)
    """
    today = date.today()
    return db.query(models.CarVisit).filter(
        models.CarVisit.WADAT_IST == today,
        models.CarVisit.Ship_point == 'P8'
    ).order_by(models.CarVisit.SEQ).all()
# ------------------------------------

# --- เพิ่มฟังก์ชันใหม่สำหรับ "แทนที่" รายการสินค้า ---
def replace_ticket_items(db: Session, ticket_id: str, items: List[schemas.WeightTicketItemCreate]):
    """
    ลบรายการสินค้าเก่าทั้งหมดของบัตรชั่ง แล้วเพิ่มรายการใหม่เข้าไปแทน
    """
    # 1. ค้นหาบัตรชั่งหลักเพื่อให้แน่ใจว่ามีอยู่จริง
    db_ticket = db.query(models.WeightTicket).filter(models.WeightTicket.WE_ID == ticket_id).first()
    if not db_ticket:
        return None

    # 2. ลบรายการสินค้าเก่าทั้งหมดที่ผูกกับ ticket_id นี้
    # synchronize_session=False เป็น option ที่แนะนำเมื่อมีการลบหลายแถว
    db.query(models.WeightTicketItem).filter(models.WeightTicketItem.WE_ID == ticket_id).delete(synchronize_session=False)

    # 3. สร้าง object ของรายการใหม่ (เหมือนใน create_ticket)
    new_db_items = []
    for item in items:
        db_item = models.WeightTicketItem(
            WE_ID=ticket_id,
            VBELN=item.VBELN,
            POSNR=item.POSNR,
            WE_MAT_CD=item.WE_MAT_CD,
            WE_MAT=item.WE_MAT,
            WE_QTY=item.WE_QTY,
            WE_UOM=item.WE_UOM,
        )
        new_db_items.append(db_item)
        
    # 4. เพิ่มรายการใหม่ทั้งหมดลง session
    if new_db_items:
        db.add_all(new_db_items)

    # 5. Commit การเปลี่ยนแปลงทั้งหมด (ทั้ง DELETE และ INSERT)
    db.commit()
    
    # 6. คืนค่าบัตรชั่งที่อัปเดตแล้ว
    # เราต้อง refresh object เดิมเพื่อให้ SQLAlchemy ไปดึงข้อมูล .items ใหม่จากฐานข้อมูล
    db.refresh(db_ticket)
    return db_ticket
# --------------------------------------------------