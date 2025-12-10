"""
Pydantic Schemas for API Request/Response
"""

from datetime import datetime, date
from typing import Optional, List, Dict, Any, Generic, TypeVar
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field

from app.models import PolicyStatus, ReminderStatus, ReminderChannel, OutreachType

T = TypeVar("T")

class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    size: int
    pages: int

# ===========================================
# Customer Schemas
# ===========================================
class CustomerBase(BaseModel):
    """Base customer schema."""
    first_name: str = Field(..., max_length=100)
    last_name: str = Field(..., max_length=100)
    email: EmailStr
    phone: Optional[str] = Field(None, max_length=20)
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: str = "USA"
    preferred_channel: ReminderChannel = ReminderChannel.EMAIL


class CustomerCreate(CustomerBase):
    """Schema for creating a customer."""
    communication_preferences: Optional[Dict[str, Any]] = {}


class CustomerUpdate(BaseModel):
    """Schema for updating a customer."""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    preferred_channel: Optional[ReminderChannel] = None
    communication_preferences: Optional[Dict[str, Any]] = None


class CustomerResponse(CustomerBase):
    """Schema for customer response."""
    id: UUID
    full_name: str
    engagement_score: float
    last_interaction_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# ===========================================
# Policy Schemas
# ===========================================
class PolicyBase(BaseModel):
    """Base policy schema."""
    policy_number: str = Field(..., max_length=50)
    policy_type: str = Field(..., max_length=100)
    coverage_type: str = Field(..., max_length=100)
    coverage_amount: Decimal
    premium_amount: Decimal
    payment_frequency: str = "monthly"
    start_date: date
    end_date: date
    renewal_date: date


class PolicyCreate(PolicyBase):
    """Schema for creating a policy."""
    customer_id: UUID
    beneficiaries: Optional[List[Dict[str, Any]]] = []
    add_ons: Optional[List[Dict[str, Any]]] = []
    extra_data: Optional[Dict[str, Any]] = {}


class PolicyUpdate(BaseModel):
    """Schema for updating a policy."""
    coverage_type: Optional[str] = None
    coverage_amount: Optional[Decimal] = None
    premium_amount: Optional[Decimal] = None
    payment_frequency: Optional[str] = None
    status: Optional[PolicyStatus] = None
    beneficiaries: Optional[List[Dict[str, Any]]] = None
    add_ons: Optional[List[Dict[str, Any]]] = None
    extra_data: Optional[Dict[str, Any]] = None


class PolicyResponse(PolicyBase):
    """Schema for policy response."""
    id: UUID
    customer_id: UUID
    status: PolicyStatus
    beneficiaries: Optional[List[Dict[str, Any]]]
    add_ons: Optional[List[Dict[str, Any]]]
    extra_data: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime
    customer: Optional["CustomerResponse"] = None
    
    class Config:
        from_attributes = True


class PolicyWithCustomer(PolicyResponse):
    """Policy response with customer details."""
    customer: CustomerResponse


# ===========================================
# Renewal Reminder Schemas
# ===========================================
class ReminderBase(BaseModel):
    """Base reminder schema."""
    policy_id: UUID
    reminder_type: int = Field(..., description="Days before renewal")
    channel: ReminderChannel
    scheduled_date: datetime


class ReminderCreate(ReminderBase):
    """Schema for creating a reminder."""
    message_content: Optional[str] = None
    message_template_id: Optional[str] = None


class ReminderUpdate(BaseModel):
    """Schema for updating a reminder."""
    scheduled_date: Optional[datetime] = None
    status: Optional[ReminderStatus] = None
    message_content: Optional[str] = None


class ReminderResponse(ReminderBase):
    """Schema for reminder response."""
    id: UUID
    status: ReminderStatus
    sent_at: Optional[datetime]
    delivered_at: Optional[datetime]
    message_content: Optional[str]
    error_message: Optional[str]
    retry_count: int
    response_status: Optional[str] = "no_response"
    created_at: datetime
    updated_at: datetime
    policy: Optional["PolicyResponse"] = None
    
    class Config:
        from_attributes = True


# ===========================================
# Chat Schemas
# ===========================================
class ChatMessage(BaseModel):
    """Chat message schema."""
    customer_id: UUID
    session_id: Optional[str] = None
    message: str


class ChatResponse(BaseModel):
    """Chat response schema."""
    session_id: str
    response: str
    tools_used: List[str] = []
    context: Optional[Dict[str, Any]] = None
    response_time_ms: int


# ===========================================
# Analytics Schemas
# ===========================================
class ReminderStats(BaseModel):
    """Reminder statistics schema."""
    total_sent: int
    delivered: int
    failed: int
    pending: int
    delivery_rate: float


class ConversionStats(BaseModel):
    """Conversion statistics schema."""
    policies_due: int
    renewed: int
    lapsed: int
    pending: int
    conversion_rate: float


class EngagementStats(BaseModel):
    """Customer engagement statistics."""
    total_interactions: int
    avg_response_time_ms: float
    positive_feedback_rate: float
    queries_per_customer: float


class DashboardStats(BaseModel):
    """Dashboard statistics for frontend."""
    total_customers: int
    active_policies: int
    pending_renewals: int
    expiring_soon: int
    renewal_rate: float
    avg_engagement_score: float
    reminders_sent_today: int
    reminders_pending: int


class AnalyticsDashboard(BaseModel):
    """Combined analytics dashboard."""
    reminder_stats: ReminderStats
    conversion_stats: ConversionStats
    engagement_stats: EngagementStats
    period_start: date
    period_end: date


# ===========================================
# Tool Response Schemas (for AI Agent)
# ===========================================
class PolicyDetails(BaseModel):
    """Policy details for AI agent tool response."""
    policy_number: str
    customer_name: str
    policy_type: str
    coverage_type: str
    coverage_amount: Decimal
    premium_amount: Decimal
    renewal_date: date
    days_until_renewal: int
    status: str


class RenewalAmount(BaseModel):
    """Renewal amount calculation result."""
    policy_number: str
    current_premium: Decimal
    renewal_premium: Decimal
    premium_change: Decimal
    premium_change_percent: float
    renewal_date: date
    breakdown: Dict[str, Decimal]


class DocumentSearchResult(BaseModel):
    """RAG document search result."""
    content: str
    document_name: str
    relevance_score: float
    policy_type: Optional[str]
