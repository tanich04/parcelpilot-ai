# src/database/sqlite_db.py
import sqlite3
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SQLiteDB:
    def __init__(self, db_path=None):
        self.db_path = db_path or os.getenv(
            "DB_PATH",
            os.path.join(os.getcwd(), "parcelpilot.db")
        )

        logger.info(f"Using SQLite database: {self.db_path}")

        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        self._init_db()
    
    def _init_db(self):
        logger.info(f"Initializing database: {self.db_path}")
        logger.info(f"Exists: {os.path.exists(self.db_path)}")
        logger.info(f"Directory: {os.path.dirname(self.db_path)}")
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create tables with CORRECT column names
        cursor.executescript("""
            -- Accounts table (matches your Excel)
            CREATE TABLE IF NOT EXISTS accounts (
                account_id TEXT PRIMARY KEY,
                account_name TEXT,
                plan TEXT,                    -- Changed from 'tier'
                status TEXT,
                csm TEXT,
                contract_file TEXT,
                premium_support TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            -- Orders table (matches your Excel)
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                account_id TEXT REFERENCES accounts(account_id),
                carrier TEXT,
                status TEXT,
                booked_at TIMESTAMP,
                pickup_window_start TIMESTAMP,
                pickup_window_end TIMESTAMP,
                pickup_actual_at TIMESTAMP,
                shipment_fee_inr REAL,
                carrier_fault INTEGER DEFAULT 0,
                customer_fault INTEGER DEFAULT 0,
                cancellation_requested_at TIMESTAMP,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            -- Tickets table (matches your Excel)
            CREATE TABLE IF NOT EXISTS tickets (
                ticket_id TEXT PRIMARY KEY,
                account_id TEXT REFERENCES accounts(account_id),
                created_at TIMESTAMP,
                status TEXT,
                subject TEXT,
                description TEXT,
                channel TEXT,
                assigned_to TEXT,
                last_customer_message_at TIMESTAMP,
                historical_resolution TEXT
            );
            
            -- Documents table (for PDFs)
            CREATE TABLE IF NOT EXISTS documents (
                doc_id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT,
                doc_type TEXT,
                authority_level INTEGER,
                account_scope TEXT,
                is_current INTEGER,
                content TEXT,
                metadata TEXT
            );
            
            -- Create indexes
            CREATE INDEX IF NOT EXISTS idx_orders_account ON orders(account_id);
            CREATE INDEX IF NOT EXISTS idx_tickets_account ON tickets(account_id);
            CREATE INDEX IF NOT EXISTS idx_documents_scope ON documents(account_scope);
        """)
        
        conn.commit()
        conn.close()
        logger.info("✅ SQLite database initialized with correct schema")
    
    def get_connection(self):
        logger.info(f"Opening database: {self.db_path}")
        return sqlite3.connect(self.db_path)   

if __name__ == "__main__":
    db = SQLiteDB()
    print("✅ Database ready!")
