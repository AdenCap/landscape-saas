"""
Database persistence check and warnings.

This module ensures that production deployments use a persistent database
(PostgreSQL) instead of SQLite, which gets wiped on each deployment.
"""
import os
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


def check_database_persistence():
    """
    Check if the database configuration is suitable for production.
    
    Returns:
        tuple: (is_safe, warning_message)
        - is_safe: True if using PostgreSQL or in development
        - warning_message: Warning message if database might lose data
    """
    # Check if we're using SQLite
    db_engine = settings.DATABASES['default'].get('ENGINE', '')
    is_sqlite = 'sqlite' in db_engine.lower()
    
    # Check if we're in production (DEBUG=False or specific env vars)
    is_production = (
        not settings.DEBUG or
        os.environ.get('VERCEL', '').lower() == 'true' or
        os.environ.get('RAILWAY_ENVIRONMENT', '') or
        os.environ.get('RENDER', '').lower() == 'true' or
        os.environ.get('DYNO', '')  # Heroku
    )
    
    if is_sqlite and is_production:
        warning = (
            "⚠️ CRITICAL: You are using SQLite in production! "
            "SQLite databases are stored in the filesystem and will be LOST on each deployment. "
            "You MUST use PostgreSQL (or another persistent database) in production. "
            "Set DATABASE_URL environment variable to a PostgreSQL connection string. "
            "See docs/DATABASE_PERSISTENCE.md for setup instructions."
        )
        logger.critical(warning)
        return False, warning
    
    if is_sqlite:
        # SQLite is OK for development
        logger.info("Using SQLite database (OK for development)")
        return True, None
    
    # PostgreSQL or other persistent database
    logger.info(f"Using persistent database: {db_engine}")
    return True, None
