"""
src/tools/doc_search.py
Document Search - Simplified for targeted searches
"""

import sys
import os
import logging
from typing import Optional, List, Dict

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.vector_store.chroma_store import get_vector_store

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def search_document_by_name(filename: str, query: str) -> List[Dict]:
    """
    Search a specific document by filename.
    This is the efficient version - only one document, one search.
    """
    
    vs = get_vector_store()
    
    results = vs.collection.query(
        query_embeddings=[vs.model.encode(query).tolist()],
        n_results=3,
        where={"filename": filename},
        include=["documents", "metadatas", "distances"]
    )
    
    documents = []
    if results['ids'] and results['ids'][0]:
        for i in range(len(results['ids'][0])):
            documents.append({
                "chunk": results['documents'][0][i],
                "filename": results['metadatas'][0][i].get('filename', filename),
                "authority_level": results['metadatas'][0][i].get('authority_level', 1)
            })
    
    return documents


def search_documents(query: str, account_id: Optional[str] = None) -> str:
    """
    Legacy search - kept for backward compatibility.
    New code should use the router pattern.
    """
    
    try:
        logger.info(f"🔍 Document Search: '{query}'")
        vs = get_vector_store()
        results = vs.search(query, account_id=account_id, limit=3)
        
        if not results:
            return "No documents found."
        
        response = "📄 **Document Search Results:**\n\n"
        for i, r in enumerate(results, 1):
            response += f"**{i}. {r['filename']}**\n"
            response += f"   Score: {r['authority_score']:.3f}\n"
            response += f"   {r['chunk'][:300]}...\n\n"
        
        return response
        
    except Exception as e:
        logger.error(f"Error in document search: {e}")
        return f"Error: {str(e)}"