from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# Enum for user roles (matching your models)
class UserRoleEnum(str, Enum):
    super_admin = "super_admin"
    admin = "admin"
    driver = "driver"


class InvoiceStatusEnum(str, Enum):
    pending = "pending"
    delivered = "delivered"


# Auth schemas
class LoginRequest(BaseModel):
    username: str
    password: str


class UserInfo(BaseModel):
    id: str
    email: str
    name: str
    role: UserRoleEnum
    branches: List[str]
    is_active: bool


class LoginResponse(BaseModel):
    token: str
    user: UserInfo


class LogoutResponse(BaseModel):
    message: str


# Driver schemas
class DriverInfo(BaseModel):
    id: str
    username: str
    driver_name: str
    branches: List[str]
    role: UserRoleEnum = "driver"
    isActive: bool
    isTemporary: bool
    created_at: str
    last_login: Optional[str] = None
    temp_password: Optional[str] = None  # Add for temp drivers only

class PaginationInfo(BaseModel):
    current_page: int
    total_pages: int
    total_count: int
    per_page: int


class DriversResponse(BaseModel):
    drivers: List[DriverInfo]
    pagination: PaginationInfo


class CreateDriverRequest(BaseModel):
    driver_name: str
    email: str
    password: str
    branch_ids: List[int]  
    isTemporary: bool = False



class CreateDriverResponse(BaseModel):
    driver: DriverInfo
    message: str


class CreateTempDriverRequest(BaseModel):
    branch_ids: List[int]  # Change to list of branch IDs


class TempDriverCredentials(BaseModel):
    username: str
    password: str


class CreateTempDriverResponse(BaseModel):
    driver: DriverInfo
    credentials: TempDriverCredentials
    message: str


# Invoice schemas
class InvoiceInfo(BaseModel):
    id: str
    invoice_number: str
    customer_name: str
    amount: float
    invoice_date: Optional[str] = None
    status: str
    branch: str
    driver: Optional[str] = None
    created_date: str
    is_acknowledged: bool
    # Route fields
    route_number: Optional[int] = None
    route_name: Optional[str] = None
    route_display: Optional[str] = None  # Combined route number and name for display


class InvoicesResponse(BaseModel):
    invoices: List[InvoiceInfo]
    pagination: PaginationInfo


class CSVUploadResponse(BaseModel):
    imported_count: int
    assigned_count: int
    message: str
    errors: Optional[List[str]] = None


class UploadResponse(BaseModel):
    message: str
    uploaded_count: int
    skipped_count: int


# Route schemas
class RouteUploadRequest(BaseModel):
    driver_id: str
    route_name: Optional[str] = None  # Optional custom route name


class RouteInfo(BaseModel):
    route_number: int
    route_name: Optional[str] = None
    route_display: str  
    invoice_count: int
    driver_name: str
    created_date: str


class RoutesResponse(BaseModel):
    routes: List[RouteInfo]
    pagination: PaginationInfo


# Branch schemas
class BranchInfo(BaseModel):
    id: str
    name: str
    city: str
    phone: str
    email: str
    created_at: str
    is_active: bool


class BranchesResponse(BaseModel):
    branches: List[BranchInfo]
    pagination: PaginationInfo


class CreateBranchRequest(BaseModel):
    name: str
    city: str
    phone: Optional[str] = None
    email: str


class CreateBranchResponse(BaseModel):
    branch: BranchInfo
    message: str


class AdminInfo(BaseModel):
    id: str
    username: str
    admin_name: str
    assigned_branches: List[str]
    role: UserRoleEnum = "admin"


class BranchUsers(BaseModel):
    admins: List[AdminInfo]
    drivers: List[DriverInfo]
    total_users: int


class BranchDetailsResponse(BaseModel):
    branch: BranchInfo
    users: BranchUsers


# Admin schemas
class AdminFullInfo(BaseModel):
    id: str
    name: str
    branch: str
    email: str
    role: UserRoleEnum = "admin"
    created_at: str
    last_login: Optional[str] = None
    is_active: bool


class AdminsResponse(BaseModel):
    admins: List[AdminFullInfo]
    pagination: PaginationInfo


class CreateAdminRequest(BaseModel):
    name: str
    email: str
    password: str
    branch_id: str


class UpdateAdminRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    branch_id: Optional[str] = None


class UpdateDriverRequest(BaseModel):
    driver_name: Optional[str] = None
    email: Optional[str] = None
    branch_ids: Optional[List[int]] = None


class CreateAdminResponse(BaseModel):
    admin: AdminFullInfo
    message: str


# File upload schemas
class FileUploadResponse(BaseModel):
    file_id: str
    file_url: str
    file_name: str
    file_size: int
    message: str


# Error schemas
class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Optional[Any] = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
    timestamp: str
    path: str


# Legacy schemas for backward compatibility
class UserBase(BaseModel):
    name: str
    email: EmailStr
    role: UserRoleEnum
    branch_id: Optional[int] = None


class UserCreate(UserBase):
    password: str


class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[UserRoleEnum] = None
    branch_id: Optional[int] = None
    is_temporary: Optional[bool] = None
    expiry_time: Optional[datetime] = None


class UserResponse(UserBase):
    user_id: int
    is_temporary: bool
    expiry_time: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# Auth schemas for backward compatibility
class Token(BaseModel):
    access_token: str
    token_type: str
    user_id: int
    role: str
    branch_id: Optional[int] = None


class TokenData(BaseModel):
    email: Optional[str] = None


# Branch schemas for backward compatibility
class BranchBase(BaseModel):
    name: str
    city: str


class BranchCreate(BranchBase):
    pass


class BranchResponse(BranchBase):
    branch_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True


# Invoice schemas for backward compatibility
class InvoiceBase(BaseModel):
    shop_name: str
    amount: float
    invoice_date: Optional[datetime] = None
    branch_id: Optional[int] = None


class InvoiceCreate(InvoiceBase):
    delivery_date: Optional[datetime] = None


class InvoiceUpdate(BaseModel):
    shop_name: Optional[str] = None
    amount: Optional[float] = None
    invoice_date: Optional[datetime] = None
    branch_id: Optional[int] = None
    assigned_driver_id: Optional[int] = None
    delivery_status: Optional[InvoiceStatusEnum] = None
    pdf_path: Optional[str] = None
    delivery_date: Optional[datetime] = None


class InvoiceResponse(InvoiceBase):
    invoice_id: int
    assigned_driver_id: Optional[int] = None
    delivery_status: InvoiceStatusEnum
    pdf_path: Optional[str] = None
    delivery_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# Driver assignment schema
class DriverAssignment(BaseModel):
    invoice_ids: List[int]
    driver_id: int


# Signature submission schema
class SignatureSubmission(BaseModel):
    invoice_id: int
    signature_data: str
    delivery_notes: Optional[str] = None


# Driver statistics schema
class DriverStatistics(BaseModel):
    total_assigned: int
    delivered: int
    pending: int
    delivery_rate: float
    total_amount_delivered: float


# PDF generation schema
class PDFGenerationRequest(BaseModel):
    invoice_id: int
    include_signature: bool = True


class PDFResponse(BaseModel):
    pdf_url: str
    invoice_id: int
    generated_at: datetime


# CSV upload schema
class CSVUploadResponse(BaseModel):
    message: str
    processed_count: int
    failed_count: int
    failed_records: List[Dict[str, Any]]


# Additional schemas for driver operations
class DeliveryStatusUpdate(BaseModel):
    invoice_id: int
    status: InvoiceStatusEnum
    delivery_notes: Optional[str] = None


class DriverDashboard(BaseModel):
    total_assigned: int
    pending_deliveries: int
    completed_deliveries: int
    today_deliveries: int
    delivery_rate: float


# Driver response schemas
class DriverDashboardResponse(BaseModel):
    driver_name: str
    branches: List[str]
    total_invoices: int
    pending_invoices: int
    acknowledged_invoices: int
    today_invoices: int


class DriverInvoicesResponse(BaseModel):
    invoices: List[InvoiceInfo]
    total: int
    page: int
    per_page: int
    total_pages: int


class InvoiceDetailResponse(BaseModel):
    invoice: InvoiceInfo


class AcknowledgeRequest(BaseModel):
    signature: str
    notes: Optional[str] = None


class AcknowledgeResponse(BaseModel):
    message: str
    invoice_id: str
    acknowledged_at: str


class SignatureResponse(BaseModel):
    message: str
    signature_url: str


class DriverStats(BaseModel):
    total_invoices: int
    acknowledged_invoices: int
    pending_invoices: int


class DriverProfileResponse(BaseModel):
    driver: UserInfo
    statistics: DriverStats


class BulkDownloadRequest(BaseModel):
    invoice_ids: List[int]


class RouteWisePDFRequest(BaseModel):
    route_name: Optional[str] = None
    driver_id: Optional[int] = None
    date: Optional[str] = None  # Optional date filter in YYYY-MM-DD format
    branch_id: Optional[int] = None


# Customer Visit schemas (for grouping invoices by customer)
class CustomerVisitInfo(BaseModel):
    customer_name: str
    route_number: Optional[int] = None
    route_name: Optional[str] = None
    route_display: Optional[str] = None
    route_date: str
    invoice_count: int
    total_amount: float
    acknowledged_count: int
    is_fully_acknowledged: bool
    invoice_ids: List[int]


class CustomerVisitsResponse(BaseModel):
    visits: List[CustomerVisitInfo]
    pagination: PaginationInfo


class CustomerVisitDetailResponse(BaseModel):
    customer_name: str
    route_display: str
    route_date: str
    total_amount: float
    acknowledged_count: int
    total_count: int
    invoices: List[InvoiceInfo]


class CustomerVisitAcknowledgeRequest(BaseModel):
    signature: str  # Base64 encoded PNG signature
    notes: Optional[str] = None


class CustomerVisitAcknowledgeResponse(BaseModel):
    message: str
    customer_name: str
    acknowledged_invoices: List[str]  # List of invoice IDs that were acknowledged
    acknowledged_at: str


# New Grouped Invoice Schemas (for driver list view)
class CustomerGroupInfo(BaseModel):
    customer_visit_group: str  # "route_number-customer_name-date"
    customer_name: str
    shop_address: Optional[str] = None
    route_number: Optional[int] = None
    route_name: Optional[str] = None
    route_display: Optional[str] = None
    invoice_count: int
    total_amount: float
    status: str  # "pending", "delivered"
    first_invoice_id: int  # Used for navigation
    invoice_numbers: List[str]
    sequence_order: int  # Maintains CSV order
    branch: Optional[str] = None


class GroupedInvoicesResponse(BaseModel):
    groups: List[CustomerGroupInfo]
    total_groups: int
    pending_groups: int
    delivered_groups: int


class CustomerGroupDetail(BaseModel):
    customer_visit_group: str
    customer_name: str
    shop_address: Optional[str] = None
    route_number: Optional[int] = None
    route_name: Optional[str] = None
    route_display: Optional[str] = None
    invoices: List[InvoiceInfo]
    total_amount: float
    invoice_count: int
    all_acknowledged: bool
    branch: Optional[str] = None


class AcknowledgeGroupRequest(BaseModel):
    signature: str  # Base64 encoded PNG signature
    notes: Optional[str] = None


class AcknowledgeGroupResponse(BaseModel):
    message: str
    customer_name: str
    acknowledged_invoices: List[str]
    signature_saved: str
    pdfs_generated: List[str]
