"""
src/agent/graph.py
Efficient Agent Graph - Uses router to reduce LLM calls
Supports confirmation flow for staged actions
"""

import sys
import os
import json
from typing import Dict, Any, Optional, Literal
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import SystemMessage, AIMessage, HumanMessage
from langchain_groq import ChatGroq

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.agent.state import AgentState, create_initial_state
from src.agent.router import IntentRouter, build_llm_context
from src.agent.prompts import SYSTEM_PROMPT, INTERNAL_PROMPT
from src.tools.action_tools import stage_action, execute_action

from dotenv import load_dotenv
load_dotenv()

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_llm():
    """Get Groq LLM without tool bindings (router does the work)"""
    groq_api_key = os.getenv("GROQ_API_KEY")
    if not groq_api_key:
        raise ValueError("GROQ_API_KEY not found")
    
    return ChatGroq(
        temperature=0.1,
        model="openai/gpt-oss-120b",
        api_key=groq_api_key,
        max_tokens=2000,
        max_retries=2
    )


def call_agent(state: AgentState) -> Dict[str, Any]:
    """
    Agent node - uses router for efficient context building.
    Handles confirmation flow for staged actions.
    """
    
    logger.info("🧠 Agent node: Processing with router...")
    
    # Get the last user message
    messages = state.get("messages", [])
    user_message = None
    for msg in reversed(messages):
        if hasattr(msg, 'type') and msg.type == 'human':
            user_message = msg.content
            break
    
    if not user_message:
        return {"messages": [AIMessage(content="I didn't receive a question. Please try again.")]}
    
    # Get user context
    user_context = state.get("user_context", {})
    account_id = user_context.get("account_id")
    role = user_context.get("role", "customer")
    account_scope = user_context.get("account_scope", "single")
    account_name = user_context.get("account_name")
    
    logger.info(f"📋 Context: Role={role}, Scope={account_scope}, Account={account_id}")
    
    # ============================================================
    # ✅ STEP 1: Check if this is a confirmation/rejection
    # ============================================================
    
    query_lower = user_message.lower()
    is_confirmation = any(word in query_lower for word in ["okay", "ok", "yes", "yeah", "yep", "sure", "go ahead", "proceed", "confirm", "approve", "do it"])
    is_rejection = any(word in query_lower for word in ["no", "not", "cancel", "stop", "reject", "decline", "don't", "dont"])
    
    # Check if there's a staged action
    staged_action = state.get("staged_action")
    
    if staged_action and is_confirmation:
        logger.info(f"✅ Confirmation detected! Executing staged action: {staged_action.get('action_type')}")
        state["action_approved"] = True
        return execute_action_node(state)
    
    if staged_action and is_rejection:
        logger.info("❌ Rejection detected! Cancelling staged action")
        state["staged_action"] = None
        state["requires_approval"] = False
        state["action_approved"] = False
        return {
            "messages": [AIMessage(content="✅ Action cancelled. No changes were made.")],
            "staged_action": None,
            "requires_approval": False,
            "action_approved": False
        }
    
    # ============================================================
    # ✅ STEP 2: Route the query using the router
    # ============================================================
    
    router = IntentRouter()
    router_result = router.route(user_message, account_id, role, account_scope)
    intent = router_result.get("intent")
    entities = router_result.get("entities", {})
    context = router_result.get("context", {})
    
    logger.info(f"🎯 Intent: {intent}, Entities: {entities}")
    
    # ============================================================
    # ✅ STEP 3: Handle action intents directly
    # ============================================================
    
    # Check if this is an escalation request
    if intent == "escalate_ticket" and entities.get("ticket_id"):
        ticket_id = entities["ticket_id"]
        action_result = stage_action(
            action_type="escalate_ticket",
            reasoning=f"User requested escalation of {ticket_id}",
            payload={"ticket_id": ticket_id, "priority": "P1"},
            ticket_id=ticket_id
        )
        state["staged_action"] = action_result
        state["requires_approval"] = True
        
        response = f"""
⚠️ **Action Staged for Approval**

I have prepared the escalation of **{ticket_id}** to P1.

**Reasoning:** User requested escalation.

**Details:**
- Ticket: {ticket_id}
- New Priority: P1
- Account: {account_name or account_id}

Please confirm if you want to proceed by saying **"yes"** or **"okay"**.
"""
        return {"messages": [AIMessage(content=response)]}
    
    # Check if this is a cancellation request
    if intent == "cancellation_check" and entities.get("order_id"):
        order_id = entities["order_id"]
        # Check if order is eligible (from context)
        order_data = context.get("data", {}).get("order", {})
        if order_data and order_data.get("status") in ["DRAFT", "BOOKED"]:
            # Check if contract allows free cancellation
            documents = context.get("documents", [])
            contract_waives_fee = any(
                "waive" in doc.get("chunk", "").lower() or 
                "without fee" in doc.get("chunk", "").lower()
                for doc in documents
            )
            
            if contract_waives_fee:
                action_result = stage_action(
                    action_type="cancel_order",
                    reasoning=f"User requested cancellation of {order_id} - contract waives fee",
                    payload={"order_id": order_id, "account_id": account_id, "reason": "Contract waiver"}
                )
                state["staged_action"] = action_result
                state["requires_approval"] = True
                
                response = f"""
⚠️ **Action Staged for Approval**

I have prepared the cancellation of **{order_id}**.

**Reasoning:** Your contract waives cancellation fees for orders in BOOKED status.

**Details:**
- Order: {order_id}
- Status: {order_data.get('status')}
- Fee: ₹0 (waived by contract)

Please confirm if you want to proceed by saying **"yes"** or **"okay"**.
"""
                return {"messages": [AIMessage(content=response)]}
    
    # ============================================================
    # ✅ STEP 4: Build context and get LLM answer (NO TOOLS)
    # ============================================================
    
    context_text = build_llm_context(router_result, user_message)
    
    # Get LLM (without tool bindings)
    llm = get_llm()
    
    # Build system prompt based on role
    if role == "internal":
        base_prompt = SYSTEM_PROMPT + "\n\n" + INTERNAL_PROMPT
    else:
        base_prompt = SYSTEM_PROMPT
    
    # Add role-specific guidance
    if role == "internal" and account_scope == "all":
        role_guidance = """
🌐 **ALL ACCOUNTS VIEW**
You have access to ALL customer data. Provide cross-account insights.
Focus on patterns, SLA breaches, and operational recommendations.
"""
    elif role == "internal":
        role_guidance = """
🛠️ **INTERNAL STAFF VIEW**
You can see all data for this specific account.
Provide detailed investigation and analysis.
"""
    else:
        role_guidance = f"""
👤 **CUSTOMER VIEW**
You are helping a customer. Only show data for their account ({account_name or account_id}).
Protect their privacy and provide clear, actionable answers.
"""
    
    system_prompt = f"""
{base_prompt}

{role_guidance}

**IMPORTANT:** 
- You have been given ALL necessary information below.
- Do NOT call any tools - the data has already been retrieved.
- Provide a clear, direct answer based on the context.
- Cite your sources and explain your reasoning.
"""

    full_prompt = f"""
{system_prompt}

{context_text}

**Response:** Provide a clear, direct answer to the user's question.
"""
    
    # Call LLM
    try:
        response = llm.invoke(full_prompt)
        logger.info(f"📝 LLM Response: {response.content[:100]}...")
        return {"messages": [AIMessage(content=response.content)]}
    except Exception as e:
        logger.error(f"LLM Error: {e}")
        return {
            "messages": [AIMessage(
                content=f"⚠️ I encountered an error: {str(e)}. Please try again."
            )]
        }


def execute_action_node(state: AgentState) -> Dict[str, Any]:
    """Execute the approved staged action"""
    
    logger.info("⚡ Executing approved action...")
    
    staged_action = state.get("staged_action")
    
    if not staged_action:
        return {
            "messages": [AIMessage(content="❌ No action to execute.")],
            "staged_action": None,
            "requires_approval": False
        }
    
    try:
        result = execute_action(staged_action)
        
        return {
            "messages": [AIMessage(content=f"✅ {result.get('message', 'Action executed successfully!')}")],
            "staged_action": None,
            "requires_approval": False,
            "action_approved": True
        }
    except Exception as e:
        logger.error(f"Error executing action: {e}")
        return {
            "messages": [AIMessage(content=f"❌ Error executing action: {str(e)}")],
            "staged_action": None,
            "requires_approval": False
        }


def should_continue(state: AgentState) -> Literal["execute_action", "end"]:
    """Decide what to do next"""
    
    if state.get("action_approved") and state.get("staged_action"):
        logger.info("🔀 Routing to execute_action")
        return "execute_action"
    
    logger.info("🔀 Routing to end")
    return "end"


def build_agent_graph():
    """Build the efficient agent graph"""
    
    workflow = StateGraph(AgentState)
    
    workflow.add_node("agent", call_agent)
    workflow.add_node("execute_action", execute_action_node)
    
    workflow.set_entry_point("agent")
    
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "execute_action": "execute_action",
            "end": END
        }
    )
    
    workflow.add_edge("execute_action", END)
    
    memory = MemorySaver()
    graph = workflow.compile(checkpointer=memory)
    
    logger.info("✅ Efficient Agent Graph built!")
    return graph


class AgentRunner:
    """Simplified runner with role support"""
    
    def __init__(self):
        self.graph = build_agent_graph()
        self.threads = {}
    
    def run(self, message: str, account_id: Optional[str] = None, 
            role: str = "customer", account_name: str = None, 
            account_scope: str = "single") -> Dict[str, Any]:
        """Run the agent with role-based access"""
        import uuid
        thread_id = str(uuid.uuid4())
        
        user_context = {
            "account_id": account_id,
            "account_name": account_name or account_id or "All Accounts",
            "role": role,
            "account_scope": account_scope
        }
        
        state = create_initial_state(
            account_id=account_id or "ALL",
            account_name=account_name or "All Accounts",
            role=role,
            initial_message=message
        )
        state["user_context"]["account_scope"] = account_scope
        
        self.threads[thread_id] = {
            "state": state,
            "config": {"configurable": {"thread_id": thread_id}}
        }
        
        return self._run_graph(thread_id)
    
    def _run_graph(self, thread_id: str):
        thread = self.threads[thread_id]
        config = thread["config"]
        
        events = self.graph.stream(thread["state"], config, stream_mode="updates")
        
        for event in events:
            pass
        
        final_state = self.graph.get_state(config)
        thread["state"] = final_state.values
        
        messages = final_state.values.get("messages", [])
        last_message = messages[-1] if messages else None
        
        return {
            "thread_id": thread_id,
            "response": last_message.content if last_message else "No response",
            "requires_approval": final_state.values.get("requires_approval", False),
            "staged_action": final_state.values.get("staged_action"),
            "execution_result": final_state.values.get("execution_result")
        }
    
    def resume(self, thread_id: str, decision: str, feedback: str = ""):
        """Resume after approval (for API compatibility)"""
        if thread_id not in self.threads:
            return {"error": f"Thread {thread_id} not found"}
        
        thread = self.threads[thread_id]
        
        # Update state with decision
        if decision == "yes":
            thread["state"]["action_approved"] = True
        else:
            thread["state"]["action_approved"] = False
            thread["state"]["staged_action"] = None
            thread["state"]["requires_approval"] = False
        
        # Re-run the graph
        config = thread["config"]
        events = self.graph.stream(thread["state"], config, stream_mode="updates")
        
        for event in events:
            pass
        
        final_state = self.graph.get_state(config)
        thread["state"] = final_state.values
        
        messages = final_state.values.get("messages", [])
        last_message = messages[-1] if messages else None
        
        return {
            "thread_id": thread_id,
            "response": last_message.content if last_message else "No response",
            "requires_approval": False,
            "execution_result": final_state.values.get("execution_result")
        }