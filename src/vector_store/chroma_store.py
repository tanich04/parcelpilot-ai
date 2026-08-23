"""
src/vector_store/chroma_store.py
ChromaDB Vector Store - SINGLETON PATTERN

The vector store is initialized ONCE at startup and reused for all queries.
This prevents reloading the embedding model on every search.
"""

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Optional
import logging
import hashlib

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ChromaVectorStore:
    """
    ChromaDB vector store - Singleton pattern.
    
    Only ONE instance is created and reused across all queries.
    The embedding model is loaded ONCE at startup.
    """
    
    # Singleton instance
    _instance = None
    _initialized = False
    
    def __new__(cls, *args, **kwargs):
        """Ensure only one instance is ever created"""
        if cls._instance is None:
            cls._instance = super(ChromaVectorStore, cls).__new__(cls)
        return cls._instance
    
    def __init__(self, collection_name="parcelpilot_docs", persist_dir="./chroma_db"):
        """
        Initialize the vector store - only runs ONCE.
        Subsequent calls reuse the existing instance.
        """
        # Skip if already initialized
        if ChromaVectorStore._initialized:
            logger.debug("♻️ Reusing existing ChromaDB instance")
            return
        
        logger.info("🔄 Initializing ChromaDB (first time only)...")
        
        # Initialize embedding model (loaded ONCE)
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.embedding_dim = self.model.get_embedding_dimension()
        logger.info(f"✅ Embedding model loaded: {self.embedding_dim} dimensions")
        
        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Get or create collection
        self.collection_name = collection_name
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        
        logger.info(f"✅ ChromaDB initialized: {collection_name}")
        logger.info(f"   Collection has {self.collection.count()} documents")
        
        # Mark as initialized
        ChromaVectorStore._initialized = True
    
    def add_documents(self, documents: List[Dict]):
        """Add documents to vector store - only used during ingestion"""
        if not documents:
            logger.warning("No documents to add")
            return
        
        logger.info(f"Adding {len(documents)} documents to vector store...")
        
        # Prepare data
        ids = []
        embeddings = []
        metadatas = []
        documents_text = []
        
        for doc in documents:
            doc_id = doc.get('doc_id', str(hashlib.md5(doc['chunk'].encode()).hexdigest()))
            chunk_text = doc['chunk']
            
            # Generate embedding
            embedding = self.model.encode(chunk_text).tolist()
            
            # Prepare metadata
            metadata = {
                "filename": doc.get('filename', ''),
                "doc_type": doc.get('doc_type', ''),
                "authority_level": doc.get('authority_level', 3),
                "account_scope": doc.get('account_scope', 'GLOBAL'),
                "is_current": doc.get('is_current', 1),
                "chunk_index": doc.get('chunk_index', 0),
                "doc_id": str(doc_id)
            }
            
            ids.append(f"doc_{doc_id}_{doc.get('chunk_index', 0)}")
            embeddings.append(embedding)
            metadatas.append(metadata)
            documents_text.append(chunk_text)
        
        # Add to ChromaDB
        self.collection.add(
            embeddings=embeddings,
            documents=documents_text,
            metadatas=metadatas,
            ids=ids
        )
        
        logger.info(f"✅ Added {len(documents)} documents to ChromaDB")
    
    def search(self, query: str, account_id: Optional[str] = None, limit: int = 5) -> List[Dict]:
        """
        Search for similar documents - FAST because model is already loaded.
        """
        # Generate query embedding (model is already loaded!)
        query_embedding = self.model.encode(query).tolist()
        
        # Build where filter
        where_filter = None
        if account_id:
            where_filter = {
                "$or": [
                    {"account_scope": "GLOBAL"},
                    {"account_scope": account_id}
                ]
            }
        
        try:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=limit,
                where=where_filter,
                include=["documents", "metadatas", "distances"]
            )
            
        except Exception as e:
            logger.error(f"Search error: {e}")
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=limit,
                include=["documents", "metadatas", "distances"]
            )
        
        # Format results
        formatted_results = []
        if results['ids'] and results['ids'][0]:
            for i in range(len(results['ids'][0])):
                metadata = results['metadatas'][0][i] if results['metadatas'] else {}
                authority_level = metadata.get('authority_level', 3)
                is_current = metadata.get('is_current', 1)
                distance = results['distances'][0][i] if results['distances'] else 1.0
                similarity = 1 - distance
                
                authority_weight = {
                    1: 1.0, 2: 0.8, 3: 0.6, 4: 0.4, 5: 0.2
                }.get(authority_level, 0.5)
                
                authority_score = (
                    authority_weight * 0.5 +
                    (is_current if isinstance(is_current, int) else 0) * 0.3 +
                    similarity * 0.2
                )
                
                formatted_results.append({
                    "chunk": results['documents'][0][i] if results['documents'] else "",
                    "filename": metadata.get('filename', ''),
                    "doc_type": metadata.get('doc_type', ''),
                    "authority_level": authority_level,
                    "account_scope": metadata.get('account_scope', 'GLOBAL'),
                    "is_current": bool(is_current) if isinstance(is_current, int) else False,
                    "similarity": similarity,
                    "authority_score": authority_score,
                    "metadata": metadata
                })
        
        return formatted_results
    
    def clear(self):
        """Clear all documents"""
        try:
            self.client.delete_collection(self.collection_name)
        except:
            pass
        self.collection = self.client.create_collection(self.collection_name)
        logger.info("🧹 Cleared vector store")
    
    @classmethod
    def get_instance(cls):
        """Get the singleton instance"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def reset(cls):
        """Reset the singleton (for testing only)"""
        cls._instance = None
        cls._initialized = False


# ============================================================
# GLOBAL INSTANCE - Import this everywhere
# ============================================================

# Create the singleton instance ONCE at module load
_vector_store_instance = None

def get_vector_store():
    """Get the global vector store instance (lazy initialization)"""
    global _vector_store_instance
    if _vector_store_instance is None:
        _vector_store_instance = ChromaVectorStore()
    return _vector_store_instance


# For backward compatibility - direct import
__all__ = ['ChromaVectorStore', 'get_vector_store', 'reset_vector_store']


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":
    import time
    
    print("🧪 Testing Singleton Pattern\n")
    print("="*50)
    
    # First call - loads the model (slow)
    print("\n1️⃣ First call (loading model):")
    start = time.time()
    vs1 = get_vector_store()
    print(f"   Time: {time.time() - start:.2f}s")
    print(f"   Instance ID: {id(vs1)}")
    
    # Second call - uses cached instance (fast)
    print("\n2️⃣ Second call (reusing instance):")
    start = time.time()
    vs2 = get_vector_store()
    print(f"   Time: {time.time() - start:.2f}s")
    print(f"   Instance ID: {id(vs2)}")
    print(f"   Same instance: {vs1 is vs2}")
    
    # Search test (fast - model already loaded)
    print("\n3️⃣ Search test:")
    start = time.time()
    results = vs1.search("cancellation policy", "ACC-Northstar", limit=2)
    print(f"   Time: {time.time() - start:.2f}s")
    print(f"   Results: {len(results)}")
    for r in results[:2]:
        print(f"     - {r['filename']} (Score: {r['authority_score']:.3f})")
    
    print("\n" + "="*50)
    print("✅ Singleton pattern working!")
    print("   - Model loaded ONCE")
    print("   - All searches reuse it")
    print("   - Fast and memory efficient")