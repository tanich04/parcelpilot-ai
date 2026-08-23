"""
src/api/models.py
Pydantic models for API requests and responses
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime


class ChatRequest(BaseModel):
    """Request model for chat endpoint"""
    
    message: str = Field(..., description="The user's message")
    account_id: Optional[str] = Field(None, description="The user's account ID (None for internal 'All Accounts' view)")
    account_name: Optional[str] = Field(None, description="Optional account name")
    role: str = Field("customer", description="User role: 'customer' or 'internal'")
    account_scope: str = Field("single", description="'single' for specific account, 'all' for cross-account view (internal only)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "What is the status of ORD-1001?",
                "account_id": "ACCT-001",
                "account_name": "Northstar Logistics",
                "role": "customer",
                "account_scope": "single"
            }
        }


class ChatResponse(BaseModel):
    """Response model for chat endpoint"""
    
    thread_id: str = Field(..., description="Unique thread ID for this conversation")
    response: str = Field(..., description="The agent's response")
    requires_approval: bool = Field(False, description="Whether action requires approval")
    staged_action: Optional[Dict[str, Any]] = Field(None, description="Staged action details")
    execution_result: Optional[str] = Field(None, description="Result of action execution")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    
    class Config:
        json_schema_extra = {
            "example": {
                "thread_id": "abc-123-def-456",
                "response": "Order ORD-1001 is currently BOOKED...",
                "requires_approval": False,
                "staged_action": None,
                "execution_result": None,
                "timestamp": "2026-08-23T10:00:00"
            }
        }


class ResumeRequest(BaseModel):
    """Request model for resuming after approval"""
    
    thread_id: str = Field(..., description="The thread ID to resume")
    decision: str = Field(..., description="'yes' or 'no'")
    feedback: Optional[str] = Field(None, description="Optional feedback text")
    
    class Config:
        json_schema_extra = {
            "example": {
                "thread_id": "abc-123-def-456",
                "decision": "yes",
                "feedback": "Approved by manager"
            }
        }


class HealthResponse(BaseModel):
    """Health check response"""
    
    status: str
    version: str
    timestamp: str
    components: Dict[str, str]