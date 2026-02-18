# handlers/my_jobs.py - FIXED IMPORTS
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from datetime import datetime

from database.db import create_session  # FIXED: Use create_session from database.db
from database.models import Job, User, JobClaim

logger = logging.getLogger(__name__)

async def show_my_jobs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's jobs"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    db = create_session()  # FIXED: Use create_session()
    try:
        # Get user
        user = db.query(User).filter(User.telegram_id == str(user_id)).first()
        
        if not user:
            await query.edit_message_text("User not found.")
            return
        
        # Get user's jobs
        jobs = db.query(Job).filter(Job.user_id == user.id).order_by(Job.created_at.desc()).all()
        
        if not jobs:
            await query.edit_message_text(
                "📭 You haven't posted any jobs yet.\n\n"
                "Create your first job posting to get started!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📝 Post a Job", callback_data="post_job")],
                    [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
                ])
            )
            return
        
        text = "📋 <b>My Jobs</b>\n\n"
        
        for job in jobs:
            status_emoji = {
                'draft': '📝',
                'awaiting_deposit': '💳',
                'pending_approval': '⏳',
                'open': '🔓',
                'claimed': '🔒',
                'in_progress': '⚡',
                'delivered': '📦',
                'completed': '✅',
                'cancelled': '❌',
                'disputed': '⚖️',
                'refunded': '💸'
            }.get(job.status, '❓')
            
            text += (
                f"{status_emoji} <b>{job.title}</b>\n"
                f"   📅 {job.created_at.strftime('%Y-%m-%d')} | "
                f"💰 ${job.budget:.2f} | "
                f"📊 {job.status.replace('_', ' ').title()}\n\n"
            )
        
        # Create keyboard with job buttons
        keyboard = []
        for job in jobs:
            keyboard.append([
                InlineKeyboardButton(
                    f"{job.job_id} - {job.title[:30]}",
                    callback_data=f"my_job_{job.job_id}"
                )
            ])
        
        keyboard.append([
            InlineKeyboardButton("📝 Post New Job", callback_data="post_job"),
            InlineKeyboardButton("🔍 Browse Jobs", callback_data="job_board")
        ])
        keyboard.append([InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")])
        
        await query.edit_message_text(
            text,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except Exception as e:
        logger.error(f"Error showing my jobs: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading your jobs.")
    finally:
        db.close()

async def my_job_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show details of a specific job"""
    query = update.callback_query
    await query.answer()
    
    job_id = query.data.replace("my_job_", "")
    
    db = create_session()  # FIXED: Use create_session()
    try:
        job = db.query(Job).filter(Job.job_id == job_id).first()
        
        if not job:
            await query.edit_message_text("Job not found.")
            return
        
        # Get claim info if job is claimed
        claim = None
        if job.status in ['claimed', 'in_progress', 'delivered']:
            claim = db.query(JobClaim).filter(JobClaim.job_id == job.id).first()
        
        status_emoji = {
            'draft': '📝 Draft',
            'awaiting_deposit': '💳 Awaiting Deposit',
            'pending_approval': '⏳ Pending Approval',
            'open': '🔓 Open for Claims',
            'claimed': '🔒 Claimed',
            'in_progress': '⚡ In Progress',
            'delivered': '📦 Delivered',
            'completed': '✅ Completed',
            'cancelled': '❌ Cancelled',
            'disputed': '⚖️ Disputed',
            'refunded': '💸 Refunded'
        }.get(job.status, job.status)
        
        text = (
            f"📋 <b>Job Details</b>\n\n"
            f"<b>Job ID:</b> {job.job_id}\n"
            f"<b>Title:</b> {job.title}\n"
            f"<b>Status:</b> {status_emoji}\n"
            f"<b>Category:</b> {job.category}\n"
            f"<b>Budget:</b> ${job.budget:.2f}\n"
            f"<b>Deposit:</b> ${job.deposit_amount:.2f}\n"
            f"<b>Timeline:</b> {job.expected_timeline}\n"
            f"<b>Created:</b> {job.created_at.strftime('%Y-%m-%d %H:%M')}\n\n"
            f"<b>Description:</b>\n{job.description}\n\n"
            f"<b>Expected Outcome:</b>\n{job.expected_outcome}\n\n"
        )
        
        if claim and claim.developer:
            text += f"<b>Claimed by:</b> {claim.developer.user.first_name}\n"
            if claim.submitted_at:
                text += f"<b>Submitted:</b> {claim.submitted_at.strftime('%Y-%m-%d %H:%M')}\n"
        
        # Create appropriate buttons based on job status
        keyboard = []
        
        if job.status == 'awaiting_deposit':
            keyboard.append([
                InlineKeyboardButton("💳 Pay Deposit", callback_data=f"pay_deposit_job_{job.job_id}"),
                InlineKeyboardButton("❌ Cancel Job", callback_data=f"cancel_job_{job.job_id}")
            ])
        elif job.status == 'open':
            keyboard.append([
                InlineKeyboardButton("👀 View as Public", callback_data=f"view_job_{job.job_id}"),
                InlineKeyboardButton("❌ Cancel Job", callback_data=f"cancel_job_{job.job_id}")
            ])
        elif job.status == 'claimed' and claim:
            keyboard.append([
                InlineKeyboardButton("💬 Open Chat", callback_data=f"job_chat_{job.job_id}"),
                InlineKeyboardButton("📋 View Claim Details", callback_data=f"view_claim_{claim.claim_id}")
            ])
        elif job.status == 'delivered' and claim:
            keyboard.append([
                InlineKeyboardButton("✅ Accept Delivery", callback_data=f"accept_delivery_{claim.claim_id}"),
                InlineKeyboardButton("❌ Report Issue", callback_data=f"report_issue_{claim.claim_id}")
            ])
        
        keyboard.append([
            InlineKeyboardButton("⬅️ Back to My Jobs", callback_data="my_jobs"),
            InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")
        ])
        
        await query.edit_message_text(
            text,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except Exception as e:
        logger.error(f"Error showing job details: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading job details.")
    finally:
        db.close()

async def cancel_my_job(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel a job"""
    query = update.callback_query
    await query.answer()
    
    job_id = query.data.replace("cancel_job_", "")
    
    db = create_session()  # FIXED: Use create_session()
    try:
        job = db.query(Job).filter(Job.job_id == job_id).first()
        
        if not job:
            await query.edit_message_text("Job not found.")
            return
        
        # Check if job can be cancelled
        if job.status not in ['draft', 'awaiting_deposit', 'pending_approval', 'open']:
            await query.edit_message_text(
                f"Cannot cancel job with status: {job.status}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Back", callback_data=f"my_job_{job.job_id}")]
                ])
            )
            return
        
        # Update job status
        job.status = 'cancelled'
        db.commit()
        
        await query.edit_message_text(
            f"✅ Job '{job.title}' has been cancelled.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back to My Jobs", callback_data="my_jobs")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
            ])
        )
        
    except Exception as e:
        logger.error(f"Error cancelling job: {e}")
        await query.edit_message_text("❌ Error cancelling job.")
        db.rollback()
    finally:
        db.close()

# Add the show_job_board and view_job functions if they don't exist
async def show_job_board(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show job board with available jobs"""
    query = update.callback_query
    await query.answer()
    
    db = create_session()
    try:
        # Get open jobs
        jobs = db.query(Job).filter(
            Job.status == 'open',
            Job.is_public == True
        ).order_by(Job.created_at.desc()).all()
        
        if not jobs:
            await query.edit_message_text(
                "🔍 *Job Board*\n\n"
                "No open jobs available at the moment.\n\n"
                "Check back later or post your own job!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📝 Post a Job", callback_data="post_job")],
                    [InlineKeyboardButton("⬅️ Back", callback_data="menu_main")]
                ]),
                parse_mode='Markdown'
            )
            return
        
        text = "🔍 *Job Board*\n\n"
        text += f"Found *{len(jobs)}* open jobs:\n\n"
        
        for job in jobs[:10]:  # Show first 10 jobs
            text += (
                f"📋 *{job.title}*\n"
                f"   💰 Budget: ${job.budget:.2f}\n"
                f"   ⏰ Timeline: {job.expected_timeline}\n"
                f"   📊 Status: {job.status.replace('_', ' ').title()}\n\n"
            )
        
        keyboard = []
        
        # Add buttons for each job
        for job in jobs[:5]:  # Show buttons for first 5 jobs
            keyboard.append([
                InlineKeyboardButton(
                    f"📋 {job.title[:30]}... - ${job.budget:.2f}",
                    callback_data=f"view_job_{job.job_id}"
                )
            ])
        
        keyboard.append([
            InlineKeyboardButton("📝 Post a Job", callback_data="post_job"),
            InlineKeyboardButton("⬅️ Back", callback_data="menu_main")
        ])
        
        await query.edit_message_text(
            text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except Exception as e:
        logger.error(f"Error showing job board: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading job board.")
    finally:
        db.close()

async def view_job(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View a specific job from job board"""
    query = update.callback_query
    await query.answer()
    
    job_id = query.data.replace("view_job_", "")
    
    db = create_session()
    try:
        job = db.query(Job).filter(Job.job_id == job_id).first()
        
        if not job:
            await query.edit_message_text("Job not found.")
            return
        
        user = db.query(User).filter(User.id == job.user_id).first()
        
        text = (
            f"📋 *Job Details*\n\n"
            f"*Title:* {job.title}\n"
            f"*Posted by:* {user.first_name if user else 'Anonymous'}\n"
            f"*Budget:* ${job.budget:.2f}\n"
            f"*Deposit Required:* ${job.deposit_amount:.2f}\n"
            f"*Timeline:* {job.expected_timeline}\n"
            f"*Category:* {job.category}\n"
            f"*Status:* {job.status.replace('_', ' ').title()}\n"
            f"*Posted:* {job.created_at.strftime('%Y-%m-%d')}\n\n"
            f"*Description:*\n{job.description}\n\n"
            f"*Expected Outcome:*\n{job.expected_outcome}\n\n"
        )
        
        keyboard = [
            [InlineKeyboardButton("🔍 Browse More Jobs", callback_data="job_board")],
            [InlineKeyboardButton("📝 Post Your Own Job", callback_data="post_job")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
        ]
        
        await query.edit_message_text(
            text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except Exception as e:
        logger.error(f"Error viewing job: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading job details.")
    finally:
        db.close()