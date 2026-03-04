from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from app.database import get_db
from app.models import User, Invoice, Branch, DriverBranch, UserRole
from app import auth, schemas
from datetime import datetime, timedelta, time
import os
from app.config import settings
import io
# from weasyprint import HTML  # Removed for Vercel compatibility
from jinja2 import Template
import base64

router = APIRouter()


@router.get("/driver-routes", response_model=schemas.RoutesResponse)
async def get_routes(
    route_date: Optional[str] = None,  # YYYY-MM-DD format
    current_driver: User = Depends(auth.get_current_driver_user),
    db: Session = Depends(get_db)
):
    """Driver-only: return all distinct routes assigned to the current driver.

    This endpoint is intended for the driver's dashboard dropdown. It returns a
    simple list (no pagination) of routes with `route_display`.
    """
    # Debug logging
    print(f"[DEBUG] /driver-routes called by driver_id: {current_driver.user_id}, name: {current_driver.name}")
    total_invoices = db.query(Invoice).count()
    assigned_invoices = db.query(Invoice).filter(Invoice.assigned_driver_id == current_driver.user_id).count()
    invoices_with_driver = db.query(Invoice).filter(Invoice.assigned_driver_id.isnot(None)).count()
    print(f"[DEBUG] Total invoices: {total_invoices}, Assigned to this driver: {assigned_invoices}, With any driver: {invoices_with_driver}")
    
    # Query distinct routes for this driver
    query = db.query(
        Invoice.route_number,
        Invoice.route_name,
        Invoice.route_date,
        func.count(Invoice.invoice_id).label('invoice_count')
    ).filter(
        and_(
            Invoice.assigned_driver_id == current_driver.user_id,
            Invoice.route_number.isnot(None)
        )
    ).group_by(
        Invoice.route_number,
        Invoice.route_name,
        Invoice.route_date
    )

    # Optional date filter (by route_date) using explicit range to avoid DB-specific date() issues
    if route_date:
        try:
            rd = datetime.strptime(route_date, "%Y-%m-%d").date()
            start = datetime.combine(rd, time.min)
            end = start + timedelta(days=1)
            query = query.filter(Invoice.route_date >= start, Invoice.route_date < end)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid route_date format. Use YYYY-MM-DD"
            )

    routes = query.order_by(Invoice.route_date.desc(), Invoice.route_number).all()

    # Convert to response format
    from app import utils
    route_list = []
    for route in routes:
        route_date_str = route.route_date.strftime("%Y-%m-%d") if route.route_date else ""
        route_display = utils.format_route_display(route.route_number, route.route_name, route_date_str)
        route_info = schemas.RouteInfo(
            route_number=route.route_number,
            route_name=route.route_name,
            route_display=route_display,
            invoice_count=route.invoice_count,
            driver_name=current_driver.name,
            created_date=route_date_str
        )
        route_list.append(route_info)
        print("Route Info: "+str(route_info))

    return schemas.RoutesResponse(
        routes=route_list,
        pagination=schemas.PaginationInfo(
            current_page=1,
            total_pages=1,
            total_count=len(route_list),
            per_page=len(route_list)
        )
    )


@router.get("/dashboard", response_model=schemas.DriverDashboardResponse)
async def get_driver_dashboard(
    current_driver: User = Depends(auth.get_current_driver_user),
    db: Session = Depends(get_db)
):
    """Get driver dashboard with summary statistics."""
    
    # Get all invoices assigned to this driver
    all_invoices = db.query(Invoice).filter(
        Invoice.assigned_driver_id == current_driver.user_id
    ).all()
    
    # Calculate statistics
    total_invoices = len(all_invoices)
    pending_invoices = len([inv for inv in all_invoices if inv.status == "pending"])
    acknowledged_invoices = len([inv for inv in all_invoices if inv.status == "acknowledged"])
    
    # Get today's invoices
    today = datetime.utcnow().date()
    today_invoices = [
        inv for inv in all_invoices 
        if inv.created_at and inv.created_at.date() == today
    ]
    
    # Get driver's branches
    driver_branches = db.query(DriverBranch).join(Branch).filter(
        DriverBranch.driver_id == current_driver.user_id
    ).all()
    branches = [
        db.query(Branch).filter(Branch.branch_id == db_branch.branch_id).first().name
        for db_branch in driver_branches
    ]
    
    return schemas.DriverDashboardResponse(
        driver_name=current_driver.name,
        branches=branches,
        total_invoices=total_invoices,
        pending_invoices=pending_invoices,
        acknowledged_invoices=acknowledged_invoices,
        today_invoices=len(today_invoices)
    )

@router.get("/invoices", response_model=schemas.InvoicesResponse)
async def get_invoices(
    branch_id: Optional[int] = None,  # Changed from branch name to branch ID
    status_filter: Optional[str] = None,
    search: Optional[str] = None,
    from_date: Optional[str] = None,  # Now filters by created_at (system entry date)
    to_date: Optional[str] = None,    # Now filters by created_at (system entry date)
    driver_id: Optional[int] = None,  # Changed from driver name to driver ID
    route_number: Optional[int] = None,  # Filter by route number
    route_date: Optional[str] = None,    # Filter by route date (YYYY-MM-DD)
    page: int = 1,
    per_page: int = 20,
    current_user: User = Depends(auth.get_current_driver_admin_user),
    db: Session = Depends(get_db)
):
    """Get invoices with filtering and pagination. Admin users see only their branch, super admin can filter by branch, drivers see only their assigned invoices."""
    query = db.query(Invoice)

    # Role-based filtering
    if current_user.role.value == "driver":
        # Drivers can only see their assigned invoices
        query = query.filter(Invoice.assigned_driver_id == current_user.user_id)
        print(f"Driver {current_user.user_id} accessing their invoices")
        
    elif current_user.role.value == "admin":
        # Regular admin can only see their own branch
        if not current_user.branch_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin must be assigned to a branch"
            )
        query = query.filter(Invoice.branch_id == current_user.branch_id)
        
    else:
        # Super admin MUST specify a branch - they cannot see all invoices
        if branch_id is None or branch_id == "":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Super admin must specify a branch to view invoices"
            )
        branch_obj = db.query(Branch).filter(Branch.branch_id == branch_id).first()
        if not branch_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Branch with ID {branch_id} not found"
            )
        query = query.filter(Invoice.branch_id == branch_id)
    
    # Filter by status
    if status_filter:
        query = query.filter(Invoice.status == status_filter)
    
    # Search by customer name or invoice number
    if search:
        query = query.filter(
            or_(
                Invoice.cust_name.ilike(f"%{search}%"),
                Invoice.n_inv_no.ilike(f"%{search}%")
            )
        )
    
    # Date range filter (by created_at - system entry date)
    if from_date:
        try:
            from_dt = datetime.strptime(from_date, "%Y-%m-%d")
            query = query.filter(func.date(Invoice.created_at) >= from_dt.date())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid from_date format. Use YYYY-MM-DD"
            )

    if to_date:
        try:
            to_dt = datetime.strptime(to_date, "%Y-%m-%d")
            query = query.filter(func.date(Invoice.created_at) <= to_dt.date())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid to_date format. Use YYYY-MM-DD"
            )

    # Filter by driver ID (only for admin/super_admin, drivers can't filter by other drivers)
    if driver_id is not None and current_user.role.value != "driver":
        driver_obj = db.query(User).filter(
            and_(User.user_id == driver_id, User.role == UserRole.driver)
        ).first()
        if not driver_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Driver with ID {driver_id} not found"
            )
        query = query.filter(Invoice.assigned_driver_id == driver_id)
    
    # Route filtering
    if route_number is not None:
        query = query.filter(Invoice.route_number == route_number)
    
    if route_date:
        try:
            route_dt = datetime.strptime(route_date, "%Y-%m-%d").date()
            query = query.filter(func.date(Invoice.route_date) == route_dt)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid route_date format. Use YYYY-MM-DD"
            )
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    offset = (page - 1) * per_page
    invoices = query.offset(offset).limit(per_page).all()
    
    # Convert to response format
    invoice_list = []
    for invoice in invoices:
        # Get branch name
        branch_name = ""
        if invoice.branch_id:
            branch_obj = db.query(Branch).filter(Branch.branch_id == invoice.branch_id).first()
            if branch_obj:
                branch_name = branch_obj.name
        
        # Get driver name
        driver_name = ""
        if invoice.assigned_driver_id:
            driver_obj = db.query(User).filter(User.user_id == invoice.assigned_driver_id).first()
            if driver_obj:
                driver_name = driver_obj.name
        
        # Import utils here to avoid circular imports
        from app import utils
        route_date_str = invoice.route_date.strftime("%Y-%m-%d") if invoice.route_date else ""
        route_display = utils.format_route_display(invoice.route_number, invoice.route_name, route_date_str) if invoice.route_number else None
        
        invoice_info = schemas.InvoiceInfo(
            id=str(invoice.invoice_id),
            invoice_number=invoice.n_inv_no,
            customer_name=invoice.cust_name,
            amount=float(invoice.amount),
            invoice_date=invoice.invoice_date.strftime("%Y-%m-%d") if invoice.invoice_date else None,
            status=invoice.status,
            branch=branch_name,
            driver=driver_name,
            created_date=invoice.created_at.strftime("%Y-%m-%d") if invoice.created_at else "",
            is_acknowledged=invoice.status == "delivered",
            route_number=invoice.route_number,
            route_name=invoice.route_name,
            route_display=route_display
        )
        invoice_list.append(invoice_info)
    
    return schemas.InvoicesResponse(
        invoices=invoice_list,
        pagination=schemas.PaginationInfo(
            current_page=page,
            total_pages=(total + per_page - 1) // per_page,
            total_count=total,
            per_page=per_page
        )
    )


@router.get("/invoices/{invoice_id}", response_model=schemas.InvoiceDetailResponse)
async def get_invoice_detail(
    invoice_id: str,
    current_driver: User = Depends(auth.get_current_driver_user),
    db: Session = Depends(get_db)
):
    """Get detailed information about a specific invoice."""
    
    try:
        invoice_id_int = int(invoice_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid invoice ID format"
        )
    
    invoice = db.query(Invoice).filter(Invoice.invoice_id == invoice_id_int).first()
    
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )
    
    # Verify the invoice is assigned to this driver
    if invoice.assigned_driver_id != current_driver.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invoice not assigned to current driver"
        )
    
    # Get branch name
    branch_name = ""
    if invoice.branch_id:
        branch = db.query(Branch).filter(Branch.branch_id == invoice.branch_id).first()
        if branch:
            branch_name = branch.name
    
    invoice_info = schemas.InvoiceInfo(
        id=str(invoice.invoice_id),
        invoice_number=invoice.n_inv_no,
        customer_name=invoice.cust_name,
        amount=float(invoice.amount),
        invoice_date=invoice.invoice_date.strftime("%Y-%m-%d") if invoice.invoice_date else None,
        status=invoice.status,
        branch=branch_name,
        driver=current_driver.name,
        created_date=invoice.created_at.strftime("%Y-%m-%d") if invoice.created_at else "",
        is_acknowledged=invoice.status == "delivered"
    )
    
    return schemas.InvoiceDetailResponse(invoice=invoice_info)


@router.post("/invoices/{invoice_id}/acknowledge", response_model=schemas.AcknowledgeResponse)
async def acknowledge_invoice(
    invoice_id: str,
    signature_file: UploadFile = File(...),  # Required signature PNG
    notes: Optional[str] = Form(None),  # Optional name/notes
    photo_file: Optional[UploadFile] = File(None),  # Optional photo
    current_driver: User = Depends(auth.get_current_driver_user),
    db: Session = Depends(get_db)
):
    """Acknowledge an invoice with signature, generate PDF, and store it."""
    
    try:
        invoice_id_int = int(invoice_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid invoice ID format"
        )
    
    invoice = db.query(Invoice).filter(Invoice.invoice_id == invoice_id_int).first()
    
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )
    
    # Verify the invoice is assigned to this driver
    if invoice.assigned_driver_id != current_driver.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invoice not assigned to current driver"
        )
    
    # Check if already acknowledged
    if invoice.status == "acknowledged":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invoice already acknowledged"
        )
    
    # Validate signature file (must be PNG)
    if not signature_file.content_type or signature_file.content_type != 'image/png':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Signature file must be a PNG image"
        )
    
    # Read signature content
    signature_content = await signature_file.read()
    
    # Save signature file locally
    signature_filename = f"signature_{invoice_id}_{int(datetime.utcnow().timestamp())}.png"
    signature_path = os.path.join(settings.upload_folder, signature_filename)
    try:
        with open(signature_path, 'wb') as f:
            f.write(signature_content)
        signature_url = f"/uploads/{signature_filename}"
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save signature file: {str(e)}"
        )
    
    # Optional: Validate photo file if provided
    photo_content = None
    if photo_file:
        if not photo_file.content_type.startswith('image/'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Photo file must be an image"
            )
        photo_content = await photo_file.read()
    
    # Generate PDF using ReportLab (Vercel compatible)
    pdf_filename = f"invoice_{invoice_id}_acknowledged.pdf"

    # Prepare data for PDF template
    signature_data_url = f"data:image/png;base64,{base64.b64encode(signature_content).decode('utf-8')}"

    # Get branch info for delivery address
    branch_name = ""
    branch_city = ""
    if invoice.branch_id:
        branch_obj = db.query(Branch).filter(Branch.branch_id == invoice.branch_id).first()
        if branch_obj:
            branch_name = branch_obj.name
            branch_city = branch_obj.city if hasattr(branch_obj, 'city') else branch_name

    template_data = {
        "company_logo_url_or_data": "",  # Add logo URL if available
        "invoice_id": invoice.n_inv_no,
        "date": datetime.utcnow().strftime("%Y-%m-%d"),
        "customer_name": invoice.cust_name,
        "branch_address": f"{branch_name}, {branch_city}",
        "delivered_by_name": current_driver.name,
        "signature_data_url_or_path": signature_data_url,
        "signature_name_or_empty": notes or "",
        "company_name": "ZED WELL",
        "company_support_contact": "support@zedwell.com"  # Customize as needed
    }

    # Generate PDF using ReportLab
    from app import utils
    pdf_content = utils.generate_acknowledgement_pdf(template_data)

    # Save PDF to local directory
    pdf_path = os.path.join(settings.pdf_folder, pdf_filename)
    try:
        with open(pdf_path, 'wb') as f:
            f.write(pdf_content)
        pdf_url = f"/pdfs/{pdf_filename}"
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save PDF locally: {str(e)}"
        )

    # Update invoice
    invoice.pdf_path = pdf_filename  # Store the filename for local storage
    invoice.status = "acknowledged"
    invoice.driver_signature = signature_filename  # Store the signature filename
    invoice.driver_notes = notes
    invoice.acknowledged_at = datetime.utcnow()

    db.commit()

    return schemas.AcknowledgeResponse(
        message="Invoice acknowledged and PDF generated successfully",
        invoice_id=str(invoice.invoice_id),
        acknowledged_at=invoice.acknowledged_at.isoformat() if invoice.acknowledged_at else "",
        pdf_url=pdf_url
    )



@router.get("/profile", response_model=schemas.DriverProfileResponse)
async def get_driver_profile(
    current_driver: User = Depends(auth.get_current_driver_user),
    db: Session = Depends(get_db)
):
    """Get current driver's profile information."""
    
    # Get driver's branches
    driver_branches = db.query(DriverBranch).join(Branch).filter(
        DriverBranch.driver_id == current_driver.user_id
    ).all()
    branches = [
        db.query(Branch).filter(Branch.branch_id == db_branch.branch_id).first().name
        for db_branch in driver_branches
    ]
    
    # Get statistics
    total_invoices = db.query(Invoice).filter(
        Invoice.assigned_driver_id == current_driver.user_id
    ).count()
    
    acknowledged_invoices = db.query(Invoice).filter(
        and_(
            Invoice.assigned_driver_id == current_driver.user_id,
            Invoice.status == "acknowledged"
        )
    ).count()
    
    return schemas.DriverProfileResponse(
        driver=schemas.UserInfo(
            id=str(current_driver.user_id),
            username=current_driver.email,
            driver_name=current_driver.name,
            role=current_driver.role.value,
            branches=branches,
            is_active=True
        ),
        statistics=schemas.DriverStats(
            total_invoices=total_invoices,
            acknowledged_invoices=acknowledged_invoices,
            pending_invoices=total_invoices - acknowledged_invoices
        )
    )


@router.get("/invoices/{invoice_id}/download-pdf")
async def download_invoice_pdf(
    invoice_id: str,
    current_user: User = Depends(auth.get_current_driver_admin_user),
    db: Session = Depends(get_db)
):
    """Download the PDF acknowledgment for an invoice."""

    try:
        invoice_id_int = int(invoice_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid invoice ID format"
        )

    invoice = db.query(Invoice).filter(Invoice.invoice_id == invoice_id_int).first()

    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )

    # Permission check: drivers can only access their own invoices, admins/super admins can access any
    if current_user.role.value == "driver":
        if invoice.assigned_driver_id != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invoice not assigned to current driver"
            )
    # Admins and super admins can access any invoice (no additional check needed)

    # Check if PDF exists
    if not invoice.pdf_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PDF not found for this invoice"
        )

    # Check if invoice is acknowledged
    if invoice.status != "delivered":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="PDF is only available for acknowledged invoices"
        )

    try:
        # Read PDF from local storage
        pdf_path = os.path.join(settings.pdf_folder, invoice.pdf_path)
        if not os.path.exists(pdf_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="PDF not found in storage"
            )
        with open(pdf_path, 'rb') as f:
            pdf_content = f.read()

        filename = f"invoice_{invoice.n_inv_no}_acknowledged.pdf"

        return Response(
            content=pdf_content,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error downloading PDF: {str(e)}"
        )


@router.get("/invoices/{invoice_id}/preview-pdf")
async def preview_invoice_pdf(
    invoice_id: str,
    current_user: User = Depends(auth.get_current_driver_admin_user),
    db: Session = Depends(get_db)
):
    """Preview the PDF acknowledgment for an invoice in browser."""

    try:
        invoice_id_int = int(invoice_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid invoice ID format"
        )

    invoice = db.query(Invoice).filter(Invoice.invoice_id == invoice_id_int).first()

    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )

    # Permission check: drivers can only access their own invoices, admins/super admins can access any
    if current_user.role.value == "driver":
        if invoice.assigned_driver_id != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invoice not assigned to current driver"
            )
    # Admins and super admins can access any invoice (no additional check needed)

    # Check if PDF exists
    if not invoice.pdf_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PDF not found for this invoice"
        )

    # Check if invoice is acknowledged
    if invoice.status != "delivered":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="PDF is only available for acknowledged invoices"
        )

    try:
        # Read PDF from local storage
        pdf_path = os.path.join(settings.pdf_folder, invoice.pdf_path)
        if not os.path.exists(pdf_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="PDF not found in storage"
            )
        with open(pdf_path, 'rb') as f:
            pdf_content = f.read()

        filename = f"invoice_{invoice.n_inv_no}_acknowledged.pdf"

        return Response(
            content=pdf_content,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"inline; filename={filename}"
            }
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error downloading PDF: {str(e)}"
        )


@router.get("/admin/invoices/{invoice_id}/download-pdf")
async def admin_download_invoice_pdf(
    invoice_id: str,
    current_user: User = Depends(auth.get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Download the PDF acknowledgment for any invoice (admin only)."""

    try:
        invoice_id_int = int(invoice_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid invoice ID format"
        )

    invoice = db.query(Invoice).filter(Invoice.invoice_id == invoice_id_int).first()

    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )

    # Check if PDF exists
    if not invoice.pdf_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PDF not found for this invoice"
        )

    # Check if invoice is acknowledged
    if invoice.status != "delivered":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="PDF is only available for acknowledged invoices"
        )

    try:
        # Read PDF from local storage
        pdf_path = os.path.join(settings.pdf_folder, invoice.pdf_path)
        if not os.path.exists(pdf_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="PDF not found in storage"
            )
        with open(pdf_path, 'rb') as f:
            pdf_content = f.read()

        filename = f"invoice_{invoice.n_inv_no}_acknowledged.pdf"

        return Response(
            content=pdf_content,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error downloading PDF: {str(e)}"
        )


@router.get("/admin/invoices/{invoice_id}/preview-pdf")
async def admin_preview_invoice_pdf(
    invoice_id: str,
    current_user: User = Depends(auth.get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Preview the PDF acknowledgment for any invoice in browser (admin only)."""

    try:
        invoice_id_int = int(invoice_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid invoice ID format"
        )

    invoice = db.query(Invoice).filter(Invoice.invoice_id == invoice_id_int).first()

    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )

    # Check if PDF exists
    if not invoice.pdf_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PDF not found for this invoice"
        )

    # Check if invoice is acknowledged
    if invoice.status != "delivered":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="PDF is only available for acknowledged invoices"
        )

    try:
        # Read PDF from local storage
        pdf_path = os.path.join(settings.pdf_folder, invoice.pdf_path)
        if not os.path.exists(pdf_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="PDF not found in storage"
            )
        with open(pdf_path, 'rb') as f:
            pdf_content = f.read()

        filename = f"invoice_{invoice.n_inv_no}_acknowledged.pdf"

        return Response(
            content=pdf_content,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"inline; filename={filename}"
            }
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error downloading PDF: {str(e)}"
        )


@router.get("/admin/available-routes", response_model=schemas.RoutesResponse)
async def get_admin_available_routes(
    driver_id: int,
    route_date: str,  # Required date parameter in YYYY-MM-DD format
    current_user: User = Depends(auth.get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get available routes for a specific driver on a specific date (admin only)."""
    # Validate date format
    try:
        route_dt = datetime.strptime(route_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid route_date format. Use YYYY-MM-DD"
        )
    
    # Verify the driver exists
    driver = db.query(User).filter(
        and_(User.user_id == driver_id, User.role == UserRole.driver)
    ).first()
    if not driver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Driver with ID {driver_id} not found"
        )
    
    # Query to get distinct routes for this driver on the specified date
    query = db.query(
        Invoice.route_number,
        Invoice.route_name,
        Invoice.route_date,
        func.count(Invoice.invoice_id).label('invoice_count')
    ).filter(
        and_(
            Invoice.assigned_driver_id == driver_id,
            Invoice.route_number.isnot(None),
            func.date(Invoice.route_date) == route_dt
        )
    ).group_by(
        Invoice.route_number,
        Invoice.route_name,
        Invoice.route_date
    )
    
    # Get all routes for this driver on this date
    routes = query.order_by(Invoice.route_number).all()
    
    # Convert to response format
    route_list = []
    for route in routes:
        # Import utils here to avoid circular imports
        from app import utils
        route_date_str = route.route_date.strftime("%Y-%m-%d") if route.route_date else ""
        route_display = utils.format_route_display(route.route_number, route.route_name, route_date_str)
        
        route_info = schemas.RouteInfo(
            route_number=route.route_number,
            route_name=route.route_name,
            route_display=route_display,
            invoice_count=route.invoice_count,
            driver_name=driver.name,
            created_date=route.route_date.strftime("%Y-%m-%d") if route.route_date else ""
        )
        route_list.append(route_info)
    
    return schemas.RoutesResponse(
        routes=route_list,
        pagination=schemas.PaginationInfo(
            current_page=1,
            total_pages=1,
            total_count=len(route_list),
            per_page=len(route_list)
        )
    )


@router.get("/available-routes", response_model=schemas.RoutesResponse)
async def get_available_routes(
    route_date: str,  # Required date parameter in YYYY-MM-DD format
    driver_id: Optional[int] = None,  # Optional driver ID for admin use
    current_user: User = Depends(auth.get_current_driver_admin_user),
    db: Session = Depends(get_db)
):
    """Get available routes for the current driver (or specified driver for admin) on a specific date."""
    # Validate date format
    try:
        route_dt = datetime.strptime(route_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid route_date format. Use YYYY-MM-DD"
        )
    
    # Determine which driver to get routes for
    target_driver_id = driver_id if driver_id and current_user.role.value in ["admin", "super_admin"] else current_user.user_id
    
    # If admin specified a driver_id, verify it exists
    if driver_id and current_user.role.value in ["admin", "super_admin"]:
        driver = db.query(User).filter(
            and_(User.user_id == driver_id, User.role == UserRole.driver)
        ).first()
        if not driver:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Driver with ID {driver_id} not found"
            )
    elif current_user.role.value == "driver" and driver_id:
        # Drivers can't specify other drivers
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Drivers can only view their own routes"
        )
    
    # Query to get distinct routes for this driver on the specified date
    query = db.query(
        Invoice.route_number,
        Invoice.route_name,
        Invoice.route_date,
        func.count(Invoice.invoice_id).label('invoice_count')
    ).filter(
        and_(
            Invoice.assigned_driver_id == target_driver_id,
            Invoice.route_number.isnot(None),
            func.date(Invoice.route_date) == route_dt
        )
    ).group_by(
        Invoice.route_number,
        Invoice.route_name,
        Invoice.route_date
    )
    
    # Get all routes for this driver on this date
    routes = query.order_by(Invoice.route_number).all()
    
    # Get driver name
    driver_name = current_user.name
    if driver_id and current_user.role.value in ["admin", "super_admin"]:
        driver_obj = db.query(User).filter(User.user_id == target_driver_id).first()
        if driver_obj:
            driver_name = driver_obj.name
    
    # Convert to response format
    route_list = []
    for route in routes:
        # Import utils here to avoid circular imports
        from app import utils
        route_date_str = route.route_date.strftime("%Y-%m-%d") if route.route_date else ""
        route_display = utils.format_route_display(route.route_number, route.route_name, route_date_str)
        
        route_info = schemas.RouteInfo(
            route_number=route.route_number,
            route_name=route.route_name,
            route_display=route_display,
            invoice_count=route.invoice_count,
            driver_name=driver_name,
            created_date=route.route_date.strftime("%Y-%m-%d") if route.route_date else ""
        )
        route_list.append(route_info)
    
    return schemas.RoutesResponse(
        routes=route_list,
        pagination=schemas.PaginationInfo(
            current_page=1,
            total_pages=1,
            total_count=len(route_list),
            per_page=len(route_list)
        )
    )


@router.get("/customer-visits", response_model=schemas.CustomerVisitsResponse)
async def get_customer_visits(
    route_date: Optional[str] = None,  # YYYY-MM-DD format
    route_number: Optional[int] = None,
    page: int = 1,
    per_page: int = 20,
    current_driver: User = Depends(auth.get_current_driver_user),
    db: Session = Depends(get_db)
):
    """Get customer visits (grouped invoices) for the current driver."""
    query = db.query(
        Invoice.cust_name,
        Invoice.route_number,
        Invoice.route_name,
        Invoice.route_date,
        func.count(Invoice.invoice_id).label('invoice_count'),
        func.sum(Invoice.amount).label('total_amount'),
        func.array_agg(Invoice.invoice_id).label('invoice_ids')
    ).filter(
        and_(
            Invoice.assigned_driver_id == current_driver.user_id,
            Invoice.route_number.isnot(None),
            Invoice.cust_name.isnot(None)
        )
    ).group_by(
        Invoice.cust_name,
        Invoice.route_number,
        Invoice.route_name,
        Invoice.route_date
    )

    # Filter by route date
    if route_date:
        try:
            route_dt = datetime.strptime(route_date, "%Y-%m-%d").date()
            query = query.filter(func.date(Invoice.route_date) == route_dt)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid route_date format. Use YYYY-MM-DD"
            )

    # Filter by route number
    if route_number is not None:
        query = query.filter(Invoice.route_number == route_number)

    # Get total count
    total = query.count()

    # Apply pagination and ordering
    visits = query.order_by(
        Invoice.route_date.desc(),
        Invoice.route_number,
        Invoice.cust_name
    ).offset((page - 1) * per_page).limit(per_page).all()

    # Convert to response format
    visit_list = []
    for visit in visits:
        # Import utils here to avoid circular imports
        from app import utils
        route_date_str = visit.route_date.strftime("%Y-%m-%d") if visit.route_date else ""
        route_display = utils.format_route_display(visit.route_number, visit.route_name, route_date_str)

        # Check if all invoices in this visit are acknowledged
        invoice_ids = visit.invoice_ids
        acknowledged_count = db.query(Invoice).filter(
            and_(
                Invoice.invoice_id.in_(invoice_ids),
                Invoice.status == "acknowledged"
            )
        ).count()

        visit_info = schemas.CustomerVisitInfo(
            customer_name=visit.cust_name,
            route_number=visit.route_number,
            route_name=visit.route_name,
            route_display=route_display,
            route_date=route_date_str,
            invoice_count=visit.invoice_count,
            total_amount=float(visit.total_amount),
            acknowledged_count=acknowledged_count,
            is_fully_acknowledged=acknowledged_count == visit.invoice_count,
            invoice_ids=invoice_ids
        )
        visit_list.append(visit_info)

    return schemas.CustomerVisitsResponse(
        visits=visit_list,
        pagination=schemas.PaginationInfo(
            current_page=page,
            total_pages=(total + per_page - 1) // per_page,
            total_count=total,
            per_page=per_page
        )
    )


@router.get("/customer-visits/{customer_name}/{route_number}/{route_date}", response_model=schemas.CustomerVisitDetailResponse)
async def get_customer_visit_detail(
    customer_name: str,
    route_number: int,
    route_date: str,
    current_driver: User = Depends(auth.get_current_driver_user),
    db: Session = Depends(get_db)
):
    """Get detailed information about all invoices for a specific customer visit."""

    try:
        route_dt = datetime.strptime(route_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid route_date format. Use YYYY-MM-DD"
        )

    # Get all invoices for this customer visit
    invoices = db.query(Invoice).filter(
        and_(
            Invoice.assigned_driver_id == current_driver.user_id,
            Invoice.cust_name == customer_name,
            Invoice.route_number == route_number,
            func.date(Invoice.route_date) == route_dt
        )
    ).all()

    if not invoices:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer visit not found"
        )

    # Import utils here to avoid circular imports
    from app import utils
    route_display = utils.format_route_display(route_number, invoices[0].route_name, route_date)

    # Calculate totals
    total_amount = sum(float(invoice.amount) for invoice in invoices)
    acknowledged_count = sum(1 for invoice in invoices if invoice.status == "acknowledged")

    # Convert invoices to response format
    invoice_list = []
    for invoice in invoices:
        # Get branch name
        branch_name = ""
        if invoice.branch_id:
            branch_obj = db.query(Branch).filter(Branch.branch_id == invoice.branch_id).first()
            if branch_obj:
                branch_name = branch_obj.name

        route_date_str = invoice.route_date.strftime("%Y-%m-%d") if invoice.route_date else ""
        route_display_inv = utils.format_route_display(invoice.route_number, invoice.route_name, route_date_str)

        invoice_info = schemas.InvoiceInfo(
            id=str(invoice.invoice_id),
            invoice_number=invoice.n_inv_no,
            customer_name=invoice.cust_name,
            amount=float(invoice.amount),
            invoice_date=invoice.invoice_date.strftime("%Y-%m-%d") if invoice.invoice_date else None,
            status=invoice.status,
            branch=branch_name,
            driver=current_driver.name,
            created_date=invoice.created_at.strftime("%Y-%m-%d") if invoice.created_at else "",
            is_acknowledged=invoice.status == "delivered",
            route_number=invoice.route_number,
            route_name=invoice.route_name,
            route_display=route_display_inv
        )
        invoice_list.append(invoice_info)

    return schemas.CustomerVisitDetailResponse(
        customer_name=customer_name,
        route_display=route_display,
        route_date=route_date,
        total_amount=total_amount,
        acknowledged_count=acknowledged_count,
        total_count=len(invoices),
        invoices=invoice_list
    )


@router.post("/customer-visits/{customer_name}/{route_number}/{route_date}/acknowledge", response_model=schemas.CustomerVisitAcknowledgeResponse)
async def acknowledge_customer_visit(
    customer_name: str,
    route_number: int,
    route_date: str,
    signature_file: UploadFile = File(...),  # Required signature PNG
    notes: Optional[str] = Form(None),  # Optional name/notes
    current_driver: User = Depends(auth.get_current_driver_user),
    db: Session = Depends(get_db)
):
    """Acknowledge all invoices for a customer visit with a single signature."""

    try:
        route_dt = datetime.strptime(route_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid route_date format. Use YYYY-MM-DD"
        )

    # Get all invoices for this customer visit
    invoices = db.query(Invoice).filter(
        and_(
            Invoice.assigned_driver_id == current_driver.user_id,
            Invoice.cust_name == customer_name,
            Invoice.route_number == route_number,
            func.date(Invoice.route_date) == route_dt
        )
    ).all()

    if not invoices:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer visit not found"
        )

    # Check if any invoices are already acknowledged
    already_acknowledged = [inv for inv in invoices if inv.status == "acknowledged"]
    if already_acknowledged:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Some invoices are already acknowledged: {[inv.n_inv_no for inv in already_acknowledged]}"
        )

    # Validate signature file (must be PNG)
    if not signature_file.content_type or signature_file.content_type != 'image/png':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Signature file must be a PNG image"
        )

    # Read signature content
    signature_content = await signature_file.read()

    # Save signature file locally (shared for all invoices in this visit)
    signature_filename = f"signature_visit_{customer_name.replace(' ', '_')}_{route_number}_{route_date}_{int(datetime.utcnow().timestamp())}.png"
    signature_path = os.path.join(settings.upload_folder, signature_filename)
    try:
        with open(signature_path, 'wb') as f:
            f.write(signature_content)
        signature_url = f"/uploads/{signature_filename}"
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save signature file: {str(e)}"
        )

    acknowledged_invoice_ids = []

    # Process each invoice
    for invoice in invoices:
        # Generate PDF for this invoice
        pdf_filename = f"invoice_{invoice.invoice_id}_acknowledged.pdf"

        # Prepare data for HTML template
        signature_data_url = f"data:image/png;base64,{base64.b64encode(signature_content).decode('utf-8')}"

        # Get branch info for delivery address
        branch_name = ""
        branch_city = ""
        if invoice.branch_id:
            branch_obj = db.query(Branch).filter(Branch.branch_id == invoice.branch_id).first()
            if branch_obj:
                branch_name = branch_obj.name
                branch_city = branch_obj.city if hasattr(branch_obj, 'city') else branch_name

        template_data = {
            "company_logo_url_or_data": "",  # Add logo URL if available
            "invoice_id": invoice.n_inv_no,
            "date": datetime.utcnow().strftime("%Y-%m-%d"),
            "customer_name": invoice.cust_name,
            "branch_address": f"{branch_name}, {branch_city}",
            "delivered_by_name": current_driver.name,
            "signature_data_url_or_path": signature_data_url,
            "signature_name_or_empty": notes or "",
            "company_name": "ZED WELL",
            "company_support_contact": "support@zedwell.com"  # Customize as needed
        }

        # Generate PDF using ReportLab
        from app import utils
        pdf_content = utils.generate_acknowledgement_pdf(template_data)

        # Save PDF to local directory
        pdf_path = os.path.join(settings.pdf_folder, pdf_filename)
        try:
            with open(pdf_path, 'wb') as f:
                f.write(pdf_content)
            pdf_url = f"/pdfs/{pdf_filename}"
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save PDF for invoice {invoice.n_inv_no}: {str(e)}"
            )

        # Update invoice
        invoice.pdf_path = pdf_filename  # Store the filename for local storage
        invoice.status = "acknowledged"
        invoice.driver_signature = signature_filename  # Store the shared signature filename
        invoice.driver_notes = notes
        invoice.acknowledged_at = datetime.utcnow()

        acknowledged_invoice_ids.append(str(invoice.invoice_id))

    db.commit()

    return schemas.CustomerVisitAcknowledgeResponse(
        message=f"Successfully acknowledged {len(invoices)} invoices for {customer_name}",
        customer_name=customer_name,
        acknowledged_invoices=acknowledged_invoice_ids,
        acknowledged_at=datetime.utcnow().isoformat()
    )


# New Grouped Invoice Endpoints for Driver List View
@router.get("/invoices-grouped", response_model=schemas.GroupedInvoicesResponse)
async def get_grouped_invoices(
    route_number: Optional[int] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    created_date: Optional[str] = None,
    current_driver: User = Depends(auth.get_current_driver_user),
    db: Session = Depends(get_db)
):
    """
    Get deduplicated customer list for driver's invoices.
    Groups by route_number + customer_name.
    Filters by created_date if provided (YYYY-MM-DD format) - when invoice was entered into system.
    """
    from app.crud import get_grouped_invoices_for_driver
    
    groups = get_grouped_invoices_for_driver(
        db,
        driver_id=current_driver.user_id,
        route_number=route_number,
        status=status,
        search=search,
        created_date=created_date
    )
    
    # Count status groups
    pending_count = sum(1 for g in groups if g["status"] == "pending")
    delivered_count = sum(1 for g in groups if g["status"] == "delivered")
    
    # Convert to schema objects
    group_responses = []
    for group in groups:
        # Get route display
        route_display = None
        if group["route_number"]:
            route_display = f"Route {group['route_number']}"
            if group["route_name"]:
                route_display += f": {group['route_name']}"
        
        # Get branch name for first invoice in group
        branch_name = None
        first_invoice = db.query(Invoice).filter(Invoice.invoice_id == group["first_invoice_id"]).first()
        if first_invoice and first_invoice.branch_id:
            branch_obj = db.query(Branch).filter(Branch.branch_id == first_invoice.branch_id).first()
            if branch_obj:
                branch_name = branch_obj.name
        
        group_responses.append(schemas.CustomerGroupInfo(
            customer_visit_group=group["customer_visit_group"],
            customer_name=group["customer_name"],
            route_number=group["route_number"],
            route_name=group["route_name"],
            route_display=route_display,
            invoice_count=group["invoice_count"],
            total_amount=group["total_amount"],
            status=group["status"],
            first_invoice_id=group["first_invoice_id"],
            invoice_numbers=group["invoice_numbers"],
            sequence_order=group["sequence_order"],
            branch=branch_name
        ))
    
    return schemas.GroupedInvoicesResponse(
        groups=group_responses,
        total_groups=len(groups),
        pending_groups=pending_count,
        delivered_groups=delivered_count
    )


@router.get("/customer-group/{group_id}", response_model=schemas.CustomerGroupDetail)
async def get_customer_group_detail(
    group_id: str,
    current_driver: User = Depends(auth.get_current_driver_user),
    db: Session = Depends(get_db)
):
    """
    Get all invoices for a specific customer group.
    """
    from app.crud import get_invoices_by_customer_group
    
    invoices = get_invoices_by_customer_group(db, current_driver.user_id, group_id)
    
    if not invoices:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No invoices found for this customer group"
        )
    
    first_invoice = invoices[0]
    total_amount = sum(float(inv.amount) for inv in invoices)
    all_acknowledged = all(inv.status == "delivered" for inv in invoices)
    
    # Get route display
    route_display = None
    if first_invoice.route_number:
        route_display = f"Route {first_invoice.route_number}"
        if first_invoice.route_name:
            route_display += f": {first_invoice.route_name}"
    
    # Get branch info
    branch_name = ""  # Default to empty string instead of None
    if first_invoice.branch_id:
        branch_obj = db.query(Branch).filter(Branch.branch_id == first_invoice.branch_id).first()
        if branch_obj:
            branch_name = branch_obj.name
    
    # Convert invoices to schema
    invoice_responses = []
    for inv in invoices:
        invoice_responses.append(schemas.InvoiceInfo(
            id=str(inv.invoice_id),
            invoice_number=inv.n_inv_no,
            customer_name=inv.cust_name,
            amount=float(inv.amount),
            invoice_date=inv.invoice_date.isoformat() if inv.invoice_date else None,
            status=inv.status,
            branch=branch_name,
            created_date=inv.created_at.isoformat() if inv.created_at else "",
            is_acknowledged=(inv.status == "delivered"),
            route_number=inv.route_number,
            route_name=inv.route_name,
            route_display=route_display
        ))
    
    return schemas.CustomerGroupDetail(
        customer_visit_group=group_id,
        customer_name=first_invoice.cust_name,
        route_number=first_invoice.route_number,
        route_name=first_invoice.route_name,
        route_display=route_display,
        invoices=invoice_responses,
        total_amount=total_amount,
        invoice_count=len(invoices),
        all_acknowledged=all_acknowledged,
        branch=branch_name  # Will be empty string if no branch found
    )


@router.post("/acknowledge-group/{group_id}", response_model=schemas.AcknowledgeGroupResponse)
async def acknowledge_customer_group(
    group_id: str,
    signature: UploadFile = File(...),
    notes: Optional[str] = Form(None),
    current_driver: User = Depends(auth.get_current_driver_user),
    db: Session = Depends(get_db)
):
    """
    Acknowledge all invoices in a customer group with a single signature.
    Generates individual PDFs for each invoice with the same signature.
    """
    from app.crud import get_invoices_by_customer_group
    
    # Get all invoices in the group
    invoices = get_invoices_by_customer_group(db, current_driver.user_id, group_id)
    
    if not invoices:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No invoices found for this customer group"
        )
    
    # Save signature file
    signature_content = await signature.read()
    signature_filename = f"signature_{group_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.png"
    signature_path = os.path.join(settings.upload_folder, signature_filename)
    
    try:
        with open(signature_path, "wb") as f:
            f.write(signature_content)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save signature: {str(e)}"
        )
    
    # Process each invoice
    acknowledged_invoices = []
    generated_pdfs = []
    customer_name = invoices[0].cust_name
    
    for invoice in invoices:
        # Generate PDF filename
        pdf_filename = f"invoice_{invoice.invoice_id}_acknowledged.pdf"
        
        # Prepare data for HTML template
        signature_data_url = f"data:image/png;base64,{base64.b64encode(signature_content).decode('utf-8')}"
        
        # Get branch info
        branch_name = ""
        branch_city = ""
        if invoice.branch_id:
            branch_obj = db.query(Branch).filter(Branch.branch_id == invoice.branch_id).first()
            if branch_obj:
                branch_name = branch_obj.name
                branch_city = branch_obj.city if hasattr(branch_obj, 'city') else branch_name
        
        template_data = {
            "company_logo_url_or_data": "",
            "invoice_id": invoice.n_inv_no,
            "date": datetime.utcnow().strftime("%Y-%m-%d"),
            "customer_name": invoice.cust_name,
            "branch_address": f"{branch_name}, {branch_city}",
            "delivered_by_name": current_driver.name,
            "signature_data_url_or_path": signature_data_url,
            "signature_name_or_empty": notes or "",
            "company_name": "ZED WELL",
            "company_support_contact": "support@zedwell.com"
        }
        
        # Generate PDF using ReportLab
        from app import utils
        pdf_content = utils.generate_acknowledgement_pdf(template_data)
        
        # Save PDF to local directory
        pdf_path = os.path.join(settings.pdf_folder, pdf_filename)
        try:
            with open(pdf_path, 'wb') as f:
                f.write(pdf_content)
            generated_pdfs.append(pdf_filename)
        except Exception as e:
            print(f"Warning: Failed to save PDF for invoice {invoice.n_inv_no}: {str(e)}")
        
        # Update invoice
        invoice.pdf_path = pdf_filename
        invoice.status = "delivered"
        invoice.driver_signature = signature_filename
        invoice.driver_notes = notes
        invoice.acknowledged_at = datetime.utcnow()
        invoice.delivery_date = datetime.utcnow()
        
        acknowledged_invoices.append(invoice.n_inv_no)
    
    db.commit()
    
    return schemas.AcknowledgeGroupResponse(
        message=f"Successfully acknowledged {len(invoices)} invoices for {customer_name}",
        customer_name=customer_name,
        acknowledged_invoices=acknowledged_invoices,
        signature_saved=signature_filename,
        pdfs_generated=generated_pdfs
    )




@router.post("/location", response_model=schemas.LocationUpdateResponse)
async def update_driver_location(
    location: schemas.LocationUpdate,
    current_driver: User = Depends(auth.get_current_driver_user),
    db: Session = Depends(get_db)
):
    """Driver sends current GPS coordinates. Upserts one row per driver (no history bloat)."""
    from app.models import DriverLocation
    now = datetime.utcnow()
    existing = db.query(DriverLocation).filter(
        DriverLocation.driver_id == current_driver.user_id
    ).first()
    if existing:
        existing.latitude = location.latitude
        existing.longitude = location.longitude
        existing.accuracy = location.accuracy
        existing.updated_at = now
    else:
        db.add(DriverLocation(
            driver_id=current_driver.user_id,
            latitude=location.latitude,
            longitude=location.longitude,
            accuracy=location.accuracy,
            updated_at=now,
        ))
    db.commit()
    return schemas.LocationUpdateResponse(message="ok", updated_at=now.isoformat())
