from pydantic import BaseModel
from datetime import datetime, date
from typing import Optional, List

# Schema พื้นฐานที่มีข้อมูลร่วมกัน
class WeightTicketBase(BaseModel):
    WE_LICENSE: str
    WE_WEIGHTIN: float

# --- เพิ่ม Schema ใหม่สำหรับ 1 รายการที่จะสร้างใน TBL_WEIGHT_ITEM ---
class WeightTicketItemCreate(BaseModel):
    VBELN: str
    POSNR: str
    WE_MAT_CD: Optional[str] = None
    WE_MAT: Optional[str] = None
    WE_QTY: Optional[float] = None
    WE_UOM: Optional[str] = None

# -------------------------------------------------------------

class WeightTicketCreate(BaseModel):
    WE_LICENSE: str
    WE_WEIGHTIN: float
    WE_VENDOR: Optional[str] = None
    WE_VENDOR_CD: Optional[str] = None
    # --- เพิ่ม WE_SEQ สำหรับเก็บเลขคิว ---
    WE_SEQ: Optional[str] = None  # เลขคิวจากตาราง CarVisit
    
    # --- ข้อมูลสำหรับ "ชั่งแยก" ---
    WE_DIREF: Optional[str] = None
    WE_MAT_CD: Optional[str] = None
    WE_MAT: Optional[str] = None
    WE_QTY: Optional[float] = None  # เปลี่ยนจาก int เป็น float
    WE_UOM: Optional[str] = None
    # --- ข้อมูลสำหรับการชั่งต่อเนื่อง ---
    parent_id: Optional[str] = None  # ID ของบัตรชั่งหลัก (สำหรับการอัปเดต WE_CONT)
    # --- ข้อมูลสำหรับ "ชั่งรวม" ---
    # รับ List ของ WeightTicketItemCreate เข้ามาได้
    items: Optional[List[WeightTicketItemCreate]] = None
    
class WeightTicketUpdateWeighOut(BaseModel):
    WE_WEIGHTOUT: float

class WeightTicketUpdate(BaseModel):
    WE_LICENSE: Optional[str] = None
    WE_VENDOR_CD: Optional[str] = None
    WE_VENDOR: Optional[str] = None
    WE_DIREF: Optional[str] = None
    WE_MAT_CD: Optional[str] = None
    WE_MAT: Optional[str] = None
    WE_QTY: Optional[float] = None # <-- เพิ่มบรรทัดนี้

# Schema สำหรับการอ่านข้อมูลจากฐานข้อมูลมาแสดงผล
class WeightTicket(WeightTicketBase):
    WE_ID: str
    WE_DATE: Optional[date] = None
    WE_TIMEIN: datetime
    WE_TIMEOUT: Optional[datetime] = None
    WE_WEIGHTOUT: Optional[float] = None
    WE_USER: Optional[str] = None
    
    # --- เพิ่ม Field ใหม่ที่นี่ ---
    WE_DIREF: Optional[str] = None
    WE_MAT_CD: Optional[str] = None
    WE_MAT: Optional[str] = None
    WE_QTY: Optional[float] = None
    WE_UOM: Optional[str] = None
    WE_VENDOR_CD: Optional[str] = None
    WE_VENDOR: Optional[str] = None
    # --- เพิ่ม WE_SEQ สำหรับการอ่านข้อมูล ---
    WE_SEQ: Optional[str] = None  # เลขคิวจากตาราง CarVisit
    # --- เพิ่ม WE_CONT สำหรับการอ่านข้อมูล ---
    WE_CONT: Optional[str] = None  # ID ของบัตรชั่งต่อเนื่อง
    WE_WEIGHTNET: Optional[float]
    # -----------------------------

    class Config:
        from_attributes = True

class WeightTicketItem(BaseModel):
    WE_MAT_CD: Optional[str] = None
    WE_MAT: Optional[str] = None
    WE_QTY: Optional[float] = None
    WE_UOM: Optional[str] = None
    VBELN: str
    POSNR: str
    # WE_PARTNER_NAME: Optional[str] = None # <--- เอา field นี้ออก

    class Config:
        from_attributes = True

# Schema สำหรับ Response ตอนดึงข้อมูลแบบละเอียด
# จะมีข้อมูลเหมือน WeightTicket ปกติ แต่เพิ่ม "items" ที่เป็น List ของ WeightTicketItem เข้ามา
class WeightTicketDetails(WeightTicket):
    items: List[WeightTicketItem] = []

# -----------------------------

# --- เพิ่ม Schema ใหม่สำหรับ 1 รายการใน Shipment Plan ---
class ShipmentPlanItem(BaseModel):
    VBELN: str
    POSNR: str
    AR_NAME: Optional[str] = None
    MATNR: Optional[str] = None
    ARKTX: Optional[str] = None
    NTGEW: Optional[float] = None
    VRKME: Optional[str] = None
    LFIMG: Optional[float] = None

    class Config:
        from_attributes = True
# ----------------------------------------------------


# --- เพิ่ม Schema ใหม่สำหรับ 1 รายการในคิวรถ ---
class CarVisit(BaseModel):
    WADAT_IST: date
    SEQ: str
    CARLICENSE: Optional[str] = None  # เปลี่ยนเป็น Optional
    AR_NAME: Optional[str] = None
    KUNNR: Optional[str] = None
    Ship_point: Optional[str] = None
    TICKET: Optional[str] = None

    class Config:
        from_attributes = True
# -------------------------------------------