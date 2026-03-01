#!/usr/bin/env python
"""
Standalone script to check database configuration.
Run this to verify your database is set up correctly for production.
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from config.database_check import check_database_persistence
from django.conf import settings

def main():
    print("=" * 70)
    print("Database Configuration Check")
    print("=" * 70)
    print()
    
    db_config = settings.DATABASES['default']
    engine = db_config.get('ENGINE', '')
    name = db_config.get('NAME', '')
    
    print(f"Database Engine: {engine}")
    print(f"Database Name: {name}")
    print()
    
    is_safe, warning = check_database_persistence()
    
    if is_safe and not warning:
        print("✅ Database configuration is safe for production!")
        if 'sqlite' in engine.lower():
            print("   (Using SQLite - OK for local development)")
        else:
            print("   (Using persistent database - data will survive deployments)")
    else:
        print("❌ WARNING: Database configuration may cause data loss!")
        print()
        if warning:
            print(warning)
        print()
        print("To fix:")
        print("1. Set DATABASE_URL environment variable")
        print("2. Use a PostgreSQL connection string")
        print("3. See docs/DATABASE_PERSISTENCE.md for details")
        sys.exit(1)
    
    print()
    print("=" * 70)

if __name__ == '__main__':
    main()
