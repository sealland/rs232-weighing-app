from pydantic import BaseModel
from datetime import datetime, date
from typing import Optional, List

# Schema พื้นฐานที่มีข้อมูลร่วมกัน
class WeightTicketBase(BaseModel):
    WE_LICENSE: str
    WE_WEIGHTIN: float

class WeightTicketCreate(BaseModel):
    WE_LICENSE: str
    WE_WEIGHTIN: float

class WeightTicketUpdateWeighOut(BaseModel):
    WE_WEIGHTOUT: float

# Schema สำหรับการสร้างข้อมูล (อาจจะไม่ต้องใช้ตอนนี้)
class WeightTicketCreate(WeightTicketBase):
    pass

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
    WE_WEIGHTNET: Optional[float]
    # -----------------------------

    class Config:
        from_attributes = True

class WeightTicketItem(BaseModel):
    WE_MAT_CD: str
    WE_MAT: str
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