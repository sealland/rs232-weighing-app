from sqlalchemy.orm import Session
from typing import List, Optional
from models import WeightTicket, WeightTicketItem
from pdf_generator import WeightTicketPDFGenerator
from fastapi import HTTPException
from io import BytesIO

class ReportService:
    def __init__(self):
        """Initialize Report Service with PDF Generator"""
        self.pdf_generator = WeightTicketPDFGenerator()
    
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
    
    def generate_separate_weighing_pdf(self, db: Session, ticket_id: str) -> BytesIO:
        """
        สร้างรายงานบัตรชั่งแบบชั่งแยก (A5)
        """
        try:
            # ดึงข้อมูลบัตรชั่ง
            ticket, _ = self.get_ticket_with_items(db, ticket_id)
            
            # สร้าง PDF
            pdf_buffer = self.pdf_generator.generate_separate_weighing_report(ticket)
            
            return pdf_buffer
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error generating PDF: {str(e)}")
    
    def generate_combined_weighing_pdf(self, db: Session, ticket_id: str) -> BytesIO:
        """
        สร้างรายงานบัตรชั่งแบบชั่งรวม (A4)
        """
        try:
            # ดึงข้อมูลบัตรชั่งพร้อมรายการสินค้า
            ticket, items = self.get_ticket_with_items(db, ticket_id)
            
            # ตรวจสอบว่ามีรายการสินค้าหรือไม่
            if not items:
                raise HTTPException(
                    status_code=400, 
                    detail="This ticket has no items. Use separate weighing report instead."
                )
            
            # สร้าง PDF
            pdf_buffer = self.pdf_generator.generate_combined_weighing_report(ticket, items)
            
            return pdf_buffer
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error generating PDF: {str(e)}")
    
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
