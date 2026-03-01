#!/usr/bin/env python
"""
Quick script to verify database connection and configuration.
Run this to check if your database is set up correctly.
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.conf import settings
from django.db import connection
from config.database_check import check_database_persistence

def main():
    print("=" * 70)
    print("Database Verification")
    print("=" * 70)
    print()
    
    # Check configuration
    db_config = settings.DATABASES['default']
    engine = db_config.get('ENGINE', '')
    name = db_config.get('NAME', '')
    host = db_config.get('HOST', '')
    
    print(f"Database Engine: {engine}")
    print(f"Database Name: {name}")
    if host:
        print(f"Database Host: {host}")
    print()
    
    # Check persistence
    is_safe, warning = check_database_persistence()
    
    if is_safe and not warning:
        print("✅ Database configuration is SAFE - data will persist!")
        if 'postgresql' in engine.lower():
            print("   ✓ Using PostgreSQL - data will survive deployments")
        elif 'sqlite' in engine.lower():
            print("   ⚠ Using SQLite - OK for local development only")
    else:
        print("❌ WARNING: Database may lose data on deployments!")
        if warning:
            print()
            print(warning)
        sys.exit(1)
    
    print()
    print("Testing database connection...")
    
    # Test connection
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT version();")
            version = cursor.fetchone()[0]
            print(f"✅ Database connection successful!")
            print(f"   Database version: {version[:50]}...")
            
            # Check if we can read/write
            cursor.execute("SELECT COUNT(*) FROM django_migrations;")
            migration_count = cursor.fetchone()[0]
            print(f"   Migrations applied: {migration_count}")
            
            # Try to check for existing data
            try:
                from businesses.models import Business
                business_count = Business.objects.count()
                print(f"   Businesses in database: {business_count}")
                
                if business_count > 0:
                    print("   ✅ You have existing data - this will persist!")
                else:
                    print("   ℹ️  Database is empty (normal for new setup)")
            except Exception as e:
                print(f"   ⚠️  Could not check business data: {e}")
            
    except Exception as e:
        print(f"❌ Database connection failed!")
        print(f"   Error: {str(e)}")
        print()
        print("Troubleshooting:")
        print("1. Check DATABASE_URL is set correctly")
        print("2. Verify database credentials")
        print("3. Check database host is accessible")
        print("4. For Supabase: Use Session mode (port 6543)")
        sys.exit(1)
    
    print()
    print("=" * 70)
    print("✅ All checks passed! Your database is configured correctly.")
    print("=" * 70)
    print()
    print("Next steps:")
    print("1. Create some test data (invoice, customer, etc.)")
    print("2. Make a deployment")
    print("3. Verify data is still there after deployment")

if __name__ == '__main__':
    main()
