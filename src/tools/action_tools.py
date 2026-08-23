# src/tools/action_tools.py

"""
Tool 3: State-Changing Actions (with Confirmation)

⚠️ CRITICAL: All actions require explicit user confirmation!
"""

import json
from datetime import datetime
import logging
from typing import Optional, Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================
# MAIN ACTION FUNCTIONS (No @tool decorator for testing)
# ============================================================

def stage_action(
    action_type: str,
    reasoning: str,
    payload: Dict[str, Any],
    ticket_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Stage an operational action for human approval.
    
    ⚠️ CRITICAL: This tool does NOT execute anything!
    It only PREPARES the action for review.
    
    Valid action types:
    - "cancel_order": Cancel a shipment
    - "escalate_ticket": Increase ticket priority
    - "apply_credit": Issue service credit
    - "create_task": Create follow-up task
    - "close_ticket": Mark ticket as resolved
    """
    
    logger.info(f"📋 Staging action: {action_type}")
    
    valid_actions = [
        "cancel_order", "escalate_ticket", "apply_credit",
        "create_task", "close_ticket"
    ]
    
    if action_type not in valid_actions:
        return {
            "status": "ERROR",
            "error": f"Invalid action type: {action_type}",
            "valid_types": valid_actions
        }
    
    return {
        "status": "STAGED_FOR_APPROVAL",
        "action_type": action_type,
        "reasoning": reasoning,
        "payload": payload,
        "ticket_id": ticket_id,
        "staged_at": datetime.now().isoformat(),
        "requires_confirmation": True,
        "confirmation_message": get_confirmation_message(action_type, payload)
    }


def get_confirmation_message(action_type: str, payload: Dict[str, Any]) -> str:
    """Generate a user-friendly confirmation message"""
    
    messages = {
        "cancel_order": f"""
⚠️ **Action: Cancel Order**

You are about to cancel order: {payload.get('order_id')}

**Reason:** {payload.get('reason', 'Not specified')}

**Do you want to proceed with cancellation?**
""",
        "escalate_ticket": f"""
⚠️ **Action: Escalate Ticket**

You are about to escalate ticket: {payload.get('ticket_id')}
New Priority: {payload.get('priority')}

**Do you want to escalate this ticket?**
""",
        "apply_credit": f"""
⚠️ **Action: Apply Service Credit**

You are about to apply a service credit:
- **Order:** {payload.get('order_id')}
- **Amount:** ₹{payload.get('amount', '0')}
- **Reason:** {payload.get('reason', 'Not specified')}

**Do you want to apply this credit?**
"""
    }
    
    return messages.get(action_type, f"⚠️ Action: {action_type}. Do you approve?")


def execute_action(staged_action: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a previously staged action after user approval"""
    
    action_type = staged_action.get("action_type")
    payload = staged_action.get("payload", {})
    
    logger.info(f"▶️ Executing action: {action_type}")
    
    result = {
        "status": "EXECUTED",
        "action_type": action_type,
        "executed_at": datetime.now().isoformat(),
        "success": True,
        "message": f"Action '{action_type}' executed successfully"
    }
    
    if action_type == "cancel_order":
        result["message"] = f"Order {payload.get('order_id')} has been cancelled"
    elif action_type == "escalate_ticket":
        result["message"] = f"Ticket {payload.get('ticket_id')} escalated to {payload.get('priority')}"
    elif action_type == "apply_credit":
        result["message"] = f"Service credit of ₹{payload.get('amount')} applied"
    
    return result


# ============================================================
# LANGCHAIN TOOL WRAPPER (For use with agent)
# ============================================================

from langchain.tools import tool

@tool
def stage_action_tool(
    action_type: str,
    reasoning: str,
    payload: Dict[str, Any],
    ticket_id: Optional[str] = None
) -> Dict[str, Any]:
    """Stage an action for approval"""
    return stage_action(action_type, reasoning, payload, ticket_id)


if __name__ == "__main__":
    print("🧪 Testing Action Tools\n")
    print("="*50)
    
    result = stage_action(
        action_type="cancel_order",
        reasoning="Customer contract waives fee",
        payload={"order_id": "ORD-1001", "account_id": "ACCT-001"}
    )
    print(f"Status: {result['status']}")