from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.routers import auth_router, admin_router, driver_router
from app.database import engine
from app import models
from app.config import settings
from app.auth import get_password_hash
from app.models import User, UserRole
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
import logging
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create database tables
models.Base.metadata.create_all(bind=engine)

# Auto-create super admin on startup if none exists
def create_initial_super_admin():
    """Create initial super admin user if none exists."""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        # Check if super admin already exists
        super_admin_count = db.query(User).filter(User.role == UserRole.super_admin).count()
        
        if super_admin_count > 0:
            logger.info("ℹ️  Super admin already exists, skipping creation")
            return
        
        # Get credentials from environment variables
        super_admin_email = os.environ.get('SUPER_ADMIN_EMAIL', 'superadmin@example.com')
        super_admin_password = os.environ.get('SUPER_ADMIN_PASSWORD', 'superadmin123')
        
        # Create super admin
        super_admin = User(
            name="Super Admin",
            email=super_admin_email,
            password_hash=get_password_hash(super_admin_password),
            role=UserRole.super_admin,
            branch_id=None,
            is_temporary=False
        )
        
        db.add(super_admin)
        db.commit()
        db.refresh(super_admin)
        
        logger.info(f"✅ Initial super admin created: {super_admin.email}")
        
    except Exception as e:
        logger.error(f"❌ Error creating super admin: {e}")
        db.rollback()
        
    finally:
        db.close()

# Create super admin on startup
create_initial_super_admin()

app = FastAPI(
    title="Pharma Delivery Backend",
    description="Backend API for pharmaceutical delivery acknowledgement system",
    version="1.0.0",
    debug=settings.debug
)

# CORS middleware
# Parse CORS origins from environment variable (comma-separated)
cors_origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]

# Add default development origins if debug mode

cors_origins.extend([
    "http://localhost:3000",
    "http://localhost:8080",
    "http://localhost:5173",
    "*",
])

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # allow all origins during testing
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for PDFs and uploads
try:
    if not os.path.exists(settings.pdf_folder):
        os.makedirs(settings.pdf_folder)
    app.mount("/pdfs", StaticFiles(directory=settings.pdf_folder), name="pdfs")
except Exception as e:
    logger.warning(f"Could not mount /pdfs: {e}")

try:
    if not os.path.exists(settings.upload_folder):
        os.makedirs(settings.upload_folder)
    app.mount("/uploads", StaticFiles(directory=settings.upload_folder), name="uploads")
except Exception as e:
    logger.warning(f"Could not mount /uploads: {e}")

# Include routers
app.include_router(auth_router.router, prefix="/api/v1", tags=["authentication"])
app.include_router(admin_router.router, prefix="/api/v1", tags=["admin"])
app.include_router(driver_router.router, prefix="/api/v1", tags=["drivers"])




from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.status import HTTP_422_UNPROCESSABLE_ENTITY
import json

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    try:
        body = await request.json()
    except Exception:
        body = "Non-JSON or unreadable body"
    print("❌ 422 Validation Error:")
    print("Request path:", request.url.path)
    print("Raw body:", body)
    print("Validation details:", json.dumps(exc.errors(), indent=2))
    return JSONResponse(
        status_code=HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors(), "body": body},
    )



@app.get("/")
async def root():
    return {"message": "Pharma Delivery Backend API", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    """Check database connectivity, super admin existence, and database file status."""
    try:
        # Check if SQLite database file exists (for SQLite databases)
        db_file_exists = False
        db_file_path = None
        db_type = "postgresql"  # Default to PostgreSQL

        if "sqlite" in str(settings.database_url).lower():
            db_type = "sqlite"
            # Extract database file path from SQLite URL
            if "///" in settings.database_url:
                db_file_path = settings.database_url.split("///")[1]
                db_file_exists = os.path.exists(db_file_path)
                logger.info(f"SQLite database file path: {db_file_path}, exists: {db_file_exists}")
        else:
            logger.info("Using PostgreSQL database (Supabase)")
        
        # Test database connection
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        
        try:
            # Test database connectivity with a simple query
            db.execute(text("SELECT 1"))
            
            # Check if super admin exists
            super_admin_count = db.query(User).filter(User.role == UserRole.super_admin).count()
            super_admin_exists = super_admin_count > 0
            
            return {
                "status": "ok",
                "database": "connected",
                "database_type": db_type,
                "super_admin_exists": super_admin_exists,
                "database_file_exists": db_file_exists,
                "database_file_path": db_file_path
            }
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            "status": "error",
            "database": "disconnected",
            "super_admin_exists": False,
            "database_file_exists": False,
            "error": str(e)
        }