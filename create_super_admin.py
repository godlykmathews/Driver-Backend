"""
Script to create the initial super admin user.
Run this script before deploying the application.
"""

from app.database import engine, get_db
from app.models import Base, User, UserRole
from app.auth import get_password_hash
from sqlalchemy.orm import sessionmaker
import sys

def create_super_admin():
    """Create the initial super admin user if none exists."""
    
    # Create database session
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        # Check if any users already exist
        user_count = db.query(User).count()
        
        if user_count > 0:
            print("❌ Super admin already exists. Skipping creation.")
            print(f"Found {user_count} user(s) in the database.")
            return False
        
        # Create super admin
        super_admin = User(
            name="Super Admin",
            email="superadmin@example.com",
            password_hash=get_password_hash("superadmin123"),
            role=UserRole.super_admin,
            branch_id=None,
            is_temporary=False
        )
        
        db.add(super_admin)
        db.commit()
        db.refresh(super_admin)  
        print("✅ Super admin created successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error creating super admin: {e}")
        db.rollback()
        return False
        
    finally:
        db.close()

if __name__ == "__main__":
    print("🚀 Creating initial super admin...")
    
    # Create tables if they don't exist
    print("📦 Ensuring database tables exist...")
    Base.metadata.create_all(bind=engine)
    
    success = create_super_admin()
    
    if success:
        print("\n🎉 Setup complete! You can now start the application.")
        sys.exit(0)
    else:
        print("\n⚠️  Setup completed with warnings.")
        sys.exit(1)