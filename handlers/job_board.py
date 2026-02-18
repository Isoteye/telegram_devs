# job_board.py - FREE JOB MARKETPLACE (no deposits, no claim tokens)
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.db import create_session
from database.models import Job, User

logger = logging.getLogger(__name__)

async def show_job_board(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show public job board with approved jobs"""
    query = update.callback_query
    await query.answer()

    db = create_session()
    try:
        # Get all approved and public jobs, newest first
        jobs = db.query(Job).filter(
            Job.is_public == True
        ).order_by(Job.created_at.desc()).limit(20).all()

        if not jobs:
            await query.edit_message_text(
                "📭 No jobs available at the moment.\n\n"
                "Be the first to post a job!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📝 Post a Job", callback_data="post_job")],
                    [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
                ])
            )
            return

        text = "📋 <b>Available Jobs</b>\n\n"
        for job in jobs:
            poster = db.query(User).filter(User.id == job.user_id).first()
            poster_name = poster.first_name if poster else "Anonymous"
            text += (
                f"🔹 <b>{job.title}</b>\n"
                f"   👤 {poster_name}\n"
                f"   💰 Budget: ${job.budget:.2f}\n"
                f"   ⏰ Timeline: {job.expected_timeline}\n\n"
            )

        # Build keyboard with each job as a button
        keyboard = []
        for job in jobs:
            keyboard.append([
                InlineKeyboardButton(
                    f"💰 ${job.budget:.0f} - {job.title[:30]}",
                    callback_data=f"view_job_{job.job_id}"
                )
            ])

        keyboard.append([
            InlineKeyboardButton("📝 Post a Job", callback_data="post_job"),
            InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")
        ])

        await query.edit_message_text(
            text,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except Exception as e:
        logger.error(f"Error showing job board: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading job board.")
    finally:
        db.close()


async def view_job_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show full job details – NO blurred content, NO claim token"""
    query = update.callback_query
    await query.answer()

    job_id = query.data.replace("view_job_", "")
    db = create_session()
    try:
        job = db.query(Job).filter(Job.job_id == job_id).first()
        if not job:
            await query.edit_message_text("❌ Job not found.")
            return

        # Get job poster info
        poster = db.query(User).filter(User.id == job.user_id).first()
        poster_name = poster.first_name if poster else "Anonymous"
        poster_username = f"@{poster.username}" if poster and poster.username else "Not shared"

        # Full details – everything is visible (no paywall)
        text = (
            f"📋 <b>Job Details</b>\n\n"
            f"<b>Job ID:</b> <code>{job.job_id}</code>\n"
            f"<b>Title:</b> {job.title}\n"
            f"<b>Category:</b> {job.category}\n"
            f"<b>Posted by:</b> {poster_name}\n"
            f"<b>Budget:</b> ${job.budget:.2f}\n"
            f"<b>Timeline:</b> {job.expected_timeline}\n\n"
            f"<b>Description:</b>\n{job.description}\n\n"
            f"<b>Expected Outcome:</b>\n{job.expected_outcome or 'Not specified'}\n\n"
            f"<b>Status:</b> {'Open' if job.is_public else 'Under review'}\n\n"
        )

        # Buttons: Contact Poster, Back to Jobs, Main Menu
        keyboard = [
            [InlineKeyboardButton("📬 Contact Poster", callback_data=f"contact_poster_{job.job_id}")],
            [InlineKeyboardButton("⬅️ Back to Jobs", callback_data="job_board")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
        ]

        # If the current user is the job poster, show additional management options
        current_user = db.query(User).filter(User.telegram_id == str(update.effective_user.id)).first()
        if current_user and current_user.id == job.user_id:
            keyboard.insert(0, [
                InlineKeyboardButton("✏️ Edit Job", callback_data=f"edit_job_{job.job_id}"),
                InlineKeyboardButton("❌ Cancel Job", callback_data=f"cancel_job_{job.job_id}")
            ])

        await query.edit_message_text(
            text,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except Exception as e:
        logger.error(f"Error viewing job details: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading job details.")
    finally:
        db.close()


# Optional: simple pagination (if you want to keep it, otherwise remove)
# This is a placeholder – you can expand it later.
async def handle_job_board_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle pagination for job board (simple implementation)"""
    query = update.callback_query
    await query.answer()
    # For now, just reload the job board
    await show_job_board(update, context)