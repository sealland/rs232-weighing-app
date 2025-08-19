# database_pp.py

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

# --- ตั้งค่าการเชื่อมต่อ PP ---
SERVER_PP = "192.168.201.115"
DATABASE_PP = "PP"
USERNAME_PP = "sa"
PASSWORD_PP = "gs]HdmiyrpN2523"
DRIVER = "ODBC Driver 17 for SQL Server"

SQLALCHEMY_DATABASE_URL_PP = (
    f"mssql+pyodbc://{USERNAME_PP}:{PASSWORD_PP}@"
    f"{SERVER_PP}/{DATABASE_PP}?driver={DRIVER}"
)

# เพิ่ม options สำหรับ Connection Pool
engine_pp = create_engine(
    SQLALCHEMY_DATABASE_URL_PP,
    pool_pre_ping=True,
    pool_recycle=3600
)

SessionLocal_pp = sessionmaker(autocommit=False, autoflush=False, bind=engine_pp)

Base_pp = declarative_base()