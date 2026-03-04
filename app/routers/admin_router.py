from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Response
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from app import schemas, crud, auth, utils
from app.database import get_db
from app.models import User, Invoice, Branch, DriverBranch, UserRole
from app.config import settings
from io import BytesIO
from datetime import datetime, timedelta
import random
import string
import csv
import io
import zipfile
import os

router = APIRouter()


@router.get("/drivers", response_model=schemas.DriversResponse)
async def get_drivers(
    branch: Optional[str] = None,
    page: int = 1,
    per_page: int = 20,
    current_user: User = Depends(auth.get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get list of drivers with optional branch filtering."""
    query = db.query(User).filter(User.role == UserRole.driver)
    
    if branch:
        # Filter by branch through DriverBranch relationship
        branch_obj = db.query(Branch).filter(Branch.name == branch).first()
        if not branch_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Branch '{branch}' not found"
            )
        
        driver_ids = db.query(DriverBranch.driver_id).filter(
            DriverBranch.branch_id == branch_obj.branch_id
        ).subquery()
        
        query = query.filter(User.user_id.in_(driver_ids))
    
    total = query.count()
    drivers = query.offset((page - 1) * per_page).limit(per_page).all()
    
    driver_list = []
    for driver in drivers:
        # Get driver's branches
        driver_branches = db.query(DriverBranch).join(Branch).filter(
            DriverBranch.driver_id == driver.user_id
        ).all()
        branches = [
            db.query(Branch).filter(Branch.branch_id == db_branch.branch_id).first().name
            for db_branch in driver_branches
        ]
        
        driver_info = schemas.DriverInfo(
            id=str(driver.user_id),
            username=driver.email,
            driver_name=driver.name,
            branches=branches,
            role=driver.role.value,
            isActive=True,  # Assuming active
            isTemporary=getattr(driver, 'is_temporary', False),
            created_at=driver.created_at.isoformat() if driver.created_at else "",
            temp_password=driver.temp_password if getattr(driver, 'is_temporary', False) else None
        )
        driver_list.append(driver_info)
    
    return schemas.DriversResponse(
        drivers=driver_list,
        pagination=schemas.PaginationInfo(
            current_page=page,
            total_pages=(total + per_page - 1) // per_page,
            total_count=total,
            per_page=per_page
        )
    )



@router.post("/drivers", response_model=schemas.CreateDriverResponse)
async def create_driver(
    driver_data: schemas.CreateDriverRequest,
    current_user: User = Depends(auth.get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Create a new driver."""
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == driver_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Validate branches exist and collect branch names
    branch_names = []
    for branch_id in driver_data.branch_ids:  # Changed from branch_name to branch_id
        branch = db.query(Branch).filter(Branch.branch_id == branch_id).first()  # Changed from name to branch_id
        if not branch:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Branch with ID '{branch_id}' not found"  # Updated error message
            )
        branch_names.append(branch.name)  # Collect branch names for response
    
    # Create driver user
    hashed_password = auth.get_password_hash(driver_data.password)
    new_driver = User(
        name=driver_data.driver_name,
        email=driver_data.email, 
        password_hash=hashed_password,
        role=UserRole.driver,
        branch_id=None,
        is_temporary=driver_data.isTemporary
    )
    
    db.add(new_driver)
    db.commit()
    db.refresh(new_driver)
    
    # Assign driver to branches
    for branch_id in driver_data.branch_ids: 
        driver_branch = DriverBranch(
            driver_id=new_driver.user_id,
            branch_id=branch_id  
        )
        db.add(driver_branch)
    
    db.commit()
    
    return schemas.CreateDriverResponse(
        message="Driver created successfully",
        driver=schemas.DriverInfo(
            id=str(new_driver.user_id),
            driver_name=new_driver.name,
            username=new_driver.email,
            branches=branch_names,  
            isActive=True,
            isTemporary=new_driver.is_temporary,
            created_at=new_driver.created_at.isoformat() if new_driver.created_at else ""
        )
    )



@router.post("/drivers/temporary", response_model=schemas.CreateTempDriverResponse)
async def create_temporary_driver(
    temp_driver_data: schemas.CreateTempDriverRequest,
    current_user: User = Depends(auth.get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Create a temporary driver."""
    # Validate branches exist
    for branch_id in temp_driver_data.branch_ids:
        branch = db.query(Branch).filter(Branch.branch_id == branch_id).first()
        if not branch:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Branch with ID '{branch_id}' not found"
            )
    
    # Generate random email and password for temporary driver
    random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    temp_email = f"temp_{random_suffix}@temp.com"
    temp_password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
    
    # Create temporary driver user
    hashed_password = auth.get_password_hash(temp_password)
    new_driver = User(
        name=f"Temporary Driver {random_suffix}",
        email=temp_email,
        password_hash=hashed_password,
        temp_password=temp_password, 
        role=UserRole.driver,
        branch_id=None,
        is_temporary=True
    )
    
    db.add(new_driver)
    db.commit()
    db.refresh(new_driver)
    
    branches=[]
    # Assign driver to branches
    for branch_id in temp_driver_data.branch_ids:
        branch = db.query(Branch).filter(Branch.branch_id == branch_id).first()
        driver_branch = DriverBranch(
            driver_id=new_driver.user_id,
            branch_id=branch.branch_id
        )
        db.add(driver_branch)
        branches.append(branch.name)
    
    db.commit()
    
    return schemas.CreateTempDriverResponse(
        message="Temporary driver created successfully",
        driver=schemas.DriverInfo(
            id=str(new_driver.user_id),
            driver_name=new_driver.name,
            username=new_driver.email,
            branches=branches,
            isActive=True,
            isTemporary=True,
            created_at=new_driver.created_at.isoformat() if new_driver.created_at else ""
        ),
        credentials=schemas.TempDriverCredentials(
            username=temp_email,
            password=temp_password
        )
    )


@router.post("/invoices/upload-csv", response_model=schemas.UploadResponse)
async def upload_csv(
    driver_id: str,
    route_name: Optional[str] = None,  # Optional route name parameter
    file: UploadFile = File(...),
    current_user: User = Depends(auth.get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Upload CSV file with invoice data and assign to a route."""
    # Check if admin has a branch assigned
    if not current_user.branch_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin must be assigned to a branch to upload CSV files"
        )
    
    # Validate file type
    if not file.filename.lower().endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a CSV file"
        )
    
    # driver is mandatory
    if not driver_id or not driver_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Driver parameter is required"
        )

    driver_obj = db.query(User).filter(
        and_(User.user_id == driver_id, User.role == UserRole.driver)
    ).first()
    if not driver_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Driver '{driver_id}' not found"
        )
    driver_id = driver_obj.user_id
    
    # Validate and clean route name
    if route_name:
        route_name = utils.validate_route_data(route_name)
    
    try:
        # Read file content
        contents = await file.read()
        # Decode bytes to string
        decoded_content = contents.decode('utf-8-sig')
        csv_file = io.StringIO(decoded_content)
        reader = csv.DictReader(csv_file)
        
        # Check required columns
        required_columns = {"cust_name", "amount", "n_inv_no"}
        if not reader.fieldnames or not required_columns.issubset(reader.fieldnames):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"CSV must contain columns: {required_columns}"
            )
        
        # Get next route number for this driver today
        from datetime import date
        today = date.today()
        route_number = utils.get_next_route_number(db, driver_id, today)
        route_datetime = datetime.combine(today, datetime.min.time())
        
        # Process invoices
        uploaded_count = 0
        skipped_count = 0
        
        for row in reader:
            # Check if invoice already exists
            existing_invoice = db.query(Invoice).filter(
                Invoice.n_inv_no == row['n_inv_no']
            ).first()
            
            if existing_invoice:
                skipped_count += 1
                continue
            
            # Parse invoice date
            invoice_date = None
            if 'd_inv_date' in row and row['d_inv_date'] and row['d_inv_date'].strip():
                try:
                    # Parse DD/MM/YYYY format
                    invoice_date = datetime.strptime(str(row['d_inv_date']), "%d/%m/%Y")
                except ValueError:
                    # If parsing fails, try other formats or set to None
                    pass
            
            # Generate customer visit group for grouping
            from app.crud import generate_customer_visit_group
            customer_visit_group = generate_customer_visit_group(
                route_number,
                row['cust_name'],
                route_datetime
            )
            
            # Create new invoice with route information
            invoice = Invoice(
                cust_name=row['cust_name'],
                amount=float(row['amount']),
                n_inv_no=row['n_inv_no'],
                invoice_date=invoice_date,
                branch_id=current_user.branch_id,
                assigned_driver_id=driver_id,
                status="pending",
                route_number=route_number,
                route_name=route_name,
                route_date=route_datetime,
                customer_visit_group=customer_visit_group,  # Add customer visit group
                created_at=datetime.utcnow()
            )
            
            db.add(invoice)
            uploaded_count += 1
        
        db.commit()
        
        # Create route display message
        route_display = utils.format_route_display(route_number, route_name)
        
        return schemas.UploadResponse(
            message=f"Successfully uploaded {uploaded_count} invoices to {route_display}. {skipped_count} duplicates skipped.",
            uploaded_count=uploaded_count,
            skipped_count=skipped_count
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing CSV file: {str(e)}"
        )


@router.get("/branches", response_model=schemas.BranchesResponse)
async def get_branches(
    page: int = 1,
    per_page: int = 20,
    current_user: User = Depends(auth.get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get list of all branches."""
    total = db.query(Branch).count()
    branches = db.query(Branch).offset((page - 1) * per_page).limit(per_page).all()
    
    branch_list = []
    for branch in branches:
        branch_info = schemas.BranchInfo(
            id=str(branch.branch_id),
            name=branch.name,
            city=branch.city,
            phone='',  # Default empty if not available
            email='',  # Default empty if not available
            created_at=branch.created_at.isoformat() if branch.created_at else '',
            is_active=True  # Assuming active
        )
        branch_list.append(branch_info)
    
    return schemas.BranchesResponse(
        branches=branch_list,
        pagination=schemas.PaginationInfo(
            current_page=page,
            total_pages=(total + per_page - 1) // per_page,
            total_count=total,
            per_page=per_page
        )
    )


@router.post("/branches", response_model=schemas.BranchResponse)
async def create_branch(
    branch_data: schemas.CreateBranchRequest,
    current_user: User = Depends(auth.get_current_super_admin),
    db: Session = Depends(get_db)
):
    """Create a new branch (Super Admin only)."""
    # Check if branch already exists
    existing_branch = db.query(Branch).filter(Branch.email == branch_data.email).first()
    if existing_branch:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Branch already exists"
        )
    
    # Create new branch
    new_branch = Branch(
        name=branch_data.name,
        email=branch_data.email,
        phone=branch_data.phone,
        city=getattr(branch_data, 'city', '') or getattr(branch_data, 'location', ''),
        created_at=datetime.utcnow()
    )
    
    db.add(new_branch)
    db.commit()
    db.refresh(new_branch)
    
    return new_branch


@router.get("/branches/{branch_name}/details", response_model=schemas.BranchDetailsResponse)
async def get_branch_details(
    branch_name: str,
    current_user: User = Depends(auth.get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get detailed information about a specific branch."""
    branch = db.query(Branch).filter(Branch.name == branch_name).first()
    if not branch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Branch '{branch_name}' not found"
        )
    
    # Get admins
    admins = db.query(User).filter(
        and_(User.branch_id == branch.branch_id, User.role == UserRole.admin)
    ).all()
    
    admin_list = [
        schemas.AdminInfo(
            id=str(admin.user_id),
            username=admin.email,
            admin_name=admin.name,
            assigned_branches=[branch_name],
            role=admin.role.value
        )
        for admin in admins
    ]
    
    # Get drivers
    driver_branches = db.query(DriverBranch).filter(
        DriverBranch.branch_id == branch.branch_id
    ).all()
    
    driver_list = []
    for db_branch in driver_branches:
        driver = db.query(User).filter(User.user_id == db_branch.driver_id).first()
        if driver:
            # Get all branches for this driver
            all_driver_branches = db.query(DriverBranch).join(Branch).filter(
                DriverBranch.driver_id == driver.user_id
            ).all()
            all_branches = [
                db.query(Branch).filter(Branch.branch_id == db_branch.branch_id).first().name
                for db_branch in all_driver_branches
            ]
            
            driver_info = schemas.DriverInfo(
                id=str(driver.user_id),
                username=driver.email,
                driver_name=driver.name,
                branches=all_branches,
                role=driver.role.value,
                isActive=True,
                isTemporary=driver.is_temporary,
                created_at=driver.created_at.isoformat() if driver.created_at else ''
            )
            driver_list.append(driver_info)
    
    return schemas.BranchDetailsResponse(
        branch=schemas.BranchInfo(
            id=str(branch.branch_id),
            name=branch.name,
            city=branch.city,
            phone='',  # Default empty if not available
            email='',  # Default empty if not available
            created_at=branch.created_at.isoformat() if branch.created_at else '',
            is_active=True
        ),
        users=schemas.BranchUsers(
            admins=admin_list,
            drivers=driver_list,
            total_users=len(admin_list) + len(driver_list)
        )
    )


@router.get("/admins", response_model=schemas.AdminsResponse)
async def get_admins(
    page: int = 1,
    per_page: int = 20,
    current_user: User = Depends(auth.get_current_super_admin),
    db: Session = Depends(get_db)
):
    """Get list of all admins (Super Admin only)."""
    query = db.query(User).filter(User.role == UserRole.admin)
    total = query.count()
    admins = query.offset((page - 1) * per_page).limit(per_page).all()
    
    admin_list = []
    for admin in admins:
        branch_name = ""
        if admin.branch_id:
            branch = db.query(Branch).filter(Branch.branch_id == admin.branch_id).first()
            if branch:
                branch_name = branch.name
        
        admin_info = schemas.AdminFullInfo(
            id=str(admin.user_id),
            name=admin.name,
            email=admin.email,
            branch=f"{branch_name},{branch.city}",
            role=admin.role.value,
            created_at=admin.created_at.isoformat() if admin.created_at else '',
            is_active=True
        )
        admin_list.append(admin_info)
    
    return schemas.AdminsResponse(
        admins=admin_list,
        pagination=schemas.PaginationInfo(
            current_page=page,
            total_pages=(total + per_page - 1) // per_page,
            total_count=total,
            per_page=per_page
        )
    )


@router.post("/admins", response_model=schemas.CreateAdminResponse)
async def create_admin(
    admin_data: schemas.CreateAdminRequest,
    current_user: User = Depends(auth.get_current_super_admin),
    db: Session = Depends(get_db)
):
    """Create a new admin user (Super Admin only)."""
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == admin_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Validate branch exists
    branch = db.query(Branch).filter(Branch.branch_id == admin_data.branch_id).first()
    if not branch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Branch with ID '{admin_data.branch_id}' not found"
        )
    
    # Create admin user
    hashed_password = auth.get_password_hash(admin_data.password)
    new_admin = User(
        name=admin_data.name,
        email=admin_data.email,
        password_hash=hashed_password,
        role=UserRole.admin,
        branch_id=branch.branch_id
    )
    
    db.add(new_admin)
    db.commit()
    db.refresh(new_admin)
    
    return schemas.CreateAdminResponse(
        message="Admin created successfully",
        admin=schemas.AdminFullInfo(
            id=str(new_admin.user_id),
            name=new_admin.name,
            email=new_admin.email,
            branch=f"{branch.name},{branch.city}",
            role=new_admin.role.value,
            created_at=new_admin.created_at.isoformat() if new_admin.created_at else '',
            is_active=True
        )
    )


@router.put("/admins/{admin_id}", response_model=schemas.AdminFullInfo)
async def update_admin(
    admin_id: int,
    admin_data: schemas.UpdateAdminRequest,
    current_user: User = Depends(auth.get_current_super_admin),
    db: Session = Depends(get_db)
):
    """Update an admin user (Super Admin only)."""
    # Find the admin user
    admin = db.query(User).filter(
        and_(User.user_id == admin_id, User.role == UserRole.admin)
    ).first()
    
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin not found"
        )
    
    # Check if email is being changed and if it's already taken
    if admin_data.email and admin_data.email != admin.email:
        existing_user = db.query(User).filter(User.email == admin_data.email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
    
    # Validate branch exists if branch_id is provided
    branch_name_city = ""
    if admin_data.branch_id:
        branch = db.query(Branch).filter(Branch.branch_id == admin_data.branch_id).first()
        if not branch:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Branch with ID '{admin_data.branch_id}' not found"
            )
        branch_name_city = f"{branch.name},{branch.city}"
        admin.branch_id = branch.branch_id
    
    # Update admin fields
    if admin_data.name is not None:
        admin.name = admin_data.name
    if admin_data.email is not None:
        admin.email = admin_data.email
    if admin_data.branch_id is not None:
        admin.branch_id = admin_data.branch_id
    
    admin.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(admin)
    
    # Get current branch info
    if not branch_name_city and admin.branch_id:
        branch = db.query(Branch).filter(Branch.branch_id == admin.branch_id).first()
        if branch:
            branch_name_city = f"{branch.name},{branch.city}"
    
    return schemas.AdminFullInfo(
        id=str(admin.user_id),
        name=admin.name,
        email=admin.email,
        branch=branch_name_city,
        role=admin.role.value,
        created_at=admin.created_at.isoformat() if admin.created_at else '',
        last_login=admin.updated_at.isoformat() if admin.updated_at else '',
        is_active=True
    )


@router.put("/drivers/{driver_id}", response_model=schemas.DriverInfo)
async def update_driver(
    driver_id: int,
    driver_data: schemas.UpdateDriverRequest,
    current_user: User = Depends(auth.get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Update a driver user."""
    # Find the driver user
    driver = db.query(User).filter(
        and_(User.user_id == driver_id, User.role == UserRole.driver)
    ).first()
    
    if not driver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Driver not found"
        )
    
    # Check if email is being changed and if it's already taken
    if driver_data.email and driver_data.email != driver.email:
        existing_user = db.query(User).filter(User.email == driver_data.email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
    
    # Validate branches exist if branch_ids is provided
    branch_names = []
    if driver_data.branch_ids is not None:
        for branch_id in driver_data.branch_ids:
            branch = db.query(Branch).filter(Branch.branch_id == branch_id).first()
            if not branch:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Branch with ID '{branch_id}' not found"
                )
            branch_names.append(branch.name)
        
        # Remove existing driver-branch associations
        db.query(DriverBranch).filter(DriverBranch.driver_id == driver_id).delete()
        
        # Add new driver-branch associations
        for branch_id in driver_data.branch_ids:
            driver_branch = DriverBranch(
                driver_id=driver_id,
                branch_id=branch_id
            )
            db.add(driver_branch)
    
    # Update driver fields
    if driver_data.driver_name is not None:
        driver.name = driver_data.driver_name
    if driver_data.email is not None:
        driver.email = driver_data.email
    
    driver.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(driver)
    
    # Get current branch names
    if not branch_names:
        driver_branches = db.query(DriverBranch).join(Branch).filter(
            DriverBranch.driver_id == driver_id
        ).all()
        branch_names = [
            db.query(Branch).filter(Branch.branch_id == db_branch.branch_id).first().name
            for db_branch in driver_branches
        ]
    
    return schemas.DriverInfo(
        id=str(driver.user_id),
        username=driver.email,
        driver_name=driver.name,
        branches=branch_names,
        role=driver.role.value,
        isActive=True,
        isTemporary=getattr(driver, 'is_temporary', False),
        created_at=driver.created_at.isoformat() if driver.created_at else '',
        last_login=driver.updated_at.isoformat() if driver.updated_at else ''
    )


@router.delete("/drivers/{driver_id}")
async def delete_driver(
    driver_id: int,
    current_user: User = Depends(auth.get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Delete a driver user (both permanent and temporary drivers)."""
    # Find the driver user
    driver = db.query(User).filter(
        and_(User.user_id == driver_id, User.role == UserRole.driver)
    ).first()
    
    if not driver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Driver not found"
        )
    
    try:
        # Delete driver-branch associations first
        db.query(DriverBranch).filter(DriverBranch.driver_id == driver_id).delete()
        
        # Delete the driver user
        db.delete(driver)
        db.commit()
        
        driver_type = "temporary" if driver.is_temporary else "permanent"
        return {
            "message": f"{driver_type.capitalize()} driver {driver.name} (ID: {driver_id}) has been successfully deleted",
            "driver_id": driver_id,
            "driver_name": driver.name,
            "driver_type": driver_type
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting driver: {str(e)}"
        )


@router.delete("/admins/{admin_id}")
async def delete_admin(
    admin_id: int,
    current_user: User = Depends(auth.get_current_super_admin),
    db: Session = Depends(get_db)
):
    """Delete an admin user (super admin only)."""
    # Find the admin user
    admin = db.query(User).filter(
        and_(User.user_id == admin_id, User.role == UserRole.admin)
    ).first()
    
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin not found"
        )
    
    try:
        # Delete the admin user
        db.delete(admin)
        db.commit()
        
        return {
            "message": f"Admin {admin.name} (ID: {admin_id}) has been successfully deleted",
            "admin_id": admin_id,
            "admin_name": admin.name
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting admin: {str(e)}"
        )


@router.post("/files/upload", response_model=schemas.FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    file_type: str = "general",
    current_user: User = Depends(auth.get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Upload a file with type-based handling."""
    # Validate file
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file provided"
        )
    
    # Handle different file types
    if file_type == "csv" and file.filename.endswith('.csv'):
        # Process as CSV
        try:
            contents = await file.read()
            decoded_content = contents.decode('utf-8-sig')
            csv_file = io.StringIO(decoded_content)
            reader = csv.reader(csv_file)
            rows = list(reader)
            # Assuming first row is header, count data rows
            row_count = max(0, len(rows) - 1) if rows else 0
            
            return schemas.FileUploadResponse(
                message=f"CSV file processed successfully. Found {row_count} rows.",
                file_type="csv",
                file_size=len(contents),
                rows_processed=row_count
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error processing CSV file: {str(e)}"
            )
    
    else:
        # Handle as general file
        contents = await file.read()
        
        return schemas.FileUploadResponse(
            message=f"File '{file.filename}' uploaded successfully.",
            file_type=file_type,
            file_size=len(contents),
            rows_processed=0
        )


@router.get("/routes", response_model=schemas.RoutesResponse)
async def get_routes(
    driver_id: Optional[int] = None,
    route_date: Optional[str] = None,  # YYYY-MM-DD format
    page: int = 1,
    per_page: int = 20,
    current_user: User = Depends(auth.get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get routes with filtering and pagination."""
    # Base query to get distinct routes
    query = db.query(
        Invoice.assigned_driver_id,
        Invoice.route_number,
        Invoice.route_name,
        Invoice.route_date,
        func.count(Invoice.invoice_id).label('invoice_count')
    ).filter(
        Invoice.route_number.isnot(None)
    ).group_by(
        Invoice.assigned_driver_id,
        Invoice.route_number,
        Invoice.route_name,
        Invoice.route_date
    )
    
    # Role-based filtering
    if current_user.role.value == "admin":
        # Regular admin can only see their own branch routes
        if not current_user.branch_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin must be assigned to a branch"
            )
        query = query.filter(Invoice.branch_id == current_user.branch_id)
    
    # Filter by driver
    if driver_id is not None:
        driver_obj = db.query(User).filter(
            and_(User.user_id == driver_id, User.role == UserRole.driver)
        ).first()
        if not driver_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Driver with ID {driver_id} not found"
            )
        query = query.filter(Invoice.assigned_driver_id == driver_id)
    
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
    
    # Get total count
    total = query.count()
    
    # Apply pagination and ordering
    routes = query.order_by(
        Invoice.route_date.desc(),
        Invoice.assigned_driver_id,
        Invoice.route_number
    ).offset((page - 1) * per_page).limit(per_page).all()
    
    # Convert to response format
    route_list = []
    for route in routes:
        # Get driver name
        driver_obj = db.query(User).filter(User.user_id == route.assigned_driver_id).first()
        driver_name = driver_obj.name if driver_obj else "Unknown Driver"
        
        # Format route display with date for better identification
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
            current_page=page,
            total_pages=(total + per_page - 1) // per_page,
            total_count=total,
            per_page=per_page
        )
    )


@router.post("/bulk-download-pdfs")
async def bulk_download_pdfs(
    request: schemas.BulkDownloadRequest,
    current_user: User = Depends(auth.get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Download multiple PDFs as a ZIP file. Includes available PDFs and a text file listing missing ones."""
    
    if not request.invoice_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No invoice IDs provided"
        )
    
    if len(request.invoice_ids) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 100 PDFs can be downloaded at once"
        )
    
    # Get all requested invoices
    invoices = db.query(Invoice).filter(Invoice.invoice_id.in_(request.invoice_ids)).all()
    
    # Create ZIP file in memory
    zip_buffer = BytesIO()
    
    available_pdfs = []
    missing_pdfs = []
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for invoice_id in request.invoice_ids:
            invoice = next((inv for inv in invoices if inv.invoice_id == invoice_id), None)
            
            if not invoice:
                missing_pdfs.append(f"Invoice ID {invoice_id}: Invoice not found in database")
                continue
            
            if invoice.status != "acknowledged":
                missing_pdfs.append(f"Invoice ID {invoice_id}: Invoice not acknowledged (status: {invoice.status})")
                continue
            
            if not invoice.pdf_path:
                missing_pdfs.append(f"Invoice ID {invoice_id}: PDF file not found")
                continue
            
            try:
                # Read PDF from local storage
                pdf_path = os.path.join(settings.pdf_folder, invoice.pdf_path)
                if not os.path.exists(pdf_path):
                    missing_pdfs.append(f"Invoice ID {invoice_id}: PDF file not found in local storage")
                    continue
                
                with open(pdf_path, 'rb') as f:
                    pdf_content = f.read()
                
                # Add PDF content to ZIP
                pdf_filename = f"invoice_{invoice.n_inv_no}_acknowledged.pdf"
                zip_file.writestr(pdf_filename, pdf_content)
                available_pdfs.append(pdf_filename)
                
            except Exception as e:
                missing_pdfs.append(f"Invoice ID {invoice_id}: Error reading PDF - {str(e)}")
        
        # Add missing PDFs report if any
        if missing_pdfs:
            missing_report = "Bulk PDF Download Report\n"
            missing_report += "=" * 50 + "\n\n"
            missing_report += f"Total PDFs requested: {len(request.invoice_ids)}\n"
            missing_report += f"Available PDFs: {len(available_pdfs)}\n"
            missing_report += f"Missing PDFs: {len(missing_pdfs)}\n\n"
            
            if available_pdfs:
                missing_report += "Available PDFs:\n"
                for pdf in available_pdfs:
                    missing_report += f"  ✓ {pdf}\n"
                missing_report += "\n"
            
            missing_report += "Missing PDFs:\n"
            for missing in missing_pdfs:
                missing_report += f"  ✗ {missing}\n"
            
            missing_report += "\n" + "=" * 50 + "\n"
            missing_report += "Generated on: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "\n"
            missing_report += f"Requested by: {current_user.name} ({current_user.email})"
            
            zip_file.writestr("missing_pdfs_report.txt", missing_report)
    
    zip_buffer.seek(0)
    zip_content = zip_buffer.getvalue()
    
    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"bulk_pdf_download_{timestamp}.zip"
    
    return Response(
        content=zip_content,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/debug-routes")
async def debug_routes(
    current_user: User = Depends(auth.get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Debug endpoint to see available routes and invoices."""
    
    invoices = db.query(Invoice).all()
    
    route_info = []
    for invoice in invoices[:10]:  # Show first 10 invoices
        route_info.append({
            "invoice_id": invoice.invoice_id,
            "route_number": invoice.route_number,
            "route_name": invoice.route_name,
            "driver_id": invoice.assigned_driver_id,
            "driver_name": invoice.assigned_driver.name if invoice.assigned_driver else None,
            "invoice_date": invoice.invoice_date.strftime("%Y-%m-%d") if invoice.invoice_date else None,
            "cust_name": invoice.cust_name
        })
    
    return {
        "total_invoices": len(invoices),
        "sample_invoices": route_info,
        "unique_routes": list(set([f"Route {inv.route_number}" for inv in invoices if inv.route_number])),
        "unique_route_names": list(set([inv.route_name for inv in invoices if inv.route_name]))
    }


@router.post("/route-wise-pdf")
async def generate_route_wise_pdf(
    request: schemas.RouteWisePDFRequest,
    current_user: User = Depends(auth.get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Generate a single PDF with tabular view of all invoices in a route."""
    
    print(f"DEBUG: Route PDF request: {request}")  # Debug logging
    
    # Build query - get ALL invoices regardless of acknowledgment status
    # Simplified query without joins to avoid relationship issues
    query = db.query(Invoice)
    
    # Apply filters with more flexible route matching
    if request.route_name:
        # Try to extract route number if format is "Route X"
        route_filter = request.route_name
        if route_filter.startswith("Route "):
            try:
                route_number = int(route_filter.split(" ")[1])
                # Filter by route_number OR route_name
                query = query.filter(
                    or_(
                        Invoice.route_number == route_number,
                        Invoice.route_name == request.route_name
                    )
                )
                print(f"DEBUG: Filtering by route_number {route_number} OR route_name '{request.route_name}'")
            except (ValueError, IndexError):
                # Fallback to route_name only
                query = query.filter(Invoice.route_name == request.route_name)
                print(f"DEBUG: Filtering by route_name '{request.route_name}' only")
        else:
            query = query.filter(Invoice.route_name == request.route_name)
            print(f"DEBUG: Filtering by route_name '{request.route_name}' only")
    
    if request.driver_id:
        query = query.filter(Invoice.assigned_driver_id == request.driver_id)
        print(f"DEBUG: Filtering by driver_id {request.driver_id}")
    
    # Remove date filtering for now to get all invoices for the route
    # if request.date:
    #     try:
    #         filter_date = datetime.strptime(request.date, "%Y-%m-%d").date()
    #         query = query.filter(func.date(Invoice.invoice_date) == filter_date)
    #         print(f"DEBUG: Filtering by date {filter_date}")
    #     except ValueError:
    #         raise HTTPException(
    #             status_code=status.HTTP_400_BAD_REQUEST,
    #             detail="Invalid date format. Use YYYY-MM-DD"
    #         )
    
    if request.branch_id:
        query = query.filter(Invoice.branch_id == request.branch_id)
        print(f"DEBUG: Filtering by branch_id {request.branch_id}")
    
    # Get invoices - ALL invoices for the route regardless of status
    invoices = query.all()
    print(f"DEBUG: Found {len(invoices)} invoices")
    
    # If no invoices found, let's see what invoices exist for debugging
    if not invoices:
        # Let's try a simpler query first - just by driver
        if request.driver_id:
            simple_query = db.query(Invoice).filter(Invoice.assigned_driver_id == request.driver_id)
            driver_invoices = simple_query.all()
            print(f"DEBUG: Driver {request.driver_id} has {len(driver_invoices)} total invoices")
            
        # If still no invoices, show what's available
        all_invoices = db.query(Invoice).limit(5).all()
        print(f"DEBUG: Sample of available invoices:")
        for inv in all_invoices:
            print(f"  - ID: {inv.invoice_id}, Route: {inv.route_number}/{inv.route_name}, Driver: {inv.assigned_driver_id}")
        
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No invoices found. Searched for route_name='{request.route_name}', driver_id={request.driver_id}"
        )
    
    # Get route information from first invoice
    first_invoice = invoices[0]
    
    # Get driver name safely
    driver_name = "N/A"
    if first_invoice.assigned_driver_id:
        driver = db.query(User).filter(User.user_id == first_invoice.assigned_driver_id).first()
        driver_name = driver.name if driver else "N/A"
    
    # Get route name
    route_name = request.route_name or first_invoice.route_name or f"Route {first_invoice.route_number}" or "N/A"
    
    # Get branch name safely
    branch_name = "N/A"
    if first_invoice.branch_id:
        branch = db.query(Branch).filter(Branch.branch_id == first_invoice.branch_id).first()
        branch_name = branch.name if branch else "N/A"
    
    # Calculate totals
    total_amount = sum(float(invoice.amount) for invoice in invoices)
    total_invoices = len(invoices)
    
    # Count acknowledged vs pending - status is "delivered" not "acknowledged"
    acknowledged_count = sum(1 for inv in invoices if inv.status == "delivered")
    pending_count = total_invoices - acknowledged_count
    
    # Generate HTML for PDF
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Route Invoice Summary</title>
        <style>
            @page {{
                size: A4 portrait;
                margin: 1.5cm 2cm 2cm 2cm;
                @top-center {{
                    content: "Route Invoice Summary - Page " counter(page);
                    font-size: 10px;
                    color: #666;
                }}
            }}
            * {{
                box-sizing: border-box;
            }}
            body {{
                font-family: 'Arial', 'Helvetica', sans-serif;
                margin: 0;
                padding: 0;
                color: #333333;
                line-height: 1.3;
                font-size: 11px;
                background-color: white;
            }}
            .document-header {{
                text-align: center;
                margin-bottom: 25px;
                padding: 20px 0;
                border-bottom: 2px solid #2c3e50;
                page-break-inside: avoid;
            }}
            .document-title {{
                font-size: 20px;
                font-weight: bold;
                color: #2c3e50;
                margin: 0 0 8px 0;
                text-transform: uppercase;
                letter-spacing: 1.5px;
            }}
            .document-subtitle {{
                font-size: 12px;
                color: #666;
                margin: 0;
            }}
            .info-section {{
                margin-bottom: 25px;
                page-break-inside: avoid;
            }}
            .info-grid {{
                display: table;
                width: 100%;
                border: 1px solid #ddd;
            }}
            .info-row {{
                display: table-row;
            }}
            .info-cell {{
                display: table-cell;
                padding: 8px 12px;
                border-bottom: 1px solid #eee;
                vertical-align: top;
                width: 50%;
            }}
            .info-label {{
                font-weight: bold;
                color: #2c3e50;
                display: inline-block;
                width: 100px;
                font-size: 11px;
            }}
            .info-value {{
                color: #333;
                font-size: 11px;
            }}
            .summary-box {{
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                padding: 15px;
                margin-bottom: 20px;
                text-align: center;
                page-break-inside: avoid;
            }}
            .summary-title {{
                font-size: 14px;
                font-weight: bold;
                color: #2c3e50;
                margin: 0 0 8px 0;
            }}
            .summary-stats {{
                font-size: 12px;
                color: #666;
            }}
            .invoice-table {{
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
                font-size: 10px;
                background-color: white;
            }}
            .invoice-table th {{
                background-color: #2c3e50;
                color: white;
                font-weight: bold;
                padding: 10px 6px;
                text-align: left;
                font-size: 10px;
                border: 1px solid #2c3e50;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}
            .invoice-table td {{
                padding: 8px 6px;
                border: 1px solid #ddd;
                vertical-align: middle;
                font-size: 10px;
            }}
            .invoice-table tbody tr:nth-child(even) {{
                background-color: #f8f9fa;
            }}
            .invoice-table tbody tr:nth-child(odd) {{
                background-color: white;
            }}
            .col-sno {{ width: 6%; text-align: center; }}
            .col-invoice {{ width: 16%; }}
            .col-customer {{ width: 25%; }}
            .col-amount {{ width: 13%; text-align: right; }}
            .col-status {{ width: 12%; text-align: center; }}
            .col-signature {{ width: 28%; text-align: center; }}
            .signature-img {{
                max-width: 140px;
                max-height: 80px;
                object-fit: contain;
                border: 1px solid #ddd;
                background-color: white;
                display: block;
                margin: 4px auto;
                padding: 6px;
            }}
            .amount-cell {{
                font-weight: bold;
                color: #27ae60;
                text-align: right;
            }}
            .status-delivered {{
                color: #27ae60;
                font-weight: bold;
                background-color: #d5f4e6;
                padding: 2px 6px;
                border-radius: 3px;
                font-size: 9px;
                text-transform: uppercase;
            }}
            .status-pending {{
                color: #e67e22;
                font-weight: bold;
                background-color: #fef2e7;
                padding: 2px 6px;
                border-radius: 3px;
                font-size: 9px;
                text-transform: uppercase;
            }}
            .total-row {{
                background-color: #34495e !important;
                color: white;
                font-weight: bold;
                font-size: 11px;
            }}
            .total-row td {{
                border: 1px solid #34495e;
                padding: 12px 6px;
            }}
            .invoice-number {{
                font-weight: bold;
                color: #2980b9;
            }}
            .customer-name {{
                color: #333;
            }}
            .no-signature {{
                color: #999;
                font-style: italic;
                font-size: 9px;
            }}
            .document-footer {{
                margin-top: 30px;
                padding-top: 15px;
                border-top: 1px solid #ddd;
                font-size: 9px;
                color: #666;
                text-align: center;
                page-break-inside: avoid;
            }}
            .page-break {{
                page-break-before: always;
            }}
            /* Print-specific styles */
            @media print {{
                body {{
                    -webkit-print-color-adjust: exact;
                    color-adjust: exact;
                }}
                .invoice-table {{
                    page-break-inside: auto;
                }}
                .invoice-table tr {{
                    page-break-inside: avoid;
                    page-break-after: auto;
                }}
                .invoice-table thead {{
                    display: table-header-group;
                }}
                .invoice-table tfoot {{
                    display: table-footer-group;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="document-header">
            <h1 class="document-title">Route Invoice Summary</h1>
            <p class="document-subtitle">Generated on {datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")}</p>
        </div>
        
        <div class="info-section">
            <div class="info-grid">
                <div class="info-row">
                    <div class="info-cell">
                        <span class="info-label">Driver Name:</span>
                        <span class="info-value">{driver_name}</span>
                    </div>
                    <div class="info-cell">
                        <span class="info-label">Route Name:</span>
                        <span class="info-value">{route_name}</span>
                    </div>
                </div>
                <div class="info-row">
                    <div class="info-cell">
                        <span class="info-label">Branch:</span>
                        <span class="info-value">{branch_name}</span>
                    </div>
                    <div class="info-cell">
                        <span class="info-label">Total Invoices:</span>
                        <span class="info-value">{total_invoices}</span>
                    </div>
                </div>
                <div class="info-row">
                    <div class="info-cell">
                        <span class="info-label">Delivered:</span>
                        <span class="info-value">{acknowledged_count}</span>
                    </div>
                    <div class="info-cell">
                        <span class="info-label">Pending:</span>
                        <span class="info-value">{pending_count}</span>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="summary-box">
            <div class="summary-title">Total Route Value</div>
            <div style="font-size: 16px; font-weight: bold; color: #27ae60;">₹{total_amount:.2f}</div>
        </div>
        
        <table class="invoice-table">
            <thead>
                <tr>
                    <th class="col-sno">S.No</th>
                    <th class="col-invoice">Invoice Number</th>
                    <th class="col-customer">Customer Name</th>
                    <th class="col-amount">Amount</th>
                    <th class="col-status">Status</th>
                    <th class="col-signature">Signature</th>
                </tr>
            </thead>
            <tbody>
    """
    
    # Add table rows - include ALL invoices regardless of status
    for i, invoice in enumerate(invoices, 1):
        status_class = "status-delivered" if invoice.status == "delivered" else "status-pending"
        status_text = "Delivered" if invoice.status == "delivered" else "Pending"
        
        # Handle signature image - gracefully handle missing signatures
        signature_img = '<span class="no-signature">N/A</span>'  # Default value
        
        if invoice.status == "delivered" and invoice.driver_signature:
            signature_path = os.path.join(settings.upload_folder, invoice.driver_signature)
            if os.path.exists(signature_path):
                try:
                    import base64
                    with open(signature_path, 'rb') as f:
                        signature_data = base64.b64encode(f.read()).decode('utf-8')
                    signature_img = f'<img class="signature-img" src="data:image/png;base64,{signature_data}" alt="Signature" title="Delivery Signature" />'
                except Exception as e:
                    print(f"DEBUG: Error loading signature {invoice.driver_signature}: {e}")
                    signature_img = '<span class="no-signature">Error loading signature</span>'
            else:
                print(f"DEBUG: Signature file not found: {signature_path}")
                signature_img = '<span class="no-signature">Signature file missing</span>'
        elif invoice.status == "delivered":
            signature_img = '<span class="no-signature">No signature saved</span>'
        else:
            signature_img = '<span class="no-signature">Not delivered yet</span>'
        
        html_content += f"""
                <tr>
                    <td class="col-sno">{i}</td>
                    <td class="col-invoice invoice-number">{invoice.n_inv_no or 'N/A'}</td>
                    <td class="col-customer customer-name">{invoice.cust_name or 'N/A'}</td>
                    <td class="col-amount amount-cell">₹{float(invoice.amount):.2f}</td>
                    <td class="col-status"><span class="{status_class}">{status_text}</span></td>
                    <td class="col-signature">{signature_img}</td>
                </tr>
        """
    
    # Add total row
    html_content += f"""
            </tbody>
            <tfoot>
                <tr class="total-row">
                    <td colspan="3"><strong>TOTAL ROUTE VALUE</strong></td>
                    <td class="amount-cell"><strong>₹{total_amount:.2f}</strong></td>
                    <td colspan="2" style="text-align: center;"><strong>{acknowledged_count}/{total_invoices} COMPLETED</strong></td>
                </tr>
            </tfoot>
        </table>
        
        <div class="document-footer">
            <p><strong>Document generated by:</strong> {current_user.name} ({current_user.email})</p>
            <p><strong>Generated on:</strong> {datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")}</p>
            <p><em>This is a computer-generated document from the Pharma Delivery Management System</em></p>
        </div>
    </body>
    </html>
    """
    
    # Generate PDF using ReportLab (Vercel compatible)
    try:
        pdf_content = utils.generate_route_summary_pdf(
            route_name=route_name,
            invoices=invoices,
            current_user_name=current_user.name,
            current_user_email=current_user.email
        )
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"route_summary_{route_name}_{timestamp}.pdf"
        
        return Response(
            content=pdf_content,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate PDF: {str(e)}"
        )

@router.get("/drivers/live", response_model=schemas.LiveLocationsResponse)
async def get_live_driver_locations(
    current_admin: User = Depends(auth.get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Admin: get latest GPS location for every active driver."""
    from app.models import DriverLocation
    locations = db.query(DriverLocation).all()
    now = datetime.utcnow()
    result = []
    for loc in locations:
        driver = db.query(User).filter(User.user_id == loc.driver_id).first()
        if not driver:
            continue
        minutes_ago = int((now - loc.updated_at).total_seconds() / 60)
        result.append(schemas.DriverLiveLocation(
            driver_id=str(loc.driver_id),
            driver_name=driver.name,
            latitude=float(loc.latitude),
            longitude=float(loc.longitude),
            accuracy=float(loc.accuracy) if loc.accuracy else None,
            updated_at=loc.updated_at.isoformat(),
            minutes_ago=minutes_ago,
        ))
    return schemas.LiveLocationsResponse(drivers=result, total=len(result))
