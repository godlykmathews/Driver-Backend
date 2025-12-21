#!/usr/bin/env python3
"""
Database migration script to add route support.
This script adds the new route fields to existing Invoice table.
"""

import os
import sys
from datetime import datetime
from app.database import engine
from sqlalchemy import text, inspect

def check_migration_needed():
    """Check if migration is needed by inspecting table structure."""
    inspector = inspect(engine)
    columns = inspector.get_columns('invoices')
    column_names = [col['name'] for col in columns]
    
    route_columns = ['route_number', 'route_name', 'route_date']
    missing_columns = [col for col in route_columns if col not in column_names]
    
    return missing_columns

def run_migration():
    """Run the database migration to add route fields."""
    print("🔄 Starting database migration for route functionality...")
    
    try:
        # Check what columns need to be added
        missing_columns = check_migration_needed()
        
        if not missing_columns:
            print("✅ Database is already up to date - no migration needed")
            return True
        
        print(f"📝 Adding missing columns: {missing_columns}")
        
        with engine.begin() as conn:
            # Add route_number column
            if 'route_number' in missing_columns:
                conn.execute(text("""
                    ALTER TABLE invoices 
                    ADD COLUMN route_number INTEGER;
                """))
                print("✅ Added route_number column")
            
            # Add route_name column
            if 'route_name' in missing_columns:
                conn.execute(text("""
                    ALTER TABLE invoices 
                    ADD COLUMN route_name VARCHAR;
                """))
                print("✅ Added route_name column")
            
            # Add route_date column
            if 'route_date' in missing_columns:
                conn.execute(text("""
                    ALTER TABLE invoices 
                    ADD COLUMN route_date DATETIME;
                """))
                print("✅ Added route_date column")
        
        print("🎉 Database migration completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {str(e)}")
        return False

def verify_migration():
    """Verify that the migration was successful."""
    print("🔍 Verifying migration...")
    
    try:
        missing_columns = check_migration_needed()
        
        if not missing_columns:
            print("✅ Migration verification successful - all route columns present")
            return True
        else:
            print(f"❌ Migration verification failed - missing columns: {missing_columns}")
            return False
            
    except Exception as e:
        print(f"❌ Migration verification failed: {str(e)}")
        return False

def backup_database():
    """Create a backup of the database before migration (for SQLite)."""
    try:
        # Check if using SQLite
        db_url = str(engine.url)
        if 'sqlite' in db_url.lower():
            db_path = db_url.split('///')[-1] if '///' in db_url else db_url.split('//')[-1]
            
            if os.path.exists(db_path):
                backup_path = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                
                import shutil
                shutil.copy2(db_path, backup_path)
                print(f"💾 Database backup created: {backup_path}")
                return backup_path
        else:
            print("ℹ️  Using PostgreSQL - automatic backups are handled by the provider")
            return None
            
    except Exception as e:
        print(f"⚠️  Warning: Could not create backup: {str(e)}")
        return None

def main():
    """Main migration function."""
    print("🚀 Route System Database Migration")
    print("=" * 50)
    
    # Create backup (for SQLite databases)
    backup_path = backup_database()
    
    # Check current state
    missing_columns = check_migration_needed()
    
    if not missing_columns:
        print("✅ Database is already up to date!")
        return True
    
    print(f"📋 Migration needed for columns: {missing_columns}")
    
    # Ask for confirmation
    response = input("\n🤔 Proceed with migration? (y/N): ").strip().lower()
    
    if response != 'y':
        print("❌ Migration cancelled by user")
        return False
    
    # Run migration
    if run_migration():
        # Verify migration
        if verify_migration():
            print("\n🎉 Migration completed successfully!")
            return True
        else:
            print("\n❌ Migration verification failed!")
            return False
    else:
        print("\n❌ Migration failed!")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)