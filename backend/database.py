from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# --- ตั้งค่าการเชื่อมต่อ SQL Server ---
# **สำคัญมาก:** แก้ไขค่าด้านล่างให้ตรงกับข้อมูลของคุณ
SERVER = "192.168.100.29"  # เช่น "192.168.1.100" หรือ "MY-SERVER-NAME\SQLEXPRESS"
DATABASE = "ZUBBSCALE"
USERNAME = "sa"
PASSWORD = "sipco77"
# ตรวจสอบให้แน่ใจว่าคุณได้ติดตั้ง Driver ที่จำเป็นแล้ว (เช่น ODBC Driver 17 for SQL Server)
DRIVER = "ODBC Driver 17 for SQL Server" 

SQLALCHEMY_DATABASE_URL = f"mssql+pyodbc://{USERNAME}:{PASSWORD}@{SERVER}/{DATABASE}?driver={DRIVER}"

engine = create_engine(SQLALCHEMY_DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()