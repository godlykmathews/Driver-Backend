"""
Migration: Add driver_locations table for live GPS tracking.
Run once: python migrate_location_tracking.py
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import engine, Base
from app.models import DriverLocation  # noqa: F401 — registers table with Base

def run():
    print("Creating driver_locations table if not exists...")
    Base.metadata.create_all(bind=engine, tables=[Base.metadata.tables['driver_locations']])
    print("Done.")

if __name__ == "__main__":
    run()
