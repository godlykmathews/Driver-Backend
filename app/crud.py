from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List, Optional
from datetime import datetime
import csv

from app import models, schemas, auth


# User CRUD operations
def get_user(db: Session, user_id: int) -> Optional[models.User]:
    return db.query(models.User).filter(models.User.id == user_id).first()


def get_user_by_username(db: Session, username: str) -> Optional[models.User]:
    return db.query(models.User).filter(models.User.username == username).first()


def get_user_by_email(db: Session, email: str) -> Optional[models.User]:
    return db.query(models.User).filter(models.User.email == email).first()


def get_users(db: Session, skip: int = 0, limit: int = 100) -> List[models.User]:
    return db.query(models.User).offset(skip).limit(limit).all()


def create_user(db: Session, user: schemas.UserCreate) -> models.User:
    hashed_password = auth.get_password_hash(user.password)
    db_user = models.User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password,
        role=user.role,
        is_active=True
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def update_user(db: Session, user_id: int, user_update: schemas.UserUpdate) -> Optional[models.User]:
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if db_user:
        update_data = user_update.dict(exclude_unset=True)
        if 'password' in update_data:
            update_data['hashed_password'] = auth.get_password_hash(update_data.pop('password'))
        
        for field, value in update_data.items():
            setattr(db_user, field, value)
        
        db.commit()
        db.refresh(db_user)
    return db_user


def delete_user(db: Session, user_id: int) -> bool:
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if db_user:
        db.delete(db_user)
        db.commit()
        return True
    return False


# Invoice CRUD operations
def get_invoice(db: Session, invoice_id: int) -> Optional[models.Invoice]:
    return db.query(models.Invoice).filter(models.Invoice.id == invoice_id).first()


def get_invoice_by_number(db: Session, invoice_number: str) -> Optional[models.Invoice]:
    return db.query(models.Invoice).filter(models.Invoice.invoice_number == invoice_number).first()


def get_invoices(db: Session, skip: int = 0, limit: int = 100) -> List[models.Invoice]:
    return db.query(models.Invoice).offset(skip).limit(limit).all()


def get_invoices_by_driver(db: Session, driver_id: int, skip: int = 0, limit: int = 100) -> List[models.Invoice]:
    return db.query(models.Invoice).filter(
        models.Invoice.assigned_driver_id == driver_id
    ).offset(skip).limit(limit).all()


def get_pending_invoices_by_driver(db: Session, driver_id: int) -> List[models.Invoice]:
    return db.query(models.Invoice).filter(
        and_(
            models.Invoice.assigned_driver_id == driver_id,
            models.Invoice.status == "pending"
        )
    ).all()


def create_invoice(db: Session, invoice: schemas.InvoiceCreate) -> models.Invoice:
    db_invoice = models.Invoice(**invoice.dict())
    db.add(db_invoice)
    db.commit()
    db.refresh(db_invoice)
    return db_invoice


def update_invoice(db: Session, invoice_id: int, invoice_update: schemas.InvoiceUpdate) -> Optional[models.Invoice]:
    db_invoice = db.query(models.Invoice).filter(models.Invoice.id == invoice_id).first()
    if db_invoice:
        update_data = invoice_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_invoice, field, value)
        
        db.commit()
        db.refresh(db_invoice)
    return db_invoice


def assign_driver_to_invoice(db: Session, invoice_id: int, driver_id: int) -> Optional[models.Invoice]:
    db_invoice = db.query(models.Invoice).filter(models.Invoice.id == invoice_id).first()
    if db_invoice:
        db_invoice.assigned_driver_id = driver_id
        db_invoice.status = "assigned"
        db.commit()
        db.refresh(db_invoice)
    return db_invoice


def submit_signature(db: Session, invoice_id: int, signature_data: str, driver_id: int) -> Optional[models.Invoice]:
    db_invoice = db.query(models.Invoice).filter(
        and_(
            models.Invoice.id == invoice_id,
            models.Invoice.assigned_driver_id == driver_id
        )
    ).first()
    
    if db_invoice:
        db_invoice.signature = signature_data
        db_invoice.status = "delivered"
        db_invoice.delivered_at = datetime.utcnow()
        db.commit()
        db.refresh(db_invoice)
    return db_invoice


def delete_invoice(db: Session, invoice_id: int) -> bool:
    db_invoice = db.query(models.Invoice).filter(models.Invoice.id == invoice_id).first()
    if db_invoice:
        db.delete(db_invoice)
        db.commit()
        return True
    return False


# Bulk operations
def create_invoices_from_csv(db: Session, csv_data: str) -> List[models.Invoice]:
    """
    Create multiple invoices from CSV data
    Expected CSV columns: invoice_number, customer_name, customer_address, customer_phone, amount, items
    """
    try:
        # Parse CSV data
        import io
        
        csv_file = io.StringIO(csv_data)
        reader = csv.DictReader(csv_file)
        
        invoices = []
        for row in reader:
            # Check if invoice already exists
            existing = get_invoice_by_number(db, row['invoice_number'])
            if not existing:
                invoice_data = {
                    'invoice_number': row['invoice_number'],
                    'customer_name': row['customer_name'],
                    'customer_address': row['customer_address'],
                    'customer_phone': row.get('customer_phone', ''),
                    'amount': float(row['amount']),
                    'items': row.get('items', ''),
                    'status': 'pending'
                }
                
                db_invoice = models.Invoice(**invoice_data)
                db.add(db_invoice)
                invoices.append(db_invoice)
        
        db.commit()
        for invoice in invoices:
            db.refresh(invoice)
        
        return invoices
    
    except Exception as e:
        db.rollback()
        raise e


def get_driver_statistics(db: Session, driver_id: int) -> dict:
    """Get statistics for a specific driver"""
    total_assigned = db.query(models.Invoice).filter(
        models.Invoice.assigned_driver_id == driver_id
    ).count()
    
    delivered = db.query(models.Invoice).filter(
        and_(
            models.Invoice.assigned_driver_id == driver_id,
            models.Invoice.status == "delivered"
        )
    ).count()
    
    pending = db.query(models.Invoice).filter(
        and_(
            models.Invoice.assigned_driver_id == driver_id,
            models.Invoice.status.in_(["pending", "assigned"])
        )
    ).count()
    
    return {
        "total_assigned": total_assigned,
        "delivered": delivered,
        "pending": pending,
        "delivery_rate": (delivered / total_assigned * 100) if total_assigned > 0 else 0
    }


def get_admin_statistics(db: Session) -> dict:
    """Get overall statistics for admin dashboard"""
    total_invoices = db.query(models.Invoice).count()
    total_users = db.query(models.User).count()
    total_drivers = db.query(models.User).filter(models.User.role == "driver").count()
    
    pending_invoices = db.query(models.Invoice).filter(
        models.Invoice.status.in_(["pending", "assigned"])
    ).count()
    
    delivered_invoices = db.query(models.Invoice).filter(
        models.Invoice.status == "delivered"
    ).count()
    
    return {
        "total_invoices": total_invoices,
        "total_users": total_users,
        "total_drivers": total_drivers,
        "pending_invoices": pending_invoices,
        "delivered_invoices": delivered_invoices,
        "delivery_rate": (delivered_invoices / total_invoices * 100) if total_invoices > 0 else 0
    }


# Grouped Invoice Functions
def generate_customer_visit_group(route_number: int, customer_name: str, route_date: datetime) -> str:
    """Generate a unique customer visit group identifier"""
    date_str = route_date.strftime("%Y-%m-%d") if route_date else datetime.now().strftime("%Y-%m-%d")
    # Sanitize customer name for use in group ID
    safe_customer_name = customer_name.replace(" ", "_").replace("/", "-")
    return f"{route_number}-{safe_customer_name}-{date_str}"


def update_customer_visit_groups(db: Session, driver_id: int) -> int:
    """Update customer_visit_group for all invoices that don't have one"""
    invoices = db.query(models.Invoice).filter(
        and_(
            models.Invoice.assigned_driver_id == driver_id,
            models.Invoice.customer_visit_group == None
        )
    ).all()
    
    updated_count = 0
    for invoice in invoices:
        if invoice.route_number and invoice.cust_name:
            group_id = generate_customer_visit_group(
                invoice.route_number,
                invoice.cust_name,
                invoice.route_date or invoice.invoice_date
            )
            invoice.customer_visit_group = group_id
            updated_count += 1
    
    if updated_count > 0:
        db.commit()
    
    return updated_count


def get_driver_routes(db: Session, driver_id: int, created_date: Optional[str] = None) -> List[dict]:
    """Get all unique routes assigned to a driver"""
    from sqlalchemy import func
    
    query = db.query(
        models.Invoice.route_number,
        models.Invoice.route_name
    ).filter(
        models.Invoice.assigned_driver_id == driver_id
    ).distinct()
    
    # Filter by created_date if provided (YYYY-MM-DD format) - when invoice was entered into system
    if created_date:
        try:
            created_dt = datetime.strptime(created_date, "%Y-%m-%d").date()
            query = query.filter(func.date(models.Invoice.created_at) == created_dt)
        except (ValueError, TypeError):
            pass  # Invalid date format, skip filter
    
    routes = query.filter(
        models.Invoice.route_number.isnot(None)
    ).order_by(models.Invoice.route_number).all()
    
    return [
        {
            "route_number": route.route_number,
            "route_name": route.route_name or f"Route {route.route_number}"
        }
        for route in routes
    ]


def get_grouped_invoices_for_driver(
    db: Session, 
    driver_id: int,
    route_number: Optional[int] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    created_date: Optional[str] = None
) -> List[dict]:
    """Get deduplicated customer groups for driver's invoices"""
    from sqlalchemy import or_, func
    
    query = db.query(models.Invoice).filter(models.Invoice.assigned_driver_id == driver_id)
    
    # Apply filters
    if route_number:
        query = query.filter(models.Invoice.route_number == route_number)
    
    if status and status != "all":
        query = query.filter(models.Invoice.status == status)
    
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                models.Invoice.cust_name.ilike(search_pattern),
                models.Invoice.n_inv_no.ilike(search_pattern)
            )
        )
    
    # Filter by created_date (YYYY-MM-DD format) - when invoice was entered into system
    if created_date:
        try:
            created_dt = datetime.strptime(created_date, "%Y-%m-%d").date()
            query = query.filter(func.date(models.Invoice.created_at) == created_dt)
        except (ValueError, TypeError):
            pass  # Invalid date format, skip filter
    
    # Get all invoices ordered by invoice_id to maintain CSV order
    invoices = query.order_by(models.Invoice.invoice_id).all()
    
    # Group by customer_visit_group
    groups_dict = {}
    sequence_counter = 0
    
    for invoice in invoices:
        # Generate group key if not exists
        if not invoice.customer_visit_group and invoice.route_number:
            group_key = generate_customer_visit_group(
                invoice.route_number,
                invoice.cust_name,
                invoice.route_date or invoice.invoice_date
            )
            invoice.customer_visit_group = group_key
        else:
            group_key = invoice.customer_visit_group
        
        if not group_key:
            continue
            
        if group_key not in groups_dict:
            sequence_counter += 1
            groups_dict[group_key] = {
                "customer_visit_group": group_key,
                "customer_name": invoice.cust_name,
                "route_number": invoice.route_number,
                "route_name": invoice.route_name,
                "invoice_count": 0,
                "total_amount": 0.0,
                "status": invoice.status,
                "first_invoice_id": invoice.invoice_id,
                "invoice_numbers": [],
                "sequence_order": sequence_counter,
                "all_delivered": True,
                "any_delivered": False
            }
        
        groups_dict[group_key]["invoice_count"] += 1
        groups_dict[group_key]["total_amount"] += float(invoice.amount)
        groups_dict[group_key]["invoice_numbers"].append(invoice.n_inv_no)
        
        # Update status tracking
        if invoice.status == "delivered":
            groups_dict[group_key]["any_delivered"] = True
        else:
            groups_dict[group_key]["all_delivered"] = False
    
    # Commit any group_id updates
    db.commit()
    
    # Determine group status
    for group in groups_dict.values():
        if group["all_delivered"]:
            group["status"] = "delivered"
        else:
            group["status"] = "pending"
    
    # Convert to list and sort by sequence order (maintaining CSV order)
    groups_list = sorted(groups_dict.values(), key=lambda x: x["sequence_order"])
    
    return groups_list


def get_invoices_by_customer_group(
    db: Session,
    driver_id: int,
    customer_visit_group: str
) -> List[models.Invoice]:
    """Get all invoices for a specific customer visit group"""
    return db.query(models.Invoice).filter(
        and_(
            models.Invoice.assigned_driver_id == driver_id,
            models.Invoice.customer_visit_group == customer_visit_group
        )
    ).order_by(models.Invoice.invoice_id).all()