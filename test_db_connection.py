#!/usr/bin/env python
"""
Database connection test script
"""
import sys
from sqlalchemy import text, inspect

# Add the app directory to the path
sys.path.insert(0, 'd:\\ML- Projects\\Auto_CAD\\back_dxf')

from app.core.config import settings
from app.db.database import engine, SessionLocal

def test_connection():
    """Test database connection"""
    print("=" * 60)
    print("Database Connection Test")
    print("=" * 60)
    print(f"\nDatabase URL: {settings.DATABASE_URL}")
    print(f"Host: localhost")
    print(f"User: root")
    print(f"Database: solar_layout")
    print("\n" + "=" * 60)
    
    try:
        # Test connection with engine
        print("\n[1] Testing engine connection...")
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            print("✓ Engine connection successful!")
        
        # Test session connection
        print("\n[2] Testing session connection...")
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        print("✓ Session connection successful!")
        
        # Get database info
        print("\n[3] Getting database information...")
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        print(f"✓ Connected to database: solar_layout")
        print(f"  Tables found: {len(tables)}")
        if tables:
            for table in tables:
                print(f"    - {table}")
        else:
            print("    (No tables yet)")
        
        # Test query
        print("\n[4] Testing database query...")
        result = db.execute(text("SELECT DATABASE()")).fetchone()
        current_db = result[0] if result else None
        print(f"✓ Current database: {current_db}")
        
        db.close()
        
        print("\n" + "=" * 60)
        print("✓ ALL TESTS PASSED - Database connection is working!")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n✗ Connection Error: {type(e).__name__}")
        print(f"  Message: {str(e)}")
        print("\n" + "=" * 60)
        print("✗ DATABASE CONNECTION FAILED")
        print("=" * 60)
        print("\nTroubleshooting tips:")
        print("1. Ensure MySQL server is running")
        print("2. Check if database 'solar_layout' exists")
        print("3. Verify credentials (user: root, password: Nethajee)")
        print("4. Check if port 3306 is accessible")
        return False

if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)
