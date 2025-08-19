from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Date, PrimaryKeyConstraint
from sqlalchemy.orm import relationship 
from database import Base_scale
from database_pp import Base_pp


class WeightTicket(Base_scale):
    __tablename__ = 'TBL_WEIGHT'
    
    WE_ID = Column(String, primary_key=True, index=True)
    WE_TYPE = Column(String, nullable=False) # nullable=False เพราะห้ามเป็นค่าว่าง
    WE_DATE = Column(Date, nullable=False) # ใช้ Date Type และห้ามเป็นค่าว่าง
    WE_LICENSE = Column(String)
    WE_TIMEIN = Column(DateTime)
    WE_TIMEOUT = Column(DateTime, nullable=True)
    WE_WEIGHTIN = Column(Float)
    WE_WEIGHTOUT = Column(Float, nullable=True)
    WE_USER = Column(String, nullable=True)
    WE_CANCEL = Column(String, nullable=True)

    # --- เพิ่ม Field ใหม่ที่นี่ ---
    WE_DIREF = Column(String, nullable=True)
    WE_MAT_CD = Column(String, nullable=True)
    WE_MAT = Column(String, nullable=True)
    WE_QTY = Column(Float, nullable=True)
    WE_UOM = Column(String, nullable=True)
    WE_VENDOR_CD = Column(String, nullable=True)
    WE_VENDOR = Column(String, nullable=True)
    # -----------------------------
    WE_WEIGHTNET = Column(Float, nullable=True)

    items = relationship("WeightTicketItem", back_populates="ticket")
    # ------------------

    # --- เพิ่ม Class ใหม่ทั้งหมด ---
class WeightTicketItem(Base_scale):
    __tablename__ = 'TBL_WEIGHT_ITEM'

    # กำหนด Primary Key แบบ Composite (หลายคอลัมน์รวมกัน)
    WE_ID = Column(String, ForeignKey('TBL_WEIGHT.WE_ID'), primary_key=True)
    VBELN = Column(String, primary_key=True) # เลขที่เอกสาร
    POSNR = Column(String, primary_key=True) # รายการในเอกสาร
    
    WE_MAT_CD = Column(String)
    WE_MAT = Column(String)
    WE_QTY = Column(Float)
    WE_UOM = Column(String)
    WE_PARTNER_NAME = Column(String, nullable=True)


    # สร้างความสัมพันธ์ย้อนกลับ: บอกว่า WeightTicketItem "เป็นของ" WeightTicket หนึ่งใบ
    ticket = relationship("WeightTicket", back_populates="items")
# -----------------------------
class ShipmentPlan(Base_scale):
    __tablename__ = 'tbl_shipmentplan'

    # --- สำคัญมาก: ระบุ Schema ของตาราง ---
    __table_args__ = {'schema': 'dbo'}

    # กำหนดคอลัมน์ที่ต้องการใช้งาน
    VBELN = Column(String) # เลขที่เอกสาร (Delivery Note)
    POSNR = Column(String) # รายการในเอกสาร (Item Number)
    AR_NAME = Column(String, nullable=True) # ชื่อลูกค้า
    MATNR = Column(String, nullable=True) # รหัสสินค้า
    ARKTX = Column(String, nullable=True) # ชื่อสินค้า
    NTGEW = Column(Float, nullable=True)  # น้ำหนัก/จำนวน
    VRKME = Column(String, nullable=True) # หน่วยนับ

    # --- กำหนด Composite Primary Key ---
    # บอก SQLAlchemy ว่า Primary Key ของตารางนี้คือ VBELN และ POSNR รวมกัน
    __mapper_args__ = {
        'primary_key': [VBELN, POSNR]
    }
# ---------------------------------------------