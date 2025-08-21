from sqlalchemy.orm import Session
from typing import List, Optional
from models import WeightTicket, WeightTicketItem
from fastapi import HTTPException

class ReportService:
    def __init__(self):
        """Initialize Report Service with TCPDF URLs"""
        self.separate_report_url = "https://reports.zubbsteel.com/zticket_a5.php"
        self.combined_report_url = "https://reports.zubbsteel.com/zticket_a4.php"
    
    def get_ticket_with_items(self, db: Session, ticket_id: str) -> tuple[WeightTicket, List[WeightTicketItem]]:
        """
        ดึงข้อมูลบัตรชั่งพร้อมรายการสินค้า
        """
        # ดึงข้อมูลบัตรชั่ง
        ticket = db.query(WeightTicket).filter(WeightTicket.WE_ID == ticket_id).first()
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")
        
        # ดึงรายการสินค้า
        items = db.query(WeightTicketItem).filter(WeightTicketItem.WE_ID == ticket_id).all()
        
        return ticket, items
    
    def get_report_urls(self, db: Session, ticket_id: str) -> dict:
        """
        สร้าง URL สำหรับรายงานทั้งสองประเภท
        """
        try:
            ticket, items = self.get_ticket_with_items(db, ticket_id)
            
            # สร้าง URL สำหรับรายงานแต่ละประเภท
            separate_url = f"{self.separate_report_url}?id={ticket_id}"
            combined_url = f"{self.combined_report_url}?id={ticket_id}"
            
            # ตรวจสอบประเภทรายงาน
            report_type = "combined" if items else "separate"
            
            return {
                "ticket_id": ticket_id,
                "report_type": report_type,
                "separate_url": separate_url,
                "combined_url": combined_url,
                "recommended_url": combined_url if report_type == "combined" else separate_url
            }
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error generating report URLs: {str(e)}")
    
    def get_report_type(self, db: Session, ticket_id: str) -> str:
        """
        ตรวจสอบประเภทของรายงาน (ชั่งแยกหรือชั่งรวม)
        """
        try:
            ticket, items = self.get_ticket_with_items(db, ticket_id)
            
            # ถ้ามีรายการสินค้า = ชั่งรวม
            if items:
                return "combined"
            else:
                return "separate"
                
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error determining report type: {str(e)}")
