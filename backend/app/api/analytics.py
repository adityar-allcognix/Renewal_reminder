"""
Analytics API Routes
"""

from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.database import get_db
from app.models import (
    Policy, PolicyStatus, 
    RenewalReminder, ReminderStatus,
    InteractionLog, OutreachLog
)
from app.schemas import (
    ReminderStats, ConversionStats, 
    EngagementStats, AnalyticsDashboard, DashboardStats
)
from app.models import Customer

router = APIRouter()


@router.get("/dashboard", response_model=AnalyticsDashboard)
async def get_analytics_dashboard(
    days: int = Query(30, description="Period in days"),
    db: AsyncSession = Depends(get_db)
):
    """Get comprehensive analytics dashboard."""
    period_end = date.today()
    period_start = period_end - timedelta(days=days)
    
    reminder_stats = await get_reminder_stats_data(db, period_start, period_end)
    conversion_stats = await get_conversion_stats_data(db, period_start, period_end)
    engagement_stats = await get_engagement_stats_data(db, period_start, period_end)
    
    return AnalyticsDashboard(
        reminder_stats=reminder_stats,
        conversion_stats=conversion_stats,
        engagement_stats=engagement_stats,
        period_start=period_start,
        period_end=period_end
    )


@router.get("/reminders/stats", response_model=ReminderStats)
async def get_reminder_stats(
    days: int = Query(30, description="Period in days"),
    db: AsyncSession = Depends(get_db)
):
    """Get reminder delivery statistics."""
    period_start = date.today() - timedelta(days=days)
    return await get_reminder_stats_data(db, period_start, date.today())


async def get_reminder_stats_data(
    db: AsyncSession, 
    period_start: date, 
    period_end: date
) -> ReminderStats:
    """Calculate reminder statistics."""
    start_dt = datetime.combine(period_start, datetime.min.time())
    end_dt = datetime.combine(period_end, datetime.max.time())
    
    # Total sent
    sent_query = select(func.count(RenewalReminder.id)).where(
        and_(
            RenewalReminder.status.in_([
                ReminderStatus.SENT, 
                ReminderStatus.DELIVERED
            ]),
            RenewalReminder.sent_at >= start_dt,
            RenewalReminder.sent_at <= end_dt
        )
    )
    sent_result = await db.execute(sent_query)
    total_sent = sent_result.scalar() or 0
    
    # Delivered
    delivered_query = select(func.count(RenewalReminder.id)).where(
        and_(
            RenewalReminder.status == ReminderStatus.DELIVERED,
            RenewalReminder.delivered_at >= start_dt,
            RenewalReminder.delivered_at <= end_dt
        )
    )
    delivered_result = await db.execute(delivered_query)
    delivered = delivered_result.scalar() or 0
    
    # Failed
    failed_query = select(func.count(RenewalReminder.id)).where(
        and_(
            RenewalReminder.status == ReminderStatus.FAILED,
            RenewalReminder.updated_at >= start_dt,
            RenewalReminder.updated_at <= end_dt
        )
    )
    failed_result = await db.execute(failed_query)
    failed = failed_result.scalar() or 0
    
    # Pending
    pending_query = select(func.count(RenewalReminder.id)).where(
        RenewalReminder.status == ReminderStatus.PENDING
    )
    pending_result = await db.execute(pending_query)
    pending = pending_result.scalar() or 0
    
    delivery_rate = (delivered / total_sent * 100) if total_sent > 0 else 0.0
    
    return ReminderStats(
        total_sent=total_sent,
        delivered=delivered,
        failed=failed,
        pending=pending,
        delivery_rate=round(delivery_rate, 2)
    )


@router.get("/conversions/stats", response_model=ConversionStats)
async def get_conversion_stats(
    days: int = Query(30, description="Period in days"),
    db: AsyncSession = Depends(get_db)
):
    """Get renewal conversion statistics."""
    period_start = date.today() - timedelta(days=days)
    return await get_conversion_stats_data(db, period_start, date.today())


async def get_conversion_stats_data(
    db: AsyncSession,
    period_start: date,
    period_end: date
) -> ConversionStats:
    """Calculate conversion statistics."""
    # Policies that were due in the period
    due_query = select(func.count(Policy.id)).where(
        and_(
            Policy.renewal_date >= period_start,
            Policy.renewal_date <= period_end
        )
    )
    due_result = await db.execute(due_query)
    policies_due = due_result.scalar() or 0
    
    # Renewed policies
    renewed_query = select(func.count(Policy.id)).where(
        and_(
            Policy.renewal_date >= period_start,
            Policy.renewal_date <= period_end,
            Policy.status == PolicyStatus.RENEWED
        )
    )
    renewed_result = await db.execute(renewed_query)
    renewed = renewed_result.scalar() or 0
    
    # Lapsed policies
    lapsed_query = select(func.count(Policy.id)).where(
        and_(
            Policy.renewal_date >= period_start,
            Policy.renewal_date <= period_end,
            Policy.status == PolicyStatus.LAPSED
        )
    )
    lapsed_result = await db.execute(lapsed_query)
    lapsed = lapsed_result.scalar() or 0
    
    # Pending
    pending = policies_due - renewed - lapsed
    
    conversion_rate = (renewed / policies_due * 100) if policies_due > 0 else 0.0
    
    return ConversionStats(
        policies_due=policies_due,
        renewed=renewed,
        lapsed=lapsed,
        pending=pending,
        conversion_rate=round(conversion_rate, 2)
    )


@router.get("/engagement/stats", response_model=EngagementStats)
async def get_engagement_stats(
    days: int = Query(30, description="Period in days"),
    db: AsyncSession = Depends(get_db)
):
    """Get customer engagement statistics."""
    period_start = date.today() - timedelta(days=days)
    return await get_engagement_stats_data(db, period_start, date.today())


async def get_engagement_stats_data(
    db: AsyncSession,
    period_start: date,
    period_end: date
) -> EngagementStats:
    """Calculate engagement statistics."""
    start_dt = datetime.combine(period_start, datetime.min.time())
    end_dt = datetime.combine(period_end, datetime.max.time())
    
    # Total interactions
    interactions_query = select(func.count(InteractionLog.id)).where(
        and_(
            InteractionLog.created_at >= start_dt,
            InteractionLog.created_at <= end_dt
        )
    )
    interactions_result = await db.execute(interactions_query)
    total_interactions = interactions_result.scalar() or 0
    
    # Average response time
    avg_time_query = select(func.avg(InteractionLog.response_time_ms)).where(
        and_(
            InteractionLog.created_at >= start_dt,
            InteractionLog.created_at <= end_dt
        )
    )
    avg_time_result = await db.execute(avg_time_query)
    avg_response_time = avg_time_result.scalar() or 0.0
    
    # Positive feedback rate
    positive_query = select(func.count(InteractionLog.id)).where(
        and_(
            InteractionLog.created_at >= start_dt,
            InteractionLog.created_at <= end_dt,
            InteractionLog.was_helpful == True
        )
    )
    positive_result = await db.execute(positive_query)
    positive_count = positive_result.scalar() or 0
    
    rated_query = select(func.count(InteractionLog.id)).where(
        and_(
            InteractionLog.created_at >= start_dt,
            InteractionLog.created_at <= end_dt,
            InteractionLog.was_helpful.isnot(None)
        )
    )
    rated_result = await db.execute(rated_query)
    rated_count = rated_result.scalar() or 0
    
    positive_rate = (positive_count / rated_count * 100) if rated_count > 0 else 0.0
    
    # Unique customers
    unique_query = select(func.count(func.distinct(InteractionLog.customer_id))).where(
        and_(
            InteractionLog.created_at >= start_dt,
            InteractionLog.created_at <= end_dt
        )
    )
    unique_result = await db.execute(unique_query)
    unique_customers = unique_result.scalar() or 0
    
    queries_per_customer = (
        total_interactions / unique_customers if unique_customers > 0 else 0.0
    )
    
    return EngagementStats(
        total_interactions=total_interactions,
        avg_response_time_ms=round(avg_response_time, 2),
        positive_feedback_rate=round(positive_rate, 2),
        queries_per_customer=round(queries_per_customer, 2)
    )


@router.get("/policies/by-status")
async def get_policies_by_status(
    db: AsyncSession = Depends(get_db)
):
    """Get policy count grouped by status."""
    query = (
        select(Policy.status, func.count(Policy.id))
        .group_by(Policy.status)
    )
    result = await db.execute(query)
    
    return {
        status.value: count 
        for status, count in result.all()
    }


@router.get("/reminders/by-channel")
async def get_reminders_by_channel(
    days: int = Query(30, description="Period in days"),
    db: AsyncSession = Depends(get_db)
):
    """Get reminder count grouped by channel."""
    start_dt = datetime.combine(
        date.today() - timedelta(days=days), 
        datetime.min.time()
    )
    
    query = (
        select(RenewalReminder.channel, func.count(RenewalReminder.id))
        .where(RenewalReminder.created_at >= start_dt)
        .group_by(RenewalReminder.channel)
    )
    result = await db.execute(query)
    
    return {
        channel.value: count 
        for channel, count in result.all()
    }


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db)
):
    """Get dashboard statistics for the frontend."""
    today = date.today()
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())
    
    # Total customers
    customers_query = select(func.count(Customer.id))
    customers_result = await db.execute(customers_query)
    total_customers = customers_result.scalar() or 0
    
    # Active policies
    active_query = select(func.count(Policy.id)).where(
        Policy.status == PolicyStatus.ACTIVE
    )
    active_result = await db.execute(active_query)
    active_policies = active_result.scalar() or 0
    
    # Pending renewals
    pending_query = select(func.count(Policy.id)).where(
        Policy.status == PolicyStatus.PENDING_RENEWAL
    )
    pending_result = await db.execute(pending_query)
    pending_renewals = pending_result.scalar() or 0
    
    # Expiring soon (within 30 days)
    expiring_query = select(func.count(Policy.id)).where(
        and_(
            Policy.status == PolicyStatus.ACTIVE,
            Policy.end_date <= today + timedelta(days=30),
            Policy.end_date >= today
        )
    )
    expiring_result = await db.execute(expiring_query)
    expiring_soon = expiring_result.scalar() or 0
    
    # Renewal rate (renewed / (renewed + lapsed) * 100)
    renewed_query = select(func.count(Policy.id)).where(
        Policy.status == PolicyStatus.RENEWED
    )
    renewed_result = await db.execute(renewed_query)
    renewed_count = renewed_result.scalar() or 0
    
    lapsed_query = select(func.count(Policy.id)).where(
        Policy.status == PolicyStatus.LAPSED
    )
    lapsed_result = await db.execute(lapsed_query)
    lapsed_count = lapsed_result.scalar() or 0
    
    total_decided = renewed_count + lapsed_count
    renewal_rate = (renewed_count / total_decided * 100) if total_decided > 0 else 0.0
    
    # Average engagement score
    engagement_query = select(func.avg(Customer.engagement_score))
    engagement_result = await db.execute(engagement_query)
    avg_engagement = engagement_result.scalar() or 0.0
    
    # Reminders sent today
    sent_today_query = select(func.count(RenewalReminder.id)).where(
        and_(
            RenewalReminder.sent_at >= today_start,
            RenewalReminder.sent_at <= today_end,
            RenewalReminder.status.in_([
                ReminderStatus.SENT,
                ReminderStatus.DELIVERED
            ])
        )
    )
    sent_today_result = await db.execute(sent_today_query)
    reminders_sent_today = sent_today_result.scalar() or 0
    
    # Reminders pending
    pending_reminders_query = select(func.count(RenewalReminder.id)).where(
        RenewalReminder.status == ReminderStatus.PENDING
    )
    pending_reminders_result = await db.execute(pending_reminders_query)
    reminders_pending = pending_reminders_result.scalar() or 0
    
    return DashboardStats(
        total_customers=total_customers,
        active_policies=active_policies,
        pending_renewals=pending_renewals,
        expiring_soon=expiring_soon,
        renewal_rate=round(renewal_rate, 1),
        avg_engagement_score=round(float(avg_engagement), 1),
        reminders_sent_today=reminders_sent_today,
        reminders_pending=reminders_pending
    )
