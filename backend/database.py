# database.py

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

# --- ตั้งค่าการเชื่อมต่อ ZUBBSCALE_HQ ---
SERVER = "192.168.100.29" # IP ของ ZUBBSCALE_HQ
DATABASE = "ZUBBSCALE"
USERNAME = "sa"
PASSWORD = "sipco77"
DRIVER = "ODBC Driver 17 for SQL Server"

SQLALCHEMY_DATABASE_URL = (
    f"mssql+pyodbc://{USERNAME}:{PASSWORD}@"
    f"{SERVER}/{DATABASE}?driver={DRIVER}"
)

# เพิ่ม options สำหรับ Connection Pool
engine_scale = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True, # ตรวจสอบ connection ก่อนใช้งาน
    pool_recycle=3600   # คืน connection ที่ไม่ได้ใช้เกิน 1 ชม.
)

SessionLocal_scale = sessionmaker(autocommit=False, autoflush=False, bind=engine_scale)

Base_scale = declarative_base()