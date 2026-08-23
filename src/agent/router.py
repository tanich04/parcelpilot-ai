"""
src/agent/router.py
Intelligent Router - Parses intent and builds context without excessive LLM calls
"""
import os
import re
import sqlite3
from typing import Dict, Any, Optional, Tuple, List
from src.tools.doc_search import search_documents
from src.vector_store.chroma_store import get_vector_store
from src.agent.prompts import SYSTEM_PROMPT
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage


class IntentRouter:
    """
    Routes queries intelligently without multiple LLM calls.
    Extracts entities, looks up data, and builds context.
    Supports both single-account (customer) and cross-account (internal) views.
    """
    
    def __init__(self):
        self.db_path = os.environ.get("DB_PATH", "parcelpilot.db")
        print(f"🔍 Router using database at: {self.db_path}")
    
    def route(self, query: str, account_id: Optional[str] = None, 
              role: str = "customer", account_scope: str = "single") -> Dict[str, Any]:
        """
        Route the query to the appropriate handler.
        
        Args:
            query: The user's question
            account_id: Account ID (None for internal "All Accounts" view)
            role: "customer" or "internal"
            account_scope: "single" or "all"
        
        Returns:
            Dict with intent, entities, and context
        """
        
        # Step 1: Detect intent and extract entities
        intent, entities = self._detect_intent(query)
        
        # Step 2: Look up data based on intent and role
        context = self._build_context(intent, entities, account_id, role, account_scope)
        
        return {
            "intent": intent,
            "entities": entities,
            "context": context,
            "role": role,
            "account_scope": account_scope
        }
    
    def _detect_intent(self, query: str) -> Tuple[str, Dict[str, Any]]:
        """Detect intent and extract entities using regex patterns"""
        
        entities = {}
        query_lower = query.lower()
        
        # Extract order ID
        order_match = re.search(r'(ORD-\d+)', query, re.IGNORECASE)
        if order_match:
            entities['order_id'] = order_match.group(1).upper()
        
        # Extract account name
        account_names = ["Northstar", "LumenWorks", "Beacon", "Axis"]
        for name in account_names:
            if name.lower() in query_lower:
                entities['account_name'] = name
                break
        
        # Extract account ID
        account_match = re.search(r'(ACCT-\d+)', query, re.IGNORECASE)
        if account_match:
            entities['account_id'] = account_match.group(1).upper()
        
        # Extract ticket ID
        ticket_match = re.search(r'(TKT-\d+)', query, re.IGNORECASE)
        if ticket_match:
            entities['ticket_id'] = ticket_match.group(1).upper()
        
        # ============================================================
        # INTENT DETECTION - Check in order of SPECIFICITY
        # ============================================================
        
        # ✅ FIX: Check confirmation FIRST (before SLA check)
        if any(word in query_lower for word in ["yes", "approve", "confirm", "proceed", "go ahead", "ok", "okay"]):
            intent = "confirm_action"
            return intent, entities
        
        # Check rejection
        if any(word in query_lower for word in ["no", "not", "cancel", "stop", "reject", "decline", "don't", "dont"]):
            intent = "reject_action"
            return intent, entities
        
        # Priority 1: SLA check (MUST come before P1/P2/P3 detection)
        if any(word in query_lower for word in ["sla", "response time", "response-time", "service level"]):
            intent = "sla_check"
        
        # Priority 2: Escalation
        elif any(word in query_lower for word in ["escalate", "priority", "p1", "p2", "p3"]) and \
           any(word in query_lower for word in ["ticket", "issue", "case"]):
            intent = "escalate_ticket"
        
        # Priority 3: Cancellation
        elif any(word in query_lower for word in ["cancel", "cancellation", "fee", "waive", "waiver"]):
            intent = "cancellation_check"
        
        # Priority 4: Service Credit
        elif any(word in query_lower for word in ["credit", "late", "delay", "refund", "compensation"]):
            intent = "service_credit_check"
        
        # Priority 5: Order Status
        elif any(word in query_lower for word in ["status", "where", "track", "progress", "location"]):
            intent = "order_status"
        
        # Priority 6: Account Info
        elif any(word in query_lower for word in ["account", "plan", "csm", "customer success"]):
            intent = "account_info"
        
        # Priority 7: Known Issues
        elif any(word in query_lower for word in ["known issue", "bug", "problem", "error", "fail", "broken"]):
            intent = "known_issues"
        
        # Priority 8: Cross-account analytics (internal only)
        elif any(word in query_lower for word in ["all accounts", "across all", "cross-account", "all tickets", "all orders", "overview", "summary"]):
            intent = "cross_account_analytics"
        
        # Default
        else:
            intent = "general_query"
        
        return intent, entities
    
    def _build_context(self, intent: str, entities: Dict, 
                       account_id: Optional[str], role: str, account_scope: str) -> Dict:
        """Build context by looking up data based on intent and role"""
        
        context = {
            "account_id": account_id,
            "intent": intent,
            "data": {},
            "documents": [],
            "role": role,
            "account_scope": account_scope
        }
        print("=" * 60)
        print("DB PATH:", self.db_path)
        print("Exists:", os.path.exists(self.db_path))
        print("Directory exists:", os.path.exists(os.path.dirname(self.db_path)))
        print("Files in directory:")
        print(os.listdir(os.path.dirname(self.db_path)))
        print("=" * 60)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # ============================================================
        # INTERNAL: ALL ACCOUNTS VIEW
        # ============================================================
        if role == "internal" and account_scope == "all":
            context["data"]["all_accounts"] = True
            
            # Get ALL accounts
            cursor.execute("""
                SELECT account_id, account_name, plan, contract_file, premium_support
                FROM accounts
            """)
            accounts = cursor.fetchall()
            context["data"]["accounts"] = [
                {
                    "id": a[0],
                    "name": a[1],
                    "plan": a[2],
                    "contract_file": a[3],
                    "premium_support": bool(a[4]) if a[4] else False
                }
                for a in accounts
            ]
            
            # If cross-account analytics, get aggregated data
            if intent in ["cross_account_analytics", "sla_check", "known_issues"]:
                # Get all orders
                cursor.execute("""
                    SELECT account_id, COUNT(*) as count, status
                    FROM orders
                    GROUP BY account_id, status
                """)
                order_summary = cursor.fetchall()
                context["data"]["order_summary"] = order_summary
                
                # Get all tickets
                cursor.execute("""
                    SELECT account_id, COUNT(*) as count, status
                    FROM tickets
                    GROUP BY account_id, status
                """)
                ticket_summary = cursor.fetchall()
                context["data"]["ticket_summary"] = ticket_summary
                
                # Check SLA breaches across accounts
                cursor.execute("""
                    SELECT account_id, COUNT(*) as count
                    FROM tickets
                    WHERE status = 'open' AND created_at < datetime('now', '-4 hours')
                    GROUP BY account_id
                """)
                sla_breaches = cursor.fetchall()
                context["data"]["sla_breaches"] = [
                    {"account_id": s[0], "breached_count": s[1]}
                    for s in sla_breaches
                ]
        
        # ============================================================
        # SINGLE ACCOUNT VIEW (Customer OR Internal focusing on one)
        # ============================================================
        else:
            # Get account info for specific account
            if account_id:
                cursor.execute("""
                    SELECT account_id, account_name, plan, contract_file, premium_support
                    FROM accounts
                    WHERE account_id = ?
                """, (account_id,))
                account = cursor.fetchone()
                
                if account:
                    context["data"]["account"] = {
                        "id": account[0],
                        "name": account[1],
                        "plan": account[2],
                        "contract_file": account[3],
                        "premium_support": bool(account[4]) if account[4] else False
                    }
            
            # Handle specific intent
            if intent in ["cancellation_check", "service_credit_check", "order_status"]:
                order_id = entities.get('order_id')
                if order_id and account_id:
                    cursor.execute("""
                        SELECT 
                            o.order_id, o.status, o.carrier, o.booked_at,
                            o.pickup_window_start, o.pickup_window_end,
                            o.pickup_actual_at, o.shipment_fee_inr,
                            o.carrier_fault, o.customer_fault,
                            o.cancellation_requested_at, o.notes
                        FROM orders o
                        WHERE o.order_id = ? AND o.account_id = ?
                    """, (order_id, account_id))
                    order = cursor.fetchone()
                    
                    if order:
                        context["data"]["order"] = {
                            "id": order[0],
                            "status": order[1],
                            "carrier": order[2],
                            "booked_at": order[3],
                            "pickup_window_start": order[4],
                            "pickup_window_end": order[5],
                            "pickup_actual_at": order[6],
                            "shipment_fee": order[7],
                            "carrier_fault": bool(order[8]),
                            "customer_fault": bool(order[9]),
                            "cancellation_requested": bool(order[10]),
                            "notes": order[11]
                        }
        
        # ============================================================
        # DOCUMENT SEARCH (based on intent)
        # ============================================================
        
        # ❌ REMOVED: The broken confirmation code
        # if intent == "confirm_action" and state.get("staged_action"):
        #     state["action_approved"] = True
        #     return "execute_action"
        
        # For cancellation, find the specific contract document
        if intent == "cancellation_check":
            account_data = context["data"].get("account", {})
            if account_data and account_data.get("contract_file"):
                contract_file = account_data["contract_file"]
                context["documents"] = self._search_contract(contract_file, "cancellation fee")
            # If no contract or internal all-accounts view, search general policies
            if not context["documents"]:
                context["documents"] = self._search_document("03_Cancellation_and_Service_Credit_SOP_v4.pdf", "cancellation")
        
        # For service credit, find SOP document
        elif intent == "service_credit_check":
            context["documents"] = self._search_document("03_Cancellation_and_Service_Credit_SOP_v4.pdf", "service credit")
        
        # For SLA check, find support policy
        elif intent == "sla_check":
            context["documents"] = self._search_document("01_Support_Policy_v3_CURRENT.pdf", "SLA response time")
            # Also check if account has premium support
            account_data = context["data"].get("account", {})
            if account_data and account_data.get("premium_support"):
                context["data"]["premium_support"] = True
        
        # For known issues, find product guide
        elif intent == "known_issues":
            context["documents"] = self._search_document("04_Product_Operations_Guide_and_Known_Issues.pdf", "known issues")
        
        conn.close()
        
        return context
    
    def _search_contract(self, filename: str, topic: str) -> list:
        """Search a specific contract document for a topic"""
        
        vs = get_vector_store()
        
        # Search with filename filter
        try:
            results = vs.collection.query(
                query_embeddings=[vs.model.encode(topic).tolist()],
                n_results=3,
                where={"filename": filename},
                include=["documents", "metadatas", "distances"]
            )
        except:
            # If no results, search globally
            global_results = vs.search(topic, limit=2)
            return [
                {
                    "chunk": r['chunk'],
                    "filename": r['filename'],
                    "authority_level": r['authority_level']
                }
                for r in global_results
            ]
        
        documents = []
        if results['ids'] and results['ids'][0]:
            for i in range(len(results['ids'][0])):
                documents.append({
                    "chunk": results['documents'][0][i],
                    "filename": results['metadatas'][0][i].get('filename', filename),
                    "authority_level": 1  # Contract
                })
        
        # If no results, search globally for the topic
        if not documents:
            global_results = vs.search(topic, limit=2)
            documents = [
                {
                    "chunk": r['chunk'],
                    "filename": r['filename'],
                    "authority_level": r['authority_level']
                }
                for r in global_results
            ]
        
        return documents
    
    def _search_document(self, filename: str, topic: str) -> list:
        """Search a specific document for a topic"""
        
        vs = get_vector_store()
        
        try:
            results = vs.collection.query(
                query_embeddings=[vs.model.encode(topic).tolist()],
                n_results=3,
                where={"filename": filename},
                include=["documents", "metadatas", "distances"]
            )
        except:
            global_results = vs.search(topic, limit=2)
            return [
                {
                    "chunk": r['chunk'],
                    "filename": r['filename'],
                    "authority_level": r['authority_level']
                }
                for r in global_results
            ]
        
        documents = []
        if results['ids'] and results['ids'][0]:
            for i in range(len(results['ids'][0])):
                documents.append({
                    "chunk": results['documents'][0][i],
                    "filename": results['metadatas'][0][i].get('filename', filename),
                    "authority_level": 2  # SOP/Guide
                })
        
        return documents


def build_llm_context(router_result: Dict[str, Any], query: str) -> str:
    """
    Build a focused context for the LLM based on router results.
    Supports both single-account and cross-account contexts.
    """
    
    context = router_result.get("context", {})
    intent = router_result.get("intent", "general_query")
    data = context.get("data", {})
    documents = context.get("documents", [])
    role = router_result.get("role", "customer")
    account_scope = router_result.get("account_scope", "single")
    account = data.get("account", {})
    order = data.get("order", {})
    
    # Build focused context
    context_text = f"""
**User Question:** {query}

**Intent:** {intent}
**Role:** {role}
**Account Scope:** {account_scope}

"""
    
    # ============================================================
    # INTERNAL: ALL ACCOUNTS VIEW
    # ============================================================
    if role == "internal" and account_scope == "all":
        context_text += """
**🌐 ALL ACCOUNTS VIEW**
You have access to ALL customer data. Provide cross-account analytics and insights.

"""
        
        accounts = data.get("accounts", [])
        if accounts:
            context_text += "**All Accounts:**\n"
            for a in accounts:
                context_text += f"- {a['name']} ({a['id']}) | Plan: {a['plan']} | Premium: {'Yes' if a.get('premium_support') else 'No'}\n"
            context_text += "\n"
        
        # Show SLA breaches
        breaches = data.get("sla_breaches", [])
        if breaches:
            context_text += "**⚠️ SLA Breaches:**\n"
            for b in breaches:
                context_text += f"- {b['account_id']}: {b['breached_count']} tickets\n"
            context_text += "\n"
        
        # Show order summary
        order_summary = data.get("order_summary", [])
        if order_summary:
            context_text += "**Order Summary by Account:**\n"
            for o in order_summary:
                context_text += f"- {o[0]}: {o[1]} orders ({o[2]})\n"
            context_text += "\n"
        
        # Show ticket summary
        ticket_summary = data.get("ticket_summary", [])
        if ticket_summary:
            context_text += "**Ticket Summary by Account:**\n"
            for t in ticket_summary:
                context_text += f"- {t[0]}: {t[1]} tickets ({t[2]})\n"
            context_text += "\n"
        
        context_text += """
**Your Task:**
Provide a comprehensive, cross-account analysis. Highlight patterns, issues, and recommendations.
Focus on operational insights that help the support team prioritize work.
"""
    
    # ============================================================
    # SINGLE ACCOUNT VIEW
    # ============================================================
    else:
        if account:
            context_text += f"""
**Account Information:**
- Account: {account.get('name', 'Unknown')} ({account.get('id', 'N/A')})
- Plan: {account.get('plan', 'Standard')}
- Contract: {account.get('contract_file', 'None on file')}
- Premium Support: {'Yes' if account.get('premium_support') else 'No'}

"""
        
        if order:
            context_text += f"""
**Order Information:**
- Order ID: {order.get('id')}
- Status: {order.get('status')}
- Carrier: {order.get('carrier')}
- Booked At: {order.get('booked_at')}
- Pickup Window: {order.get('pickup_window_start')} to {order.get('pickup_window_end')}
- Pickup Actual: {order.get('pickup_actual_at') or 'Not yet picked up'}
- Carrier Fault: {'Yes' if order.get('carrier_fault') else 'No'}
- Customer Fault: {'Yes' if order.get('customer_fault') else 'No'}
- Cancellation Requested: {'Yes' if order.get('cancellation_requested') else 'No'}

"""
    
    # ============================================================
    # INTENT-SPECIFIC GUIDANCE
    # ============================================================
    
    if intent == "cancellation_check":
        context_text += """
**Cancellation Evaluation:**
- Order status determines eligibility
- Customer contracts (Level 1) override SOPs and policies
- DRAFT/BOOKED = eligible, PICKED_UP = not eligible
"""
    
    if intent == "service_credit_check":
        context_text += """
**Service Credit Evaluation:**
- Check if carrier_fault is Yes
- 3+ hours late = 50% credit, 6+ hours = 100% credit
- Customer contract may override SOP terms
"""
    
    if intent == "sla_check":
        context_text += """
**SLA Evaluation:**
- P1: Response within 1 hour
- P2: Response within 4 hours  
- P3: Response within 8 hours
- Premium Support may have faster response times
"""
    
    if intent == "escalate_ticket":
        context_text += """
**Escalation Request:**
- This is a state-changing action
- Must stage and ask for confirmation
- DO NOT escalate without user approval
"""
    
    if intent == "cross_account_analytics":
        context_text += """
**Cross-Account Analytics:**
- Identify patterns across accounts
- Flag SLA breaches, recurring issues
- Provide operational insights
"""
    
    # ============================================================
    # DOCUMENTS
    # ============================================================
    
    if documents:
        context_text += "\n**Relevant Documents:**\n"
        for i, doc in enumerate(documents[:2], 1):
            authority_label = "Contract (Level 1 - Highest)" if doc.get('authority_level') == 1 else "SOP/Guide (Level 2)"
            context_text += f"\nDocument {i}: {doc.get('filename')} [{authority_label}]\n"
            context_text += f"  {doc.get('chunk', '')[:500]}...\n"
    
    return context_text
