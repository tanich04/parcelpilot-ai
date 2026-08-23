"""
src/agent/state.py
Agent State Management - The Memory System

This defines what the agent remembers during a conversation:
- Chat history (short-term memory)
- User context (entity memory)  
- Pending actions (action memory)
- Execution status (state memory)
"""

from typing import Annotated, Sequence, Optional, Dict, Any
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict
import json
from datetime import datetime


class AgentState(TypedDict):
    """
    The complete memory state of our agent.
    
    This is like the agent's "working memory" - everything it remembers
    about the current conversation and user.
    """
    
    # ============================================================
    # SHORT-TERM MEMORY: Everything said in this conversation
    # ============================================================
    # The 'add_messages' annotation tells LangGraph to automatically
    # append new messages to the list instead of replacing them.
    messages: Annotated[Sequence[BaseMessage], add_messages]
    
    # ============================================================
    # ENTITY MEMORY: Who is the user and what do we know about them?
    # ============================================================
    user_context: Dict[str, Any]
    """
    Stores information about the current user:
    {
        "account_id": "ACCT-001",
        "account_name": "Northstar Logistics", 
        "role": "customer",  # or "internal"
        "plan": "Enterprise",
        "csm": "Jane Doe",  # Customer Success Manager
        "session_id": "abc-123"  # For tracking
    }
    """
    
    # ============================================================
    # ACTION MEMORY: What actions are pending?
    # ============================================================
    staged_action: Optional[Dict[str, Any]]
    """
    Stores an action that needs approval:
    {
        "action_type": "escalate_ticket" | "apply_credit" | "cancel_order",
        "reasoning": "Why this action is needed",
        "payload": {...},  # The actual data for the action
        "created_at": "2026-08-22T10:00:00"
    }
    """
    
    # ============================================================
    # STATE MEMORY: What's happening right now?
    # ============================================================
    action_approved: Optional[bool]
    """Has the user approved the staged action? None = not asked yet"""
    
    requires_approval: bool
    """Does the agent need to pause and ask for confirmation?"""
    
    execution_result: Optional[str]
    """Result after executing an action (success/error message)"""
    
    # ============================================================
    # CONTEXT MEMORY: Additional tracking
    # ============================================================
    conversation_id: Optional[str]
    """Unique ID for this conversation thread"""
    
    last_updated: Optional[str]
    """Timestamp of last state update"""
    
    tool_calls_made: int
    """Counter for how many tools have been called (for debugging)"""
    
    # ============================================================
    # METADATA: Authority rules (always applied, not stored per query)
    # ============================================================
    # These are defined in prompts.py, not stored in state
    # But we keep track of what was used
    sources_used: Optional[list]
    """Track which documents were cited in responses"""


# ============================================================
# HELPER FUNCTIONS: Creating and managing state
# ============================================================

def create_initial_state(
    account_id: str = None,
    account_name: str = None,
    role: str = "customer",
    plan: str = None,
    csm: str = None,
    initial_message: str = None
) -> AgentState:
    """
    Create a new agent state with default values.
    This is the "fresh memory" for a new conversation.
    
    Args:
        account_id: The user's account ID
        account_name: The user's account name
        role: "customer" or "internal"
        plan: The account plan (Enterprise, Growth, etc.)
        csm: Customer Success Manager name
        initial_message: The first user message
    
    Returns:
        A complete AgentState with defaults set
    """
    from langchain_core.messages import HumanMessage
    
    # Build user context
    user_context = {
        "account_id": account_id or "UNKNOWN",
        "account_name": account_name or "Unknown Customer",
        "role": role,
        "plan": plan or "Standard",
        "csm": csm or "Not Assigned",
        "session_started": datetime.now().isoformat(),
        "is_authenticated": bool(account_id)
    }
    
    # Create initial messages
    messages = []
    if initial_message:
        messages.append(HumanMessage(content=initial_message))
    
    # Return complete state
    return {
        # Short-term memory
        "messages": messages,
        
        # Entity memory
        "user_context": user_context,
        
        # Action memory
        "staged_action": None,
        
        # State memory
        "action_approved": None,
        "requires_approval": False,
        "execution_result": None,
        
        # Context memory
        "conversation_id": None,  # Will be set by the API
        "last_updated": datetime.now().isoformat(),
        "tool_calls_made": 0,
        
        # Metadata
        "sources_used": []
    }


def add_message_to_state(state: AgentState, message: BaseMessage) -> AgentState:
    """
    Add a new message to the state and update timestamps.
    This is how we add new messages to memory.
    
    Args:
        state: Current agent state
        message: New message to add
    
    Returns:
        Updated state with new message and timestamp
    """
    # Create a copy of the state
    new_state = dict(state)
    
    # Add the message (using the proper field)
    if "messages" not in new_state:
        new_state["messages"] = []
    
    # Append message
    new_state["messages"] = list(new_state["messages"]) + [message]
    
    # Update timestamp
    new_state["last_updated"] = datetime.now().isoformat()
    
    return new_state


def get_conversation_summary(state: AgentState, max_messages: int = 10) -> str:
    """
    Get a summary of the conversation for debugging.
    This helps us see what's in memory.
    
    Args:
        state: The agent state
        max_messages: How many recent messages to show
    
    Returns:
        A formatted summary string
    """
    messages = state.get("messages", [])
    user = state.get("user_context", {})
    
    summary = f"""
    📋 **Conversation Summary**
    ================================
    Account: {user.get('account_name', 'Unknown')} ({user.get('account_id', 'N/A')})
    Role: {user.get('role', 'customer')}
    Plan: {user.get('plan', 'Standard')}
    Messages: {len(messages)}
    Tools Used: {state.get('tool_calls_made', 0)}
    Requires Approval: {state.get('requires_approval', False)}
    
    Recent Messages:
    """
    
    for msg in messages[-max_messages:]:
        msg_type = type(msg).__name__
        content = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
        summary += f"\n  [{msg_type}]: {content}"
    
    return summary


# ============================================================
# TESTING: Let's verify the state works
# ============================================================

if __name__ == "__main__":
    print("🧠 Testing Agent State Management\n")
    print("="*50)
    
    # 1. Create a new state
    print("\n1️⃣ Creating new agent state...")
    state = create_initial_state(
        account_id="ACCT-001",
        account_name="Northstar Logistics",
        role="customer",
        plan="Enterprise",
        initial_message="Can I cancel order ORD-1001?"
    )
    
    print(f"   ✅ Account: {state['user_context']['account_name']}")
    print(f"   ✅ Messages: {len(state['messages'])}")
    print(f"   ✅ Role: {state['user_context']['role']}")
    
    # 2. Add a message
    print("\n2️⃣ Adding AI response...")
    from langchain_core.messages import AIMessage
    
    state = add_message_to_state(
        state,
        AIMessage(content="Let me check your contract for cancellation terms...")
    )
    
    print(f"   ✅ Messages now: {len(state['messages'])}")
    
    # 3. Stage an action
    print("\n3️⃣ Staging an action...")
    state["staged_action"] = {
        "action_type": "cancel_order",
        "reasoning": "Customer has contract that waives cancellation fees",
        "payload": {"order_id": "ORD-1001", "account_id": "ACCT-001"},
        "created_at": datetime.now().isoformat()
    }
    state["requires_approval"] = True
    
    print(f"   ✅ Action staged: {state['staged_action']['action_type']}")
    print(f"   ✅ Needs approval: {state['requires_approval']}")
    
    # 4. Show summary
    print("\n4️⃣ Full state summary:")
    print(get_conversation_summary(state))
    
    print("\n" + "="*50)
    print("✅ State management is ready!")