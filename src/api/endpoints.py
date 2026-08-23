"""
src/api/endpoints.py
FastAPI endpoints for the ParcelPilot AI Agent
"""

import os
import sys
import json
from typing import Optional
from datetime import datetime
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import uvicorn

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.api.models import ChatRequest, ChatResponse, ResumeRequest, HealthResponse
from src.agent.graph import AgentRunner

# ============================================================
# APP INITIALIZATION
# ============================================================

app = FastAPI(
    title="ParcelPilot AI Agent API",
    description="AI-powered support agent for ParcelPilot logistics platform",
    version="1.0.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# GLOBAL AGENT RUNNER (Singleton)
# ============================================================

_agent_runner = None

def get_agent_runner():
    """Get the global agent runner instance (singleton)"""
    global _agent_runner
    if _agent_runner is None:
        _agent_runner = AgentRunner()
    return _agent_runner


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        timestamp=datetime.now().isoformat(),
        components={
            "database": "connected",
            "vector_store": "connected",
            "llm": "connected"
        }
    )


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "ParcelPilot AI Agent",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "/chat": "POST - Send a message to the agent",
            "/chat/resume": "POST - Resume after approval",
            "/health": "GET - Health check"
        }
    }


# ============================================================
# CHAT ENDPOINTS
# ============================================================

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Send a message to the agent.
    
    Creates a new conversation thread or continues existing one.
    Supports:
    - Customer: Single account only
    - Internal: All Accounts (cross-account) or Specific Account
    """
    
    try:
        # Get the agent runner
        runner = get_agent_runner()
        
        # Validate role
        if request.role not in ["customer", "internal"]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid role: {request.role}. Must be 'customer' or 'internal'"
            )
        
        # Validate account_scope
        if request.account_scope not in ["single", "all"]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid account_scope: {request.account_scope}. Must be 'single' or 'all'"
            )
        
        # Customers cannot use "all" scope
        if request.role == "customer" and request.account_scope == "all":
            raise HTTPException(
                status_code=400,
                detail="Customers cannot use 'all' account scope. Only internal users can view all accounts."
            )
        
        # Customers must provide account_id
        if request.role == "customer" and not request.account_id:
            raise HTTPException(
                status_code=400,
                detail="Customer role requires account_id"
            )
        
        # Run the agent
        result = runner.run(
            message=request.message,
            account_id=request.account_id,
            role=request.role,
            account_name=request.account_name,
            account_scope=request.account_scope
        )
        
        # Return response
        return ChatResponse(
            thread_id=result["thread_id"],
            response=result["response"],
            requires_approval=result.get("requires_approval", False),
            staged_action=result.get("staged_action"),
            execution_result=result.get("execution_result")
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        print(f"❌ Chat error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@app.post("/chat/resume", response_model=ChatResponse)
async def resume_chat(request: ResumeRequest):
    """
    Resume a paused conversation after user approval.
    
    Use this endpoint after the agent requests approval for an action.
    """
    
    try:
        # Get the agent runner
        runner = get_agent_runner()
        
        # Validate decision
        if request.decision not in ["yes", "no"]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid decision: {request.decision}. Must be 'yes' or 'no'"
            )
        
        # Resume the agent
        result = runner.resume(
            thread_id=request.thread_id,
            decision=request.decision,
            feedback=request.feedback or ""
        )
        
        if "error" in result:
            raise HTTPException(
                status_code=404,
                detail=result["error"]
            )
        
        # Return response
        return ChatResponse(
            thread_id=request.thread_id,
            response=result["response"],
            requires_approval=False,
            staged_action=None,
            execution_result=result.get("execution_result")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Resume error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


# ============================================================
# TEST ENDPOINTS
# ============================================================

@app.get("/test/status")
async def test_status():
    """Test endpoint - returns agent status"""
    runner = get_agent_runner()
    return {
        "status": "ready",
        "threads": len(runner.threads),
        "graph_compiled": runner.graph is not None
    }


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    print("🚀 Starting ParcelPilot AI API Server...")
    print("="*60)
    print("📡 Server running at: http://localhost:8000")
    print("📚 API docs: http://localhost:8000/docs")
    print("="*60)
    
    uvicorn.run(
        "src.api.endpoints:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )