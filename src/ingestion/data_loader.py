# src/ingestion/data_loader.py
import pandas as pd
from pathlib import Path
import pypdf
import json
import logging
from src.database.sqlite_db import SQLiteDB
from src.vector_store.chroma_store import ChromaVectorStore
from src.config import DB_PATH

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
print("Using DB:", DB_PATH)

class DataLoader:
    def __init__(self):
        self.db = SQLiteDB()
        self.vector_store = ChromaVectorStore()
    
    def load_excel(self, excel_path):
        """Load Excel data with CORRECT column mappings"""
        logger.info(f"Loading Excel: {excel_path}")
        
        try:
            # Read all sheets
            excel_data = pd.read_excel(excel_path, sheet_name=None)
            logger.info(f"📋 Sheets found: {list(excel_data.keys())}")
            
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            # Load accounts
            if 'accounts' in excel_data:
                df = excel_data['accounts']
                logger.info(f"  Loading accounts: {len(df)} rows")
                
                # Clear existing
                cursor.execute("DELETE FROM accounts")
                
                for _, row in df.iterrows():
                    # Convert NaN to None
                    record = {k: (None if pd.isna(v) else v) for k, v in row.to_dict().items()}
                    
                    # Insert with correct columns
                    cursor.execute("""
                        INSERT INTO accounts (
                            account_id, account_name, plan, status, csm,
                            contract_file, premium_support, notes
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        record.get('account_id'),
                        record.get('account_name'),
                        record.get('plan'),
                        record.get('status'),
                        record.get('csm'),
                        record.get('contract_file'),
                        record.get('premium_support'),
                        record.get('notes')
                    ))
                
                logger.info(f"  ✅ Loaded {len(df)} accounts")
            
            # Load orders
            if 'orders' in excel_data:
                df = excel_data['orders']
                logger.info(f"  Loading orders: {len(df)} rows")
                
                cursor.execute("DELETE FROM orders")
                
                for _, row in df.iterrows():
                    record = {k: (None if pd.isna(v) else v) for k, v in row.to_dict().items()}
                    
                    cursor.execute("""
                        INSERT INTO orders (
                            order_id, account_id, carrier, status,
                            booked_at, pickup_window_start, pickup_window_end,
                            pickup_actual_at, shipment_fee_inr,
                            carrier_fault, customer_fault,
                            cancellation_requested_at, notes
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        record.get('order_id'),
                        record.get('account_id'),
                        record.get('carrier'),
                        record.get('status'),
                        record.get('booked_at'),
                        record.get('pickup_window_start'),
                        record.get('pickup_window_end'),
                        record.get('pickup_actual_at'),
                        record.get('shipment_fee_inr'),
                        int(record.get('carrier_fault', 0)),
                        int(record.get('customer_fault', 0)),
                        record.get('cancellation_requested_at'),
                        record.get('notes')
                    ))
                
                logger.info(f"  ✅ Loaded {len(df)} orders")
            
            # Load tickets
            if 'tickets' in excel_data:
                df = excel_data['tickets']
                logger.info(f"  Loading tickets: {len(df)} rows")
                
                cursor.execute("DELETE FROM tickets")
                
                for _, row in df.iterrows():
                    record = {k: (None if pd.isna(v) else v) for k, v in row.to_dict().items()}
                    
                    cursor.execute("""
                        INSERT INTO tickets (
                            ticket_id, account_id, created_at, status,
                            subject, description, channel,
                            assigned_to, last_customer_message_at,
                            historical_resolution
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        record.get('ticket_id'),
                        record.get('account_id'),
                        record.get('created_at'),
                        record.get('status'),
                        record.get('subject'),
                        record.get('description'),
                        record.get('channel'),
                        record.get('assigned_to'),
                        record.get('last_customer_message_at'),
                        record.get('historical_resolution')
                    ))
                
                logger.info(f"  ✅ Loaded {len(df)} tickets")
            
            conn.commit()
            conn.close()
            logger.info("✅ Excel data loaded successfully!")
            
        except Exception as e:
            logger.error(f"Error loading Excel: {e}")
            raise
    
    def load_pdfs(self, pdf_directory):
        """Load PDFs into SQLite and ChromaDB"""
        logger.info(f"Loading PDFs from: {pdf_directory}")
        
        # Document metadata with correct mapping
        doc_metadata = {
            "01_Support_Policy_v3_CURRENT.pdf": {
                "doc_type": "policy", "authority_level": 3,
                "account_scope": "GLOBAL", "is_current": 1
            },
            "02_Support_Policy_v2_DEPRECATED.pdf": {
                "doc_type": "policy", "authority_level": 5,
                "account_scope": "GLOBAL", "is_current": 0
            },
            "03_Cancellation_and_Service_Credit_SOP_v4.pdf": {
                "doc_type": "sop", "authority_level": 2,
                "account_scope": "GLOBAL", "is_current": 1
            },
            "04_Product_Operations_Guide_and_Known_Issues.pdf": {
                "doc_type": "guide", "authority_level": 2,
                "account_scope": "GLOBAL", "is_current": 1
            },
            "05_Northstar_Logistics_Enterprise_Agreement.pdf": {
                "doc_type": "contract", "authority_level": 1,
                "account_scope": "ACC-Northstar", "is_current": 1
            },
            "06_LumenWorks_Service_Agreement.pdf": {
                "doc_type": "contract", "authority_level": 1,
                "account_scope": "ACC-LumenWorks", "is_current": 1
            }
        }
        
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        # Clear existing
        cursor.execute("DELETE FROM documents")
        self.vector_store.clear()
        
        all_chunks = []
        doc_count = 0
        
        for filename, meta in doc_metadata.items():
            pdf_path = Path(pdf_directory) / filename
            if not pdf_path.exists():
                logger.warning(f"File not found: {pdf_path}")
                continue
            
            logger.info(f"  Processing: {filename}")
            
            # Extract text
            content = self._extract_pdf_text(pdf_path)
            if not content:
                logger.warning(f"  ⚠️ No content in {filename}")
                continue
            
            # Insert into SQLite
            cursor.execute("""
                INSERT INTO documents (filename, doc_type, authority_level, account_scope, is_current, content)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (filename, meta['doc_type'], meta['authority_level'], 
                  meta['account_scope'], meta['is_current'], content))
            
            doc_id = cursor.lastrowid
            doc_count += 1
            
            # Chunk and prepare for vector store
            chunks = self._chunk_text(content)
            for i, chunk in enumerate(chunks):
                all_chunks.append({
                    "doc_id": doc_id,
                    "chunk": chunk,
                    "filename": filename,
                    "doc_type": meta['doc_type'],
                    "authority_level": meta['authority_level'],
                    "account_scope": meta['account_scope'],
                    "is_current": meta['is_current'],
                    "chunk_index": i
                })
            
            logger.info(f"  ✅ {len(chunks)} chunks created")
        
        conn.commit()
        conn.close()
        
        # Add to vector store
        if all_chunks:
            self.vector_store.add_documents(all_chunks)
            logger.info(f"✅ Added {len(all_chunks)} chunks to vector store")
        else:
            logger.warning("⚠️ No chunks to add to vector store")
        
        logger.info(f"✅ Loaded {doc_count} documents")
    
    def _extract_pdf_text(self, pdf_path):
        try:
            reader = pypdf.PdfReader(pdf_path)
            text = ""
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            return text
        except Exception as e:
            logger.error(f"Error extracting PDF: {e}")
            return ""
    
    def _chunk_text(self, text, chunk_size=1000, overlap=200):
        chunks = []
        start = 0
        text_length = len(text)
        
        while start < text_length:
            end = min(start + chunk_size, text_length)
            
            # Try to break at sentence
            if end < text_length:
                for sep in ['. ', '? ', '! ']:
                    pos = text.rfind(sep, start, end)
                    if pos > start:
                        end = pos + len(sep)
                        break
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            start = end - overlap if end < text_length else text_length
        
        return chunks
    
    def verify_data(self):
        """Verify all data was loaded"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        tables = ['accounts', 'orders', 'tickets', 'documents']
        logger.info("\n📊 Data Verification:")
        
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            logger.info(f"  {table}: {count} records")
        
        # Check vector store
        count = self.vector_store.collection.count()
        logger.info(f"  🧠 Vector store: {count} chunks")
        
        conn.close()

# Run the loader
if __name__ == "__main__":
    loader = DataLoader()
    
    # Load Excel
    loader.load_excel("data/excel/ParcelPilot_Assessment_Data.xlsx")
    
    # Load PDFs
    loader.load_pdfs("data/pdfs")
    
    # Verify
    loader.verify_data()
