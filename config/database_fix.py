"""
Helper to diagnose and fix DigitalOcean database connection issues.
"""
import os
import logging

logger = logging.getLogger(__name__)


def get_database_url():
    """
    Get DATABASE_URL from environment, checking all possible sources.
    DigitalOcean may set it in different ways.
    """
    # Check all possible environment variable names
    db_url = (
        os.environ.get("DATABASE_URL", "").strip() or
        os.environ.get("SUPABASE_URL", "").strip() or
        os.environ.get("SUPABASE_DATABASE_URL", "").strip() or
        os.environ.get("POSTGRES_URL", "").strip() or
        os.environ.get("POSTGRESQL_URL", "").strip()
    )
    
    return db_url if db_url else None


def ensure_ssl_in_connection_string(connection_string):
    """
    Ensure connection string includes SSL parameter for DigitalOcean.
    DigitalOcean requires sslmode=require.
    """
    if not connection_string:
        return connection_string
    
    # If it already has sslmode, return as-is
    if "sslmode=" in connection_string:
        return connection_string
    
    # Add sslmode=require if it's a PostgreSQL connection
    if connection_string.startswith(("postgres://", "postgresql://")):
        separator = "?" if "?" not in connection_string else "&"
        return f"{connection_string}{separator}sslmode=require"
    
    return connection_string


def diagnose_database_issue():
    """
    Diagnose database connection issues and return helpful message.
    """
    db_url = get_database_url()
    
    if not db_url:
        return {
            "issue": "DATABASE_URL not set",
            "message": "DATABASE_URL environment variable is not set. DigitalOcean should set this automatically when you add a database component. Check App → Components → Database is connected.",
            "fix": "1. Check App → Components tab - is database component listed?\n2. If not, add it: Components → Add Component → Database\n3. If yes, check App → Settings → Environment Variables - is DATABASE_URL there?\n4. If not, get connection string from Database → Connection Details and add it manually."
        }
    
    # Check if it's a valid PostgreSQL connection string
    if not db_url.startswith(("postgres://", "postgresql://")):
        return {
            "issue": "Invalid connection string format",
            "message": f"DATABASE_URL is set but doesn't look like a PostgreSQL connection string: {db_url[:50]}...",
            "fix": "Get the correct connection string from Database → Connection Details → URI format"
        }
    
    # Check if SSL is included (DigitalOcean requires it)
    if "sslmode=" not in db_url:
        return {
            "issue": "Missing SSL parameter",
            "message": "DATABASE_URL doesn't include sslmode parameter. DigitalOcean requires SSL.",
            "fix": f"Add ?sslmode=require to the end of DATABASE_URL. Should be: {db_url}?sslmode=require"
        }
    
    return {
        "issue": None,
        "message": "DATABASE_URL looks correct",
        "fix": None
    }
