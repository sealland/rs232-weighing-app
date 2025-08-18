# crud.py

from sqlalchemy.orm import Session
from sqlalchemy import or_, func, Date
import models
from datetime import date


def get_open_tickets(db: Session, skip: int = 0, limit: int = 100):
    """
    ดึงข้อมูลบัตรชั่งที่
    1. (น้ำหนักชั่งออกเป็น NULL หรือ 0)
    AND
    2. (ยังไม่ถูกยกเลิก)
    """
    return db.query(models.WeightTicket).filter(
        or_(models.WeightTicket.WE_WEIGHTOUT == None, models.WeightTicket.WE_WEIGHTOUT == 0),
        or_(models.WeightTicket.WE_CANCEL == None, models.WeightTicket.WE_CANCEL == '')
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