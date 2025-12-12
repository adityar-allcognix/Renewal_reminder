"""
Database Models
"""

from datetime import datetime, date
from typing import Optional, List
from decimal import Decimal
import uuid

from sqlalchemy import String, Text, Integer, Boolean, DateTime, Date, Numeric, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import Vector
import enum

from app.database import Base
from app.config import settings


class PolicyStatus(str, enum.Enum):
    """Policy status enumeration."""
    ACTIVE = "active"
    PENDING_RENEWAL = "pending_renewal"
    RENEWED = "renewed"
    LAPSED = "lapsed"
    CANCELLED = "cancelled"


class ReminderStatus(str, enum.Enum):
    """Reminder status enumeration."""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ReminderChannel(str, enum.Enum):
    """Communication channel enumeration."""
    EMAIL = "email"
    SMS = "sms"
    WHATSAPP = "whatsapp"
    CHAT = "chat"


class OutreachType(str, enum.Enum):
    """Outreach type enumeration."""
    REMINDER = "reminder"
    FOLLOW_UP = "follow_up"
    RETENTION = "retention"
    CONFIRMATION = "confirmation"


# ===========================================
# Customer Model
# ===========================================
class Customer(Base):
    """Customer model."""
    __tablename__ = "customers"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Basic Info
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20))
    
    # Address
    address_line1: Mapped[Optional[str]] = mapped_column(String(255))
    address_line2: Mapped[Optional[str]] = mapped_column(String(255))
    city: Mapped[Optional[str]] = mapped_column(String(100))
    state: Mapped[Optional[str]] = mapped_column(String(100))
    postal_code: Mapped[Optional[str]] = mapped_column(String(20))
    country: Mapped[str] = mapped_column(String(100), default="USA")
    
    # Preferences
    preferred_channel: Mapped[ReminderChannel] = mapped_column(
        SQLEnum(ReminderChannel), default=ReminderChannel.EMAIL
    )
    communication_preferences: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    
    # Engagement metrics
    engagement_score: Mapped[float] = mapped_column(Numeric(5, 2), default=0.0)
    last_interaction_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )
    
    # Relationships
    policies: Mapped[List["Policy"]] = relationship("Policy", back_populates="customer")
    interactions: Mapped[List["InteractionLog"]] = relationship("InteractionLog", back_populates="customer")
    
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


# ===========================================
# Policy Model
# ===========================================
class Policy(Base):
    """Policy model."""
    __tablename__ = "policies"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    policy_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    
    # Customer relationship
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"))
    customer: Mapped["Customer"] = relationship("Customer", back_populates="policies")
    
    # Policy details
    policy_type: Mapped[str] = mapped_column(String(100))  # e.g., "auto", "home", "life"
    coverage_type: Mapped[str] = mapped_column(String(100))
    coverage_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    
    # Premium
    premium_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    payment_frequency: Mapped[str] = mapped_column(String(50), default="monthly")  # monthly, quarterly, annual
    
    # Dates
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date, index=True)
    renewal_date: Mapped[date] = mapped_column(Date, index=True)
    
    # Status
    status: Mapped[PolicyStatus] = mapped_column(
        SQLEnum(PolicyStatus), default=PolicyStatus.ACTIVE, index=True
    )
    
    # Additional info
    beneficiaries: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    add_ons: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    extra_data: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )
    
    # Relationships
    reminders: Mapped[List["RenewalReminder"]] = relationship("RenewalReminder", back_populates="policy")


# ===========================================
# Renewal Reminder Model
# ===========================================
class RenewalReminder(Base):
    """Renewal reminder model."""
    __tablename__ = "renewal_reminders"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Policy relationship
    policy_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("policies.id"))
    policy: Mapped["Policy"] = relationship("Policy", back_populates="reminders")
    
    # Reminder details
    reminder_type: Mapped[int] = mapped_column(Integer)  # Days before renewal: 30, 15, 7, 1
    channel: Mapped[ReminderChannel] = mapped_column(SQLEnum(ReminderChannel))
    
    # Scheduling
    scheduled_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Status
    status: Mapped[ReminderStatus] = mapped_column(
        SQLEnum(ReminderStatus), default=ReminderStatus.PENDING, index=True
    )
    
    # Message content
    message_content: Mapped[Optional[str]] = mapped_column(Text)
    message_template_id: Mapped[Optional[str]] = mapped_column(String(100))
    
    # Tracking
    external_id: Mapped[Optional[str]] = mapped_column(String(255))  # SendGrid/Twilio message ID
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )


# ===========================================
# Outreach Log Model
# ===========================================
class OutreachLog(Base):
    """Outreach log model for tracking all customer communications."""
    __tablename__ = "outreach_logs"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # References
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), index=True)
    policy_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("policies.id"))
    reminder_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("renewal_reminders.id"))
    
    # Outreach details
    outreach_type: Mapped[OutreachType] = mapped_column(SQLEnum(OutreachType))
    channel: Mapped[ReminderChannel] = mapped_column(SQLEnum(ReminderChannel))
    
    # Message
    subject: Mapped[Optional[str]] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text)
    
    # Status
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    delivered: Mapped[bool] = mapped_column(Boolean, default=False)
    opened: Mapped[bool] = mapped_column(Boolean, default=False)
    clicked: Mapped[bool] = mapped_column(Boolean, default=False)
    responded: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Response
    customer_response: Mapped[Optional[str]] = mapped_column(Text)
    response_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Extra data
    extra_data: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


# ===========================================
# Interaction Log Model
# ===========================================
class InteractionLog(Base):
    """Customer interaction log for AI conversations."""
    __tablename__ = "interaction_logs"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Customer relationship
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), index=True)
    customer: Mapped["Customer"] = relationship("Customer", back_populates="interactions")
    
    # Session
    session_id: Mapped[str] = mapped_column(String(100), index=True)
    
    # Conversation
    user_query: Mapped[str] = mapped_column(Text)
    agent_response: Mapped[str] = mapped_column(Text)
    
    # Intent and context
    detected_intent: Mapped[Optional[str]] = mapped_column(String(100))
    tools_used: Mapped[Optional[list]] = mapped_column(JSONB, default=list)
    context: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    
    # Quality metrics
    response_time_ms: Mapped[Optional[int]] = mapped_column(Integer)
    feedback_rating: Mapped[Optional[int]] = mapped_column(Integer)  # 1-5
    was_helpful: Mapped[Optional[bool]] = mapped_column(Boolean)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


# ===========================================
# Policy Document Model (for RAG)
# ===========================================
class PolicyDocument(Base):
    """Policy document model for RAG embeddings."""
    __tablename__ = "policy_documents"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Document info
    document_name: Mapped[str] = mapped_column(String(255))
    document_type: Mapped[str] = mapped_column(String(100))  # pdf, docx, txt
    policy_type: Mapped[Optional[str]] = mapped_column(String(100))  # auto, home, life
    
    # Content
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    
    # Vector embedding
    embedding: Mapped[List[float]] = mapped_column(Vector(settings.VECTOR_DIMENSION))
    
    # Extra data
    extra_data: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )


# ===========================================
# Admin User Model (for Authentication)
# ===========================================
class UserRole(str, enum.Enum):
    """User role enumeration."""
    ADMIN = "admin"
    MANAGER = "manager"
    AGENT = "agent"


class AdminUser(Base):
    """Admin user model for authentication."""
    __tablename__ = "admin_users"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Basic Info
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(200))
    
    # Role and permissions
    role: Mapped[UserRole] = mapped_column(SQLEnum(UserRole), default=UserRole.AGENT)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


# ===========================================
# Audit Log Model (for tracking admin actions)
# ===========================================
class AuditLog(Base):
    """Audit log for tracking admin actions."""
    __tablename__ = "audit_logs"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    
    # Who performed the action
    admin_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("admin_users.id")
    )
    admin_email: Mapped[str] = mapped_column(String(255))
    
    # What action was performed
    action: Mapped[str] = mapped_column(String(100))  # create, update, delete, login, etc.
    resource_type: Mapped[str] = mapped_column(String(100))  # customer, policy, reminder, etc.
    resource_id: Mapped[Optional[str]] = mapped_column(String(100))
    
    # Details
    details: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    ip_address: Mapped[Optional[str]] = mapped_column(String(50))
    user_agent: Mapped[Optional[str]] = mapped_column(String(500))
    
    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )


# ===========================================
# Customer Token Model (for secure confirmation links)
# ===========================================
class CustomerTokenType(str, enum.Enum):
    """Customer token type enumeration."""
    RENEWAL_CONFIRMATION = "RENEWAL_CONFIRMATION"
    POLICY_VIEW = "POLICY_VIEW"
    CONTACT_UPDATE = "CONTACT_UPDATE"
    UNSUBSCRIBE = "UNSUBSCRIBE"
    DOCUMENT_UPLOAD = "DOCUMENT_UPLOAD"


class CustomerToken(Base):
    """Secure tokens for customer interactions without login."""
    __tablename__ = "customer_tokens"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    
    # Token info
    token: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    token_type: Mapped[CustomerTokenType] = mapped_column(
        SQLEnum(CustomerTokenType)
    )
    
    # Associated customer and policy
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id")
    )
    policy_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("policies.id"), nullable=True
    )
    
    # Expiry and usage
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    is_used: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Metadata
    token_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    
    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    
    # Relationships
    customer: Mapped["Customer"] = relationship("Customer")
    policy: Mapped[Optional["Policy"]] = relationship("Policy")
