"""
src/ui/streamlit_app.py
ParcelPilot AI - Chat Interface

A Streamlit-based chat UI for the ParcelPilot AI Agent.
"""

import streamlit as st
import requests
import json
import time
from datetime import datetime
import sys
import os

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
API_CHAT_URL = f"{API_BASE_URL}/chat"
API_RESUME_URL = f"{API_BASE_URL}/chat/resume"
API_HEALTH_URL = f"{API_BASE_URL}/health"

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# Page configuration
st.set_page_config(
    page_title="ParcelPilot AI Support",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better UI
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1f3a57;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1rem;
        color: #666;
        margin-bottom: 1.5rem;
    }
    .chat-message {
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 0.5rem;
    }
    .user-message {
        background-color: #e3f2fd;
        border-left: 4px solid #1976d2;
    }
    .assistant-message {
        background-color: #f5f5f5;
        border-left: 4px solid #2e7d32;
    }
    .approval-box {
        background-color: #fff3e0;
        border: 2px solid #ff9800;
        border-radius: 0.5rem;
        padding: 1rem;
        margin: 1rem 0;
    }
    .status-badge {
        display: inline-block;
        padding: 0.2rem 0.6rem;
        border-radius: 1rem;
        font-size: 0.7rem;
        font-weight: 600;
    }
    .status-online {
        background-color: #4caf50;
        color: white;
    }
    .status-offline {
        background-color: #f44336;
        color: white;
    }
    .tool-usage {
        background-color: #e8eaf6;
        padding: 0.3rem 0.6rem;
        border-radius: 0.3rem;
        font-size: 0.7rem;
        color: #3949ab;
        margin-right: 0.3rem;
    }
    .footer {
        margin-top: 2rem;
        padding-top: 1rem;
        border-top: 1px solid #ddd;
        font-size: 0.8rem;
        color: #888;
        text-align: center;
    }
    .role-badge {
        display: inline-block;
        padding: 0.2rem 0.8rem;
        border-radius: 1rem;
        font-size: 0.7rem;
        font-weight: 600;
        margin-left: 0.5rem;
    }
    .role-customer {
        background-color: #e3f2fd;
        color: #1976d2;
    }
    .role-internal {
        background-color: #fff3e0;
        color: #e65100;
    }
    .scope-all {
        background-color: #e8f5e9;
        color: #2e7d32;
    }
    .scope-single {
        background-color: #f3e5f5;
        color: #7b1fa2;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# SESSION STATE INITIALIZATION
# ============================================================

def init_session_state():
    """Initialize all session state variables"""
    
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = None
    
    if "awaiting_approval" not in st.session_state:
        st.session_state.awaiting_approval = False
    
    if "staged_action" not in st.session_state:
        st.session_state.staged_action = None
    
    if "account_id" not in st.session_state:
        st.session_state.account_id = "ACCT-001"
    
    if "account_name" not in st.session_state:
        st.session_state.account_name = "Northstar Logistics"
    
    if "role" not in st.session_state:
        st.session_state.role = "customer"

    if "account_scope" not in st.session_state: 
        st.session_state.account_scope = "single"

    if "api_connected" not in st.session_state:
        st.session_state.api_connected = False
    
    if "response_time" not in st.session_state:
        st.session_state.response_time = None

init_session_state()

# ============================================================
# API CONFIGURATION
# ============================================================

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
API_CHAT_URL = f"{API_BASE_URL}/chat"
API_RESUME_URL = f"{API_BASE_URL}/chat/resume"

# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.image("https://img.icons8.com/color/96/logistics.png", width=80)
    st.markdown("## 📦 ParcelPilot")
    st.markdown("*AI-Powered Logistics Support*")
    st.divider()
    
    # ============================================================
    # ROLE SELECTOR
    # ============================================================
    
    st.markdown("### 🔐 User Context")
    
    role = st.radio(
        "Role",
        options=["customer", "internal"],
        index=0 if st.session_state.role == "customer" else 1,
        help="""
        Customer: Only sees their own account data.
        Internal: Can see all accounts and cross-account analytics.
        """
    )
    
    if role != st.session_state.role:
        st.session_state.role = role
        st.session_state.messages = []
        st.session_state.thread_id = None
        st.session_state.awaiting_approval = False
        st.session_state.staged_action = None
        if role == "customer":
            st.session_state.account_scope = "single"
            if not st.session_state.account_id:
                st.session_state.account_id = "ACCT-001"
        st.rerun()
    
    # ============================================================
    # ACCOUNT SELECTOR
    # ============================================================
    
    accounts = {
        "ACCT-001": "Northstar Logistics (Enterprise)",
        "ACCT-002": "LumenWorks (Growth)",
        "ACCT-003": "Beacon Retail (Standard)",
        "ACCT-004": "Axis Labs (Enterprise)"
    }
    
    if st.session_state.role == "customer":
        st.markdown("### 📂 Your Account")
        
        # Get current index
        current_index = list(accounts.keys()).index(st.session_state.account_id) if st.session_state.account_id in accounts else 0
        
        selected_account = st.selectbox(
            "Account",
            options=list(accounts.keys()),
            format_func=lambda x: accounts[x],
            index=current_index,
            help="You can only see data for your own account."
        )
        
        # ✅ FIX: Clear chat when account changes
        if selected_account != st.session_state.account_id:
            st.session_state.account_id = selected_account
            st.session_state.account_name = accounts[selected_account].split(" (")[0]
            st.session_state.account_scope = "single"
            st.session_state.messages = []
            st.session_state.thread_id = None
            st.session_state.awaiting_approval = False
            st.session_state.staged_action = None
            st.rerun()
        else:
            st.session_state.account_name = accounts[selected_account].split(" (")[0]
        
        st.info("🔒 Customer view: Your account only")
        
    else:  # internal role
        st.markdown("### 📂 Account Scope")
        st.info("🔍 Internal users can view all accounts")
        
        current_view = "🌐 All Accounts" if st.session_state.account_scope == "all" else "🎯 Specific Account"
        view_options = ["🌐 All Accounts", "🎯 Specific Account"]
        view_index = 0 if current_view == "🌐 All Accounts" else 1
        
        view_mode = st.radio(
            "View Mode",
            options=view_options,
            index=view_index,
            help="""
            All Accounts: See data across all customers (analytics, SLA breaches).
            Specific Account: Focus on one customer's data.
            """
        )
        
        if view_mode == "🌐 All Accounts":
            if st.session_state.account_scope != "all":
                st.session_state.account_id = None
                st.session_state.account_name = "All Accounts"
                st.session_state.account_scope = "all"
                st.session_state.messages = []
                st.session_state.thread_id = None
                st.session_state.awaiting_approval = False
                st.session_state.staged_action = None
                st.rerun()
            st.success("✅ Viewing all accounts - cross-account analytics available")
            
            st.markdown("### 📊 Quick Actions")
            if st.button("🔴 Show SLA Breaches", use_container_width=True):
                st.session_state.messages.append({
                    "role": "user",
                    "content": "Show me all SLA breaches across accounts"
                })
                st.rerun()
            
            if st.button("📋 Show All Open Tickets", use_container_width=True):
                st.session_state.messages.append({
                    "role": "user", 
                    "content": "Show me all open tickets across accounts"
                })
                st.rerun()
            
            if st.button("📦 Account Summary", use_container_width=True):
                st.session_state.messages.append({
                    "role": "user",
                    "content": "Give me a summary of all accounts"
                })
                st.rerun()
            
        else:  # Specific Account
            # Get current index
            current_index = list(accounts.keys()).index(st.session_state.account_id) if st.session_state.account_id in accounts else 0
            
            selected_account = st.selectbox(
                "Select Account",
                options=list(accounts.keys()),
                format_func=lambda x: accounts[x],
                index=current_index,
                help="View data for a specific customer account."
            )
            
            # ✅ FIX: Clear chat when account changes
            if selected_account != st.session_state.account_id or st.session_state.account_scope != "single":
                st.session_state.account_id = selected_account
                st.session_state.account_name = accounts[selected_account].split(" (")[0]
                st.session_state.account_scope = "single"
                st.session_state.messages = []
                st.session_state.thread_id = None
                st.session_state.awaiting_approval = False
                st.session_state.staged_action = None
                st.rerun()
            
            st.info(f"🔍 Viewing: {accounts[selected_account]}")
    
    st.divider()
    
    # ============================================================
    # SYSTEM STATUS
    # ============================================================
    
    st.markdown("### 📊 System Status")
    
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=2)
        if response.status_code == 200:
            st.success("✅ API Connected")
            st.session_state.api_connected = True
        else:
            st.error("❌ API Error")
            st.session_state.api_connected = False
    except:
        st.error("❌ API Offline")
        st.session_state.api_connected = False
    
    if st.session_state.response_time:
        st.metric("⏱️ Last Response", f"{st.session_state.response_time:.1f}s")
    
    if st.session_state.thread_id:
        st.caption(f"🧵 Thread: {st.session_state.thread_id[:8]}...")
    
    st.divider()
    
    # ============================================================
    # ACTIONS
    # ============================================================
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🗑️ Clear Chat"):
            st.session_state.messages = []
            st.session_state.thread_id = None
            st.session_state.awaiting_approval = False
            st.session_state.staged_action = None
            st.rerun()
    
    with col2:
        if st.button("🔄 Refresh"):
            st.rerun()
    
    st.divider()
    
    # ============================================================
    # QUICK EXAMPLES
    # ============================================================
    
    st.markdown("### 💡 Quick Examples")
    
    if st.session_state.role == "internal" and st.session_state.account_scope == "all":
        example_queries = [
            "Show me all open tickets",
            "Which accounts have SLA breaches?",
            "Are there recurring issues across accounts?",
            "Give me a summary of all accounts"
        ]
    else:
        example_queries = [
            "What is the status of ORD-1001?",
            "Can I cancel ORD-1001 without fee?",
            "Do I get a service credit for late pickup?",
            "What's the SLA for P1 issues?",
            "Known issues with bulk upload?"
        ]
    
    for query in example_queries:
        if st.button(query, use_container_width=True, key=f"example_{query[:10]}"):
            st.session_state.messages.append({"role": "user", "content": query})
            st.rerun()

# ============================================================
# MAIN CHAT INTERFACE
# ============================================================

# Header
header_col1, header_col2 = st.columns([3, 1])
with header_col1:
    st.markdown('<p class="main-header">📦 ParcelPilot AI Support</p>', unsafe_allow_html=True)
with header_col2:
    if st.session_state.role == "customer":
        st.markdown(f'<span class="role-badge role-customer">👤 Customer</span>', unsafe_allow_html=True)
    else:
        st.markdown(f'<span class="role-badge role-internal">🛠️ Internal</span>', unsafe_allow_html=True)
    
    if st.session_state.account_scope == "all":
        st.markdown(f'<span class="role-badge scope-all">🌐 All Accounts</span>', unsafe_allow_html=True)
    else:
        st.markdown(f'<span class="role-badge scope-single">📁 {st.session_state.account_name}</span>', unsafe_allow_html=True)

st.markdown(f'<p class="sub-header">Account: {st.session_state.account_name} | Role: {st.session_state.role} | Scope: {st.session_state.account_scope}</p>', unsafe_allow_html=True)

# Display chat messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        
        # Show tool usage if available
        if "tool_used" in msg:
            st.caption(f"🛠️ Used: {msg['tool_used']}")

# ============================================================
# APPROVAL WIDGET (if awaiting approval)
# ============================================================

if st.session_state.awaiting_approval and st.session_state.staged_action:
    with st.container():
        st.markdown("---")
        st.markdown("### ⚠️ Action Requires Approval")
        
        action = st.session_state.staged_action
        st.info(f"""
        **Action:** {action.get('action_type', 'Unknown')}
        **Reasoning:** {action.get('reasoning', 'No reasoning provided')}
        **Details:** {json.dumps(action.get('payload', {}), indent=2)}
        """)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Approve", use_container_width=True):
                # Resume with approval
                try:
                    response = requests.post(API_RESUME_URL, json={
                        "thread_id": st.session_state.thread_id,
                        "decision": "yes",
                        "feedback": "Approved by user"
                    })
                    
                    if response.status_code == 200:
                        data = response.json()
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": data["response"]
                        })
                        st.session_state.awaiting_approval = False
                        st.session_state.staged_action = None
                        st.rerun()
                    else:
                        st.error(f"Error: {response.text}")
                except Exception as e:
                    st.error(f"Error: {e}")
        
        with col2:
            if st.button("❌ Reject", use_container_width=True):
                # Resume with rejection
                try:
                    response = requests.post(API_RESUME_URL, json={
                        "thread_id": st.session_state.thread_id,
                        "decision": "no",
                        "feedback": "Rejected by user"
                    })
                    
                    if response.status_code == 200:
                        data = response.json()
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": data["response"]
                        })
                        st.session_state.awaiting_approval = False
                        st.session_state.staged_action = None
                        st.rerun()
                    else:
                        st.error(f"Error: {response.text}")
                except Exception as e:
                    st.error(f"Error: {e}")

# ============================================================
# CHAT INPUT
# ============================================================

# Disable input if awaiting approval
input_disabled = st.session_state.awaiting_approval

if prompt := st.chat_input("Ask about your shipments, policies, or support...", disabled=input_disabled):
    
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Display user message
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Call API
    with st.chat_message("assistant"):
        with st.spinner("🤔 Thinking..."):
            start_time = time.time()
            
            try:
                # Prepare request
                payload = {
                    "message": prompt,
                    "account_id": st.session_state.account_id,
                    "account_name": st.session_state.account_name,
                    "role": st.session_state.role,
                    "account_scope": st.session_state.account_scope
                }
                
                # Send request
                response = requests.post(API_CHAT_URL, json=payload)
                elapsed_time = time.time() - start_time
                st.session_state.response_time = elapsed_time
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Store thread ID
                    st.session_state.thread_id = data["thread_id"]
                    
                    # Check if action requires approval
                    if data.get("requires_approval") and data.get("staged_action"):
                        st.session_state.awaiting_approval = True
                        st.session_state.staged_action = data["staged_action"]
                        
                        # Show response with approval
                        st.markdown(data["response"])
                        
                        # Show approval widget
                        st.markdown("---")
                        st.warning("⚠️ **Action Requires Your Approval**")
                        
                        action = data["staged_action"]
                        st.code(f"""
Action: {action.get('action_type', 'Unknown')}
Reasoning: {action.get('reasoning', 'No reasoning')}
Payload: {json.dumps(action.get('payload', {}), indent=2)}
                        """)
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("✅ Approve Action", key="approve_btn"):
                                resume_response = requests.post(API_RESUME_URL, json={
                                    "thread_id": st.session_state.thread_id,
                                    "decision": "yes"
                                })
                                if resume_response.status_code == 200:
                                    resume_data = resume_response.json()
                                    st.session_state.messages.append({
                                        "role": "assistant",
                                        "content": resume_data["response"]
                                    })
                                    st.session_state.awaiting_approval = False
                                    st.session_state.staged_action = None
                                    st.rerun()
                        
                        with col2:
                            if st.button("❌ Reject Action", key="reject_btn"):
                                resume_response = requests.post(API_RESUME_URL, json={
                                    "thread_id": st.session_state.thread_id,
                                    "decision": "no"
                                })
                                if resume_response.status_code == 200:
                                    resume_data = resume_response.json()
                                    st.session_state.messages.append({
                                        "role": "assistant",
                                        "content": resume_data["response"]
                                    })
                                    st.session_state.awaiting_approval = False
                                    st.session_state.staged_action = None
                                    st.rerun()
                        
                        # Store the response (without the approval UI)
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": data["response"]
                        })
                        
                    else:
                        # Normal response
                        st.markdown(data["response"])
                        
                        # Store the response
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": data["response"]
                        })
                    
                    # Show response time
                    st.caption(f"⏱️ {elapsed_time:.1f}s • 🧵 {data['thread_id'][:8]}...")
                    
                else:
                    st.error(f"❌ API Error: {response.status_code}")
                    st.code(response.text)
                    
            except requests.exceptions.ConnectionError:
                st.error("❌ Cannot connect to API server. Make sure it's running!")
                st.info("Run: `python src/api/endpoints.py` in another terminal")
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")

# ============================================================
# FOOTER
# ============================================================

st.markdown('<div class="footer">ParcelPilot AI Support • Powered by Groq • Data snapshot: 2026-08-16</div>', unsafe_allow_html=True)