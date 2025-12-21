import csv
import io
import base64
from typing import List, Dict, Any
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from datetime import datetime, date
from app import schemas
from sqlalchemy.orm import Session
from sqlalchemy import func, and_


def get_next_route_number(db: Session, driver_id: int, route_date: date = None) -> int:
    """Get the next sequential route number for a driver on a specific date."""
    if route_date is None:
        route_date = date.today()
    
    # Import here to avoid circular imports
    from app.models import Invoice
    
    # Get the highest route number for this driver on this date
    max_route = db.query(func.max(Invoice.route_number)).filter(
        and_(
            Invoice.assigned_driver_id == driver_id,
            func.date(Invoice.route_date) == route_date
        )
    ).scalar()
    
    # Return next route number (starting from 1 if no routes exist)
    return (max_route or 0) + 1


def format_route_display(route_number: int, route_name: str = None, route_date: str = None) -> str:
    """Format route display string combining number, name, and date."""
    base_display = f"Route {route_number}"
    
    # Add route name if provided
    if route_name:
        base_display += f": {route_name}"
    
    # Add date if provided for better identification
    if route_date:
        base_display += f" ({route_date})"
    
    return base_display


def validate_route_data(route_name: str = None) -> str:
    """Validate and clean route name data."""
    if route_name:
        # Clean and validate route name
        route_name = route_name.strip()
        if len(route_name) > 100:
            raise ValueError("Route name cannot exceed 100 characters")
        if not route_name:
            return None
    return route_name


def parse_csv_invoices(csv_content: str) -> List[Dict[str, Any]]:
    """Parse CSV content and return list of invoice data."""
    invoices = []
    failed_records = []
    
    try:
        csv_reader = csv.DictReader(io.StringIO(csv_content))
        
        for row_num, row in enumerate(csv_reader, start=2):  # Start from 2 (header is row 1)
            try:
                # Validate required fields
                required_fields = ['invoice_number', 'customer_name', 'customer_address', 'total_amount']
                missing_fields = [field for field in required_fields if not row.get(field)]
                
                if missing_fields:
                    failed_records.append({
                        'row': row_num,
                        'data': row,
                        'error': f"Missing required fields: {', '.join(missing_fields)}"
                    })
                    continue
                
                # Parse and validate data
                invoice_data = {
                    'invoice_number': row['invoice_number'].strip(),
                    'customer_name': row['customer_name'].strip(),
                    'customer_address': row['customer_address'].strip(),
                    'customer_phone': row.get('customer_phone', '').strip() or None,
                    'items': row.get('items', '').strip() or None,
                    'total_amount': float(row['total_amount'])
                }
                
                # Parse delivery date if provided
                if row.get('delivery_date'):
                    try:
                        invoice_data['delivery_date'] = datetime.strptime(
                            row['delivery_date'].strip(), '%Y-%m-%d'
                        )
                    except ValueError:
                        # Try different date format
                        try:
                            invoice_data['delivery_date'] = datetime.strptime(
                                row['delivery_date'].strip(), '%d/%m/%Y'
                            )
                        except ValueError:
                            failed_records.append({
                                'row': row_num,
                                'data': row,
                                'error': "Invalid delivery_date format. Use YYYY-MM-DD or DD/MM/YYYY"
                            })
                            continue
                
                invoices.append(invoice_data)
                
            except ValueError as e:
                failed_records.append({
                    'row': row_num,
                    'data': row,
                    'error': f"Data validation error: {str(e)}"
                })
            except Exception as e:
                failed_records.append({
                    'row': row_num,
                    'data': row,
                    'error': f"Unexpected error: {str(e)}"
                })
    
    except Exception as e:
        raise ValueError(f"Error parsing CSV: {str(e)}")
    
    return invoices, failed_records


def generate_delivery_pdf(invoice_data: dict, signature_data: str = None) -> bytes:
    """Generate PDF acknowledgment for delivery."""
    buffer = io.BytesIO()
    
    # Create PDF document
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=20,
        spaceAfter=30,
        alignment=1  # Center alignment
    )
    story.append(Paragraph("Pharmaceutical Delivery Acknowledgment", title_style))
    story.append(Spacer(1, 20))
    
    # Invoice details
    invoice_info = [
        ['Invoice Number:', invoice_data.get('invoice_number', 'N/A')],
        ['Customer Name:', invoice_data.get('customer_name', 'N/A')],
        ['Customer Address:', invoice_data.get('customer_address', 'N/A')],
        ['Customer Phone:', invoice_data.get('customer_phone', 'N/A')],
        ['Total Amount:', f"${invoice_data.get('total_amount', 0):.2f}"],
        ['Delivery Date:', invoice_data.get('delivery_date', 'N/A')],
        ['Status:', invoice_data.get('status', 'N/A')]
    ]
    
    invoice_table = Table(invoice_info, colWidths=[2*inch, 4*inch])
    invoice_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.grey),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('BACKGROUND', (1, 0), (1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    story.append(invoice_table)
    story.append(Spacer(1, 30))
    
    # Items section
    if invoice_data.get('items'):
        story.append(Paragraph("Items Delivered:", styles['Heading2']))
        story.append(Paragraph(invoice_data['items'], styles['Normal']))
        story.append(Spacer(1, 20))
    
    # Delivery notes
    if invoice_data.get('delivery_notes'):
        story.append(Paragraph("Delivery Notes:", styles['Heading2']))
        story.append(Paragraph(invoice_data['delivery_notes'], styles['Normal']))
        story.append(Spacer(1, 20))
    
    # Signature section
    story.append(Paragraph("Customer Signature:", styles['Heading2']))
    
    if signature_data:
        story.append(Paragraph("Digital signature captured on delivery", styles['Normal']))
        story.append(Spacer(1, 10))
        
        # Add signature timestamp
        if invoice_data.get('signature_timestamp'):
            timestamp_text = f"Signed on: {invoice_data['signature_timestamp']}"
            story.append(Paragraph(timestamp_text, styles['Normal']))
    else:
        # Add signature line for manual signing
        story.append(Spacer(1, 40))
        story.append(Paragraph("_" * 50, styles['Normal']))
        story.append(Paragraph("Customer Signature", styles['Normal']))
        story.append(Spacer(1, 20))
        story.append(Paragraph("Date: _______________", styles['Normal']))
    
    # Footer
    story.append(Spacer(1, 40))
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=10,
        alignment=1  # Center alignment
    )
    story.append(Paragraph("This document serves as proof of delivery", footer_style))
    story.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", footer_style))
    
    # Build PDF
    doc.build(story)
    
    buffer.seek(0)
    return buffer.getvalue()


def decode_signature(signature_data: str) -> bytes:
    """Decode base64 signature data."""
    try:
        # Remove data URL prefix if present
        if signature_data.startswith('data:image'):
            signature_data = signature_data.split(',')[1]
        
        return base64.b64decode(signature_data)
    except Exception as e:
        raise ValueError(f"Invalid signature data: {str(e)}")


def validate_file_upload(file_content: bytes, max_size: int = 10 * 1024 * 1024) -> bool:
    """Validate uploaded file size and basic format."""
    if len(file_content) > max_size:
        raise ValueError(f"File size exceeds maximum allowed size of {max_size} bytes")
    
    return True