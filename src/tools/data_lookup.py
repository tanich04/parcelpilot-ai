# src/tools/data_lookup.py

"""
Tool 2: Structured Data Lookup

This tool allows the agent to query:
- Order details (status, carrier, pickup times)
- Account information (plan, CSM, contract)
- Ticket history (for context)
"""

import sqlite3
import logging
from datetime import datetime
from typing import Optional, Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = "parcelpilot.db"


def get_db_connection():
    """Get a connection to the SQLite database"""
    return sqlite3.connect(DB_PATH)


def format_datetime(dt_str):
    """Format datetime string for display"""
    if not dt_str:
        return "N/A"
    try:
        dt = datetime.fromisoformat(str(dt_str))
        return dt.strftime("%d %b %Y, %I:%M %p")
    except:
        return str(dt_str)


def format_currency(amount):
    """Format currency in INR"""
    if amount is None:
        return "₹0.00"
    return f"₹{float(amount):.2f}"


# ============================================================
# MAIN LOOKUP FUNCTIONS (No @tool decorator for testing)
# ============================================================

def lookup_order(order_id: str, account_id: Optional[str] = None) -> str:
    """
    Look up order details including status, carrier, pickup times, and fees.
    
    Args:
        order_id: The order ID (e.g., "ORD-1001")
        account_id: Optional - enforces access control
    
    Returns:
        Formatted order details
    """
    
    try:
        logger.info(f"📦 Looking up order: {order_id} for account: {account_id}")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT 
                o.order_id,
                o.status,
                o.carrier,
                o.booked_at,
                o.pickup_window_start,
                o.pickup_window_end,
                o.pickup_actual_at,
                o.shipment_fee_inr,
                o.carrier_fault,
                o.customer_fault,
                o.cancellation_requested_at,
                o.notes,
                a.account_id,
                a.account_name,
                a.plan,
                a.premium_support
            FROM orders o
            JOIN accounts a ON o.account_id = a.account_id
            WHERE o.order_id = ?
        """
        
        cursor.execute(query, (order_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return f"❌ Order '{order_id}' not found."
        
        # Access Control Check
        row_account_id = row[12]
        if account_id and row_account_id != account_id:
            return f"""❌ **Access Denied**

Order '{order_id}' belongs to another account ({row_account_id}).

You can only view orders for your own account ({account_id})."""
        
        # Determine cancellation eligibility
        cancel_eligible = "❌ No"
        status = row[1]
        
        if status in ["DRAFT", "BOOKED"]:
            if row[10]:
                cancel_eligible = "⏳ Pending"
            else:
                cancel_eligible = "✅ Yes"
        elif status in ["PICKED_UP", "DELIVERED"]:
            cancel_eligible = "❌ No"
        
        response = f"""
📦 **Order Details: {order_id}**

**Account:** {row[13]} ({row[12]})
**Plan:** {row[14]}
**Premium Support:** {row[15] or 'No'}

**Shipment Details:**
- **Status:** {row[1]}
- **Carrier:** {row[2] or 'Not assigned'}
- **Booked At:** {format_datetime(row[3])}
- **Pickup Window:** {format_datetime(row[4])} to {format_datetime(row[5])}
- **Actual Pickup:** {format_datetime(row[6]) or 'Not yet picked up'}

**Financials:**
- **Shipment Fee:** {format_currency(row[7])}

**Fault Status:**
- **Carrier Fault:** {'✅ Yes' if row[8] else '❌ No'}
- **Customer Fault:** {'✅ Yes' if row[9] else '❌ No'}

**Cancellation:**
- **Eligible:** {cancel_eligible}
- **Requested At:** {format_datetime(row[10]) or 'Not requested'}

**Notes:** {row[11] or 'None'}
"""
        return response
        
    except Exception as e:
        return f"❌ Error: {str(e)}"


def lookup_account(account_id: str) -> str:
    """Look up account details"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT account_id, account_name, plan, status, csm,
                   contract_file, premium_support, notes
            FROM accounts
            WHERE account_id = ?
        """, (account_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return f"❌ Account '{account_id}' not found."
        
        response = f"""
🏢 **Account Details: {row[0]}**

**Name:** {row[1]}
**Plan:** {row[2]}
**Status:** {row[3]}
**CSM:** {row[4] or 'Not assigned'}
**Contract:** {row[5] or 'No contract on file'}
**Premium Support:** {row[6] or 'No'}
**Notes:** {row[7] or 'None'}
"""
        return response
        
    except Exception as e:
        return f"❌ Error: {str(e)}"


def check_service_credit(order_id: str, account_id: Optional[str] = None) -> str:
    """Check if an order is eligible for service credit"""
    try:
        # First verify access
        order_info = lookup_order(order_id, account_id)
        if "Access Denied" in order_info:
            return order_info
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT status, pickup_window_start, pickup_actual_at, 
                   shipment_fee_inr, carrier_fault, customer_fault
            FROM orders
            WHERE order_id = ?
        """, (order_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return "❌ Order not found"
        
        # Calculate credit
        credit_percentage = 0
        reason = "No fault found"
        
        if row[4] == 1:  # carrier_fault
            if row[1] and row[2]:
                try:
                    window_start = datetime.fromisoformat(row[1])
                    actual = datetime.fromisoformat(row[2])
                    delay_hours = (actual - window_start).total_seconds() / 3600
                    
                    if delay_hours >= 6:
                        credit_percentage = 1.0
                        reason = f"Carrier was {delay_hours:.1f} hours late (6+ hours)"
                    elif delay_hours >= 3:
                        credit_percentage = 0.5
                        reason = f"Carrier was {delay_hours:.1f} hours late (3-6 hours)"
                    else:
                        reason = f"Carrier was only {delay_hours:.1f} hours late (under 3 hours)"
                except:
                    pass
        
        amount = row[3] * credit_percentage if credit_percentage > 0 else 0
        
        response = f"""
💰 **Service Credit Check: {order_id}**

**Eligible:** {'✅ Yes' if credit_percentage > 0 else '❌ No'}
**Reason:** {reason}
**Amount:** {format_currency(amount)}
**Original Fee:** {format_currency(row[3])}
**Percentage:** {credit_percentage * 100}%

*Based on Cancellation & Service Credit SOP v4*
"""
        return response
        
    except Exception as e:
        return f"❌ Error: {str(e)}"


# ============================================================
# LANGCHAIN TOOL WRAPPER (For use with agent)
# ============================================================

from langchain.tools import tool

@tool
def lookup_order_tool(order_id: str, account_id: Optional[str] = None) -> str:
    """Look up order details"""
    return lookup_order(order_id, account_id)

@tool
def lookup_account_tool(account_id: str) -> str:
    """Look up account details"""
    return lookup_account(account_id)

@tool
def check_service_credit_tool(order_id: str, account_id: Optional[str] = None) -> str:
    """Check service credit eligibility"""
    return check_service_credit(order_id, account_id)


if __name__ == "__main__":
    print("🧪 Testing Data Lookup Tools\n")
    print("="*50)
    
    print("\n📝 Test: lookup_order('ORD-1001', 'ACCT-001')")
    print("-"*30)
    result = lookup_order("ORD-1001", "ACCT-001")
    print(result[:500] + "...")