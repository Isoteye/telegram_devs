from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, Enum, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

# Import Base from db.py to ensure all models use the same Base
from .db import Base

# ========== ENUMS ==========
class DeveloperStatus(str, enum.Enum):
    ACTIVE = "active"
    BUSY = "busy"
    INACTIVE = "inactive"

class OrderStatus(str, enum.Enum):
    PENDING_PAYMENT = "pending_payment"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"

class PaymentMethod(str, enum.Enum):
    PAYSTACK = "paystack"
    BANK_TRANSFER = "bank_transfer"
    CARD = "card"
    CRYPTO = "crypto"

class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    FAILED = "failed"
    REFUNDED = "refunded"

class RequestStatus(str, enum.Enum):
    NEW = "new"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"

# JOB MARKETPLACE ENUMS
class JobStatus(str, enum.Enum):
    DRAFT = "draft"
    AWAITING_DEPOSIT = "awaiting_deposit"
    PENDING_APPROVAL = "pending_approval"
    OPEN = "open"
    CLAIMED = "claimed"
    IN_PROGRESS = "in_progress"
    DELIVERED = "delivered"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    DISPUTED = "disputed"
    REFUNDED = "refunded"

class ClaimStatus(str, enum.Enum):
    CLAIMED = "claimed"
    IN_PROGRESS = "in_progress"
    DELIVERED = "delivered"
    COMPLETED = "completed"
    DISPUTED = "disputed"
    REFUNDED = "refunded"

class MessageType(str, enum.Enum):
    TEXT = "text"
    FILE = "file"
    SYSTEM = "system"

# ========== MODELS ==========
class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(String(100), unique=True, nullable=False)
    username = Column(String(100))
    first_name = Column(String(100))
    last_name = Column(String(100))
    email = Column(String(100))
    phone = Column(String(50))
    country = Column(String(10), default='GH')
    currency = Column(String(10), default='USD')
    currency_symbol = Column(String(10), default='$')
    is_admin = Column(Boolean, default=False)
    is_developer = Column(Boolean, default=False)
    balance = Column(Float, default=0.0)
    total_orders = Column(Integer, default=0)
    can_resolve_disputes = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relationships
    orders = relationship("Order", back_populates="user", cascade="all, delete-orphan")
    developer_profile = relationship("Developer", back_populates="user", uselist=False, cascade="all, delete-orphan")
    developer_requests = relationship("DeveloperRequest", back_populates="user", cascade="all, delete-orphan", foreign_keys="DeveloperRequest.user_id")
    custom_requests = relationship("CustomRequest", back_populates="user", cascade="all, delete-orphan")
    reviewed_developer_requests = relationship("DeveloperRequest", back_populates="reviewer", foreign_keys="DeveloperRequest.reviewed_by")
    
    # JOB MARKETPLACE RELATIONSHIPS
    jobs = relationship("Job", back_populates="user", foreign_keys="Job.user_id", cascade="all, delete-orphan")
    job_messages = relationship("JobMessage", back_populates="user", cascade="all, delete-orphan")


class Developer(Base):
    __tablename__ = 'developers'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), unique=True)
    developer_id = Column(String(50), unique=True)
    status = Column(Enum(DeveloperStatus), default=DeveloperStatus.ACTIVE)
    is_available = Column(Boolean, default=True)
    skills = Column(Text)
    experience = Column(Text)
    hourly_rate = Column(Float, default=25.0)
    portfolio_url = Column(String(500))
    github_url = Column(String(500))
    completed_orders = Column(Integer, default=0)
    rating = Column(Float, default=0.0)
    earnings = Column(Float, default=0.0)
    
    # JOB MARKETPLACE FIELDS
    claim_tokens_available = Column(Integer, default=0)
    completed_jobs_count = Column(Integer, default=0)
    average_rating = Column(Float, default=0.0)
    total_earnings = Column(Float, default=0.0)
    
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relationships
    user = relationship("User", back_populates="developer_profile")
    assigned_orders = relationship("Order", back_populates="developer")
    
    # JOB MARKETPLACE RELATIONSHIPS
    claimed_jobs = relationship("JobClaim", back_populates="developer", cascade="all, delete-orphan")
    claim_tokens = relationship("ClaimToken", back_populates="developer", cascade="all, delete-orphan")


class Bot(Base):
    __tablename__ = 'bots'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    slug = Column(String(200), unique=True)
    description = Column(Text)
    features = Column(Text)
    price = Column(Float, nullable=False)
    category = Column(String(100))
    delivery_time = Column(String(50))
    is_available = Column(Boolean, default=True)
    is_featured = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relationships
    orders = relationship("Order", back_populates="bot", cascade="all, delete-orphan")


class Order(Base):
    __tablename__ = 'orders'
    
    id = Column(Integer, primary_key=True)
    order_id = Column(String(50), unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    bot_id = Column(Integer, ForeignKey('bots.id'))
    assigned_developer_id = Column(Integer, ForeignKey('developers.id'))
    amount = Column(Float, nullable=False)
    status = Column(Enum(OrderStatus), default=OrderStatus.PENDING_PAYMENT)
    payment_method = Column(Enum(PaymentMethod))
    payment_status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING)
    payment_proof_url = Column(String(500))
    payment_reference = Column(String(200))
    payment_metadata = Column(JSON)
    admin_notes = Column(Text)
    developer_notes = Column(Text)
    delivered_at = Column(DateTime)
    paid_at = Column(DateTime)
    
    # Refund fields
    refunded_at = Column(DateTime)
    refund_reason = Column(Text)
    refund_metadata = Column(JSON)
    
    # Admin approval timestamp
    approved_at = Column(DateTime)
    
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relationships
    user = relationship("User", back_populates="orders")
    bot = relationship("Bot", back_populates="orders")
    developer = relationship("Developer", back_populates="assigned_orders")


class CustomRequest(Base):
    __tablename__ = 'custom_requests'
    
    id = Column(Integer, primary_key=True)
    request_id = Column(String(50), unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    features = Column(Text)
    budget_tier = Column(String(50))
    estimated_price = Column(Float, default=0.0)
    deposit_paid = Column(Float, default=0.0)
    is_deposit_paid = Column(Boolean, default=False)
    delivery_time = Column(String(50))
    timeline = Column(String(100))
    status = Column(Enum(RequestStatus), default=RequestStatus.NEW)
    assigned_to = Column(Integer, ForeignKey('developers.id'))
    admin_notes = Column(Text)
    payment_reference = Column(String(200))
    payment_metadata = Column(JSON)
    
    # Deposit payment timestamp
    deposit_paid_at = Column(DateTime)
    
    # Refund fields
    refunded_at = Column(DateTime)
    refund_reason = Column(Text)
    refund_metadata = Column(JSON)
    
    # Admin approval timestamp
    approved_at = Column(DateTime)
    
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relationships
    user = relationship("User", back_populates="custom_requests")


class DeveloperRequest(Base):
    __tablename__ = 'developer_requests'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    skills_experience = Column(Text, nullable=False)
    portfolio_url = Column(String(500))
    github_url = Column(String(500))
    hourly_rate = Column(Float, default=25.0)
    status = Column(Enum(RequestStatus), default=RequestStatus.NEW)
    reviewed_by = Column(Integer, ForeignKey('users.id'))
    reviewed_at = Column(DateTime)
    admin_notes = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relationships
    user = relationship("User", back_populates="developer_requests", foreign_keys=[user_id])
    reviewer = relationship("User", back_populates="reviewed_developer_requests", foreign_keys=[reviewed_by])


class Transaction(Base):
    __tablename__ = 'transactions'
    
    id = Column(Integer, primary_key=True)
    transaction_id = Column(String(100), unique=True)
    order_id = Column(Integer, ForeignKey('orders.id'))
    user_id = Column(Integer, ForeignKey('users.id'))
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default='USD')
    payment_method = Column(Enum(PaymentMethod))
    status = Column(String(50))
    reference = Column(String(200))
    gateway_response = Column(Text)
    transaction_data = Column(JSON)
    
    # USD equivalent amount
    usd_amount = Column(Float)
    
    # Refund fields
    refund_data = Column(JSON)
    verified_at = Column(DateTime)
    
    created_at = Column(DateTime, default=datetime.now)


class PaymentMethodConfig(Base):
    __tablename__ = 'payment_method_configs'
    
    id = Column(Integer, primary_key=True)
    method = Column(String(50), unique=True)
    is_active = Column(Boolean, default=True)
    config_data = Column(JSON)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


# ========== JOB MARKETPLACE MODELS ==========
class Job(Base):
    __tablename__ = 'jobs'
    
    id = Column(Integer, primary_key=True)
    job_id = Column(String(50), unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    expected_outcome = Column(Text)
    category = Column(String(100))
    budget = Column(Float, nullable=False)
    deposit_amount = Column(Float, default=0.0)
    deposit_paid = Column(Boolean, default=False)  # Fixed: Keep as deposit_paid
    deposit_paid_at = Column(DateTime, nullable=True)  # Added missing field
    status = Column(Enum(JobStatus), default=JobStatus.AWAITING_DEPOSIT)
    
    # Job visibility settings
    is_public = Column(Boolean, default=False)
    preview_description = Column(Text)
    
    # Timing
    expected_timeline = Column(String(100))
    delivery_date = Column(DateTime)
    
    # Admin
    admin_notes = Column(Text)
    approved_by = Column(Integer, ForeignKey('users.id'))
    approved_at = Column(DateTime)
    
    # Payment
    payment_reference = Column(String(200))
    claim_token_price = Column(Float, default=10.0)
    
    # Chat/Communication
    chat_id = Column(String(100))
    chat_link = Column(String(500))
    
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relationships
    user = relationship("User", back_populates="jobs", foreign_keys=[user_id])
    approver = relationship("User", foreign_keys=[approved_by])
    claim = relationship("JobClaim", back_populates="job", uselist=False, cascade="all, delete-orphan")
    messages = relationship("JobMessage", back_populates="job", cascade="all, delete-orphan")


class JobClaim(Base):
    __tablename__ = 'job_claims'
    
    id = Column(Integer, primary_key=True)
    claim_id = Column(String(50), unique=True, nullable=False)
    job_id = Column(Integer, ForeignKey('jobs.id'), unique=True)
    developer_id = Column(Integer, ForeignKey('developers.id'), nullable=False)
    claim_token_paid = Column(Boolean, default=False)
    status = Column(Enum(ClaimStatus), default=ClaimStatus.CLAIMED)
    
    # Payment info for claim token
    token_payment_reference = Column(String(200))
    token_payment_method = Column(Enum(PaymentMethod))
    
    # Work submission
    submission_text = Column(Text)
    submission_files = Column(JSON)
    submitted_at = Column(DateTime)
    
    # Completion
    customer_accepted = Column(Boolean, default=False)
    customer_rating = Column(Integer)
    customer_feedback = Column(Text)
    
    # Final payment (remaining balance)
    final_payment_paid = Column(Boolean, default=False)
    final_payment_reference = Column(String(200))
    final_payment_method = Column(Enum(PaymentMethod))
    
    # Dispute resolution
    dispute_reason = Column(Text)
    dispute_resolved_by = Column(Integer, ForeignKey('users.id'))
    dispute_resolution = Column(Text)
    
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relationships
    job = relationship("Job", back_populates="claim", foreign_keys=[job_id])
    developer = relationship("Developer", back_populates="claimed_jobs", foreign_keys=[developer_id])
    dispute_resolver = relationship("User", foreign_keys=[dispute_resolved_by])


class JobMessage(Base):
    __tablename__ = 'job_messages'
    
    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey('jobs.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    message_type = Column(Enum(MessageType))
    content = Column(Text)
    file_url = Column(String(500))
    file_type = Column(String(50))
    
    # For monitoring
    contains_contact_info = Column(Boolean, default=False)
    flagged = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.now)
    
    # Relationships
    job = relationship("Job", back_populates="messages", foreign_keys=[job_id])
    user = relationship("User", back_populates="job_messages", foreign_keys=[user_id])


class ClaimToken(Base):
    __tablename__ = 'claim_tokens'
    
    id = Column(Integer, primary_key=True)
    token_id = Column(String(50), unique=True, nullable=False)
    developer_id = Column(Integer, ForeignKey('developers.id'))
    job_id = Column(Integer, ForeignKey('jobs.id'))
    price = Column(Float, nullable=False)
    payment_method = Column(Enum(PaymentMethod))
    payment_reference = Column(String(200))
    is_used = Column(Boolean, default=False)
    used_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.now)
    
    # Relationships
    developer = relationship("Developer", back_populates="claim_tokens", foreign_keys=[developer_id])
    job = relationship("Job", foreign_keys=[job_id])