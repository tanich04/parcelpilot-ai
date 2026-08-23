# src/ingestion/init_db.py
import sqlite3
import os
import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from src.config import DB_PATH

print("Using DB:", DB_PATH)

def init_database():
    """Create all tables if they don't exist."""
    try:
        logger.info(f"📊 Initializing database at: {DB_PATH}")
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS accounts (
                account_id TEXT PRIMARY KEY, account_name TEXT, plan TEXT, status TEXT,
                csm TEXT, contract_file TEXT, premium_support TEXT, notes TEXT
            );
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY, account_id TEXT, carrier TEXT, status TEXT,
                booked_at TIMESTAMP, pickup_window_start TIMESTAMP, pickup_window_end TIMESTAMP,
                pickup_actual_at TIMESTAMP, shipment_fee_inr REAL, carrier_fault INTEGER,
                customer_fault INTEGER, cancellation_requested_at TIMESTAMP, notes TEXT
            );
            CREATE TABLE IF NOT EXISTS tickets (
                ticket_id TEXT PRIMARY KEY, account_id TEXT, created_at TIMESTAMP,
                status TEXT, subject TEXT, description TEXT, channel TEXT, assigned_to TEXT,
                last_customer_message_at TIMESTAMP, historical_resolution TEXT
            );
            CREATE TABLE IF NOT EXISTS documents (
                doc_id INTEGER PRIMARY KEY AUTOINCREMENT, filename TEXT, doc_type TEXT,
                authority_level INTEGER, account_scope TEXT, is_current INTEGER,
                content TEXT, metadata TEXT
            );
        """)
        conn.commit()
        conn.close()
        logger.info("✅ Database tables created successfully at {DB_PATH}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to initialize database: {e}")
        return False

if __name__ == "__main__":
    success = init_database()
    sys.exit(0 if success else 1)
