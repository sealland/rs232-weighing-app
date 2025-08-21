from reportlab.lib.pagesizes import A4, A5
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from io import BytesIO
import os
from datetime import datetime
from typing import List, Optional
from models import WeightTicket, WeightTicketItem

class WeightTicketPDFGenerator:
    def __init__(self):
        """Initialize PDF Generator with Thai font support"""
        self.setup_thai_font()
        self.styles = getSampleStyleSheet()
        self.setup_custom_styles()
    
    def setup_thai_font(self):
        """Setup Thai font for PDF generation"""
        try:
            # ใช้ font มาตรฐานที่รองรับภาษาไทย
            pdfmetrics.registerFont(TTFont('THSarabun', 'THSarabun.ttf'))
            self.thai_font = 'THSarabun'
        except:
            # ถ้าไม่มี font ไทย ให้ใช้ font มาตรฐาน
            self.thai_font = 'Helvetica'
    
    def setup_custom_styles(self):
        """Setup custom paragraph styles"""
        # สไตล์สำหรับหัวข้อหลัก
        self.styles.add(ParagraphStyle(
            name='ThaiTitle',
            parent=self.styles['Heading1'],
            fontName=self.thai_font,
            fontSize=18,
            alignment=TA_CENTER,
            spaceAfter=12
        ))
        
        # สไตล์สำหรับหัวข้อรอง
        self.styles.add(ParagraphStyle(
            name='ThaiHeading',
            parent=self.styles['Heading2'],
            fontName=self.thai_font,
            fontSize=14,
            alignment=TA_LEFT,
            spaceAfter=6
        ))
        
        # สไตล์สำหรับข้อความปกติ
        self.styles.add(ParagraphStyle(
            name='ThaiNormal',
            parent=self.styles['Normal'],
            fontName=self.thai_font,
            fontSize=12,
            alignment=TA_LEFT,
            spaceAfter=3
        ))
        
        # สไตล์สำหรับข้อความเล็ก
        self.styles.add(ParagraphStyle(
            name='ThaiSmall',
            parent=self.styles['Normal'],
            fontName=self.thai_font,
            fontSize=10,
            alignment=TA_LEFT,
            spaceAfter=2
        ))

    def generate_separate_weighing_report(self, ticket: WeightTicket) -> BytesIO:
        """
        สร้างรายงานบัตรชั่งแบบชั่งแยก (A5)
        """
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A5)
        story = []
        
        # หัวเอกสาร
        story.extend(self._create_header(ticket))
        story.append(Spacer(1, 10))
        
        # ข้อมูลหลัก
        story.extend(self._create_main_info(ticket))
        story.append(Spacer(1, 10))
        
        # ตารางน้ำหนัก
        story.extend(self._create_weight_table(ticket))
        story.append(Spacer(1, 15))
        
        # ส่วนท้ายเอกสาร
        story.extend(self._create_footer())
        
        doc.build(story)
        buffer.seek(0)
        return buffer

    def generate_combined_weighing_report(self, ticket: WeightTicket, items: List[WeightTicketItem]) -> BytesIO:
        """
        สร้างรายงานบัตรชั่งแบบชั่งรวม (A4)
        """
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        story = []
        
        # หัวเอกสาร (เหมือนชั่งแยก)
        story.extend(self._create_header(ticket))
        story.append(Spacer(1, 10))
        
        # ข้อมูลหลัก (เหมือนชั่งแยก)
        story.extend(self._create_main_info(ticket))
        story.append(Spacer(1, 10))
        
        # ตารางน้ำหนัก (เหมือนชั่งแยก)
        story.extend(self._create_weight_table(ticket))
        story.append(Spacer(1, 20))
        
        # ส่วนรายการสินค้า (ครึ่งล่างของ A4)
        story.extend(self._create_items_table(items))
        story.append(Spacer(1, 15))
        
        # ส่วนท้ายเอกสาร
        story.extend(self._create_footer())
        
        doc.build(story)
        buffer.seek(0)
        return buffer

    def _create_header(self, ticket: WeightTicket) -> List:
        """สร้างส่วนหัวเอกสาร"""
        elements = []
        
        # ชื่อบริษัท
        company_name = Paragraph("ZUBB STEEL บริษัท เหล็กทรัพย์ จำกัด", self.styles['ThaiTitle'])
        elements.append(company_name)
        
        # ที่อยู่
        address = Paragraph("8/88 หมู่ที่ 11 ถ.พุทธสาคร ต.อ้อมน้อย อ.กระทุ่มแบน จ.สมุทรสาคร", self.styles['ThaiSmall'])
        elements.append(address)
        elements.append(Spacer(1, 5))
        
        # หัวเอกสาร
        header_data = [
            ['', 'ต้นฉบับ', 'บัตรชั่ง']
        ]
        
        header_table = Table(header_data, colWidths=[100, 50, 50])
        header_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, -1), self.thai_font),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        elements.append(header_table)
        
        return elements

    def _create_main_info(self, ticket: WeightTicket) -> List:
        """สร้างส่วนข้อมูลหลัก"""
        elements = []
        
        # ข้อมูลหลักแบ่งเป็น 2 คอลัมน์
        main_data = [
            ['เลขที่บัตรชั่ง:', ticket.WE_ID, '', 'เลขที่ใบจ่าย:', ticket.WE_DIREF or '-'],
            ['บัตรชั่ง:', ticket.WE_VENDOR or '-', '', 'ทะเบียนรถ:', ticket.WE_LICENSE or '-'],
            ['สินค้า:', ticket.WE_MAT or '-', '', 'ประเภทสินค้า:', self._get_product_type(ticket.WE_TYPE)],
            ['คนขับรถ:', ticket.WE_DRIVER or '-', '', 'เครื่องชั่ง:', 'สนญ. P8'],
            ['จำนวนสินค้า:', f"{ticket.WE_QTY or 0} {ticket.WE_UOM or ''}", '', 'ประเภทรถ:', ticket.WE_TRUCK_CHAR or '-']
        ]
        
        main_table = Table(main_data, colWidths=[60, 120, 20, 60, 120])
        main_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), self.thai_font),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        elements.append(main_table)
        
        return elements

    def _create_weight_table(self, ticket: WeightTicket) -> List:
        """สร้างตารางน้ำหนัก"""
        elements = []
        
        # หัวตาราง
        weight_data = [
            ['รายการ', 'วันที่', 'เวลา', 'น้ำหนัก']
        ]
        
        # ข้อมูลน้ำหนัก
        if ticket.WE_TIMEIN:
            weight_data.append([
                'เข้า',
                ticket.WE_TIMEIN.strftime('%Y-%m-%d'),
                ticket.WE_TIMEIN.strftime('%H:%M:%S'),
                f"{ticket.WE_WEIGHTIN or 0:,.0f}"
            ])
        
        if ticket.WE_TIMEOUT:
            weight_data.append([
                'ออก',
                ticket.WE_TIMEOUT.strftime('%Y-%m-%d'),
                ticket.WE_TIMEOUT.strftime('%H:%M:%S'),
                f"{ticket.WE_WEIGHTOUT or 0:,.0f}"
            ])
        
        # น้ำหนักสุทธิ
        net_weight = (ticket.WE_WEIGHTOUT or 0) - (ticket.WE_WEIGHTIN or 0)
        weight_data.append([
            'น้ำหนักสุทธิ',
            '',
            '',
            f"{net_weight:,.0f}"
        ])
        
        weight_table = Table(weight_data, colWidths=[80, 80, 80, 80])
        weight_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (3, 1), (3, -1), 'RIGHT'),  # ชิดขวาสำหรับคอลัมน์น้ำหนัก
            ('FONTNAME', (0, 0), (-1, -1), self.thai_font),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        elements.append(weight_table)
        
        return elements

    def _create_items_table(self, items: List[WeightTicketItem]) -> List:
        """สร้างตารางรายการสินค้า (สำหรับชั่งรวม)"""
        elements = []
        
        # หัวข้อ
        title = Paragraph("รายการสินค้าในชั่งรวม", self.styles['ThaiHeading'])
        elements.append(title)
        elements.append(Spacer(1, 5))
        
        # หัวตาราง
        items_data = [
            ['ลำดับ', 'เลขที่เอกสาร', 'รายการ', 'รหัสสินค้า', 'ชื่อสินค้า', 'จำนวน', 'หน่วย']
        ]
        
        # ข้อมูลรายการ
        for i, item in enumerate(items, 1):
            items_data.append([
                str(i),
                item.VBELN or '-',
                item.POSNR or '-',
                item.WE_MAT_CD or '-',
                item.WE_MAT or '-',
                f"{item.WE_QTY or 0:,.2f}",
                item.WE_UOM or '-'
            ])
        
        items_table = Table(items_data, colWidths=[30, 80, 50, 80, 120, 60, 40])
        items_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (5, 1), (5, -1), 'RIGHT'),  # ชิดขวาสำหรับคอลัมน์จำนวน
            ('FONTNAME', (0, 0), (-1, -1), self.thai_font),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        elements.append(items_table)
        
        return elements

    def _create_footer(self) -> List:
        """สร้างส่วนท้ายเอกสาร"""
        elements = []
        
        # หมายเหตุ
        remark = Paragraph("หมายเหตุ: (ได้รับสินค้าตามรายการข้างต้นนี้ไว้ถูกต้องแล้ว)", self.styles['ThaiSmall'])
        elements.append(remark)
        elements.append(Spacer(1, 15))
        
        # ตารางลายเซ็น
        signature_data = [
            ['พนักงานชั่ง', 'ผู้รับสินค้า', 'ผู้อนุมัติ'],
            ['', '', ''],
            ['', '', ''],
            ['วันที่', 'วันที่', 'วันที่'],
            ['', '', '']
        ]
        
        signature_table = Table(signature_data, colWidths=[100, 100, 100])
        signature_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), self.thai_font),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        elements.append(signature_table)
        
        return elements

    def _get_product_type(self, we_type: str) -> str:
        """แปลงประเภทสินค้าจาก WE_TYPE เป็นข้อความภาษาไทย"""
        if we_type == 'O':
            return "สินค้าออก"
        else:
            return "สินค้าเข้า"
