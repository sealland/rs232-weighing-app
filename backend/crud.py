# crud.py

from sqlalchemy.orm import Session
from sqlalchemy import or_, func, Date, cast, Integer, String
from datetime import date, datetime
import random
import models, schemas 
from datetime import date


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
    สร้างบัตรชั่งใหม่ในฐานข้อมูล โดยมี WE_ID ตาม format Z1-YYMMDD-XXX (Running)
    """
    # --- ส่วนการสร้าง WE_ID ---
    
    # 1. กำหนด Prefix และ format วันที่ปัจจุบัน
    prefix = "Z1" # ในอนาคตจะดึงมาจาก setting
    today = datetime.now()
    
    # แปลงเป็นปี พ.ศ. แล้วเอาแค่เลขตัวสุดท้าย
    buddhist_year_last_digit = str(today.year + 543)[-1] 
    
    date_format = f"{buddhist_year_last_digit}{today.strftime('%m%d')}" # Ex: 80818
    id_prefix_for_today = f"{prefix}{date_format}" # Ex: Z180818
    
    # 2. ค้นหา Running Number ล่าสุดของวันนี้จากฐานข้อมูล
    # เราจะหา WE_ID ที่ขึ้นต้นด้วย id_prefix_for_today (เช่น 'Z180818%')
    # แล้วแปลง 3 ตัวท้ายให้เป็นตัวเลข เพื่อหาค่าที่มากที่สุด
    
    # สร้าง subquery เพื่อแปลง 3 ตัวท้ายเป็น Integer
    # RIGHT(WE_ID, 3) คือการดึง 3 ตัวอักษรสุดท้าย
    # CAST(...) คือการแปลงชนิดข้อมูล
    last_three_digits_as_int = cast(func.right(models.WeightTicket.WE_ID, 3), Integer)

    # ค้นหาค่า running ล่าสุด
    last_running_number = db.query(func.max(last_three_digits_as_int)).filter(
        models.WeightTicket.WE_ID.like(f"{id_prefix_for_today}%")
    ).scalar()

    # 3. สร้าง Running Number ใหม่
    if last_running_number is None:
        # ถ้ายังไม่มีข้อมูลของวันนี้เลย ให้เริ่มที่ 1
        new_running_number = 1
    else:
        # ถ้ามีแล้ว ให้บวก 1
        new_running_number = last_running_number + 1
        
    # 4. ประกอบร่างเป็น WE_ID ตัวสุดท้าย (10 หลัก)
    # .zfill(3) คือการเติม 0 ข้างหน้าให้ครบ 3 หลัก เช่น 1 -> "001", 12 -> "012"
    new_ticket_id = f"{id_prefix_for_today}{str(new_running_number).zfill(3)}"

    # -----------------------------

    # สร้าง object ของ SQLAlchemy Model
    db_ticket = models.WeightTicket(
        WE_ID=new_ticket_id,
        WE_LICENSE=ticket.WE_LICENSE,
        WE_WEIGHTIN=ticket.WE_WEIGHTIN,
        WE_TIMEIN=datetime.now(),
        WE_TYPE='I',
         WE_DATE=datetime.now().date(),
    )
    
    # บันทึกลงฐานข้อมูล
    db.add(db_ticket)
    db.commit()
    db.refresh(db_ticket)
    
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