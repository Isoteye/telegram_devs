# handlers/job_contact.py - FREE, shows job poster's contact info
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.db import create_session
from database.models import Job

logger = logging.getLogger(__name__)

async def contact_poster(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show contact information of the job poster"""
    query = update.callback_query
    await query.answer()

    job_id = query.data.replace("contact_poster_", "")
    db = create_session()
    try:
        job = db.query(Job).filter(Job.job_id == job_id).first()
        if not job:
            await query.edit_message_text("❌ Job not found.")
            return

        poster = job.user
        if not poster:
            await query.edit_message_text("❌ Poster information missing.")
            return

        # Build contact info
        contact_text = f"📬 **Contact Job Poster**\n\n"
        contact_text += f"📋 **Job:** {job.title}\n"
        contact_text += f"🔖 **Job ID:** `{job.job_id}`\n\n"

        # Telegram contact (username or ID)
        if poster.username:
            contact_text += f"📱 **Telegram:** @{poster.username}\n"
        else:
            contact_text += f"📱 **Telegram ID:** `{poster.telegram_id}`\n"
            contact_text += f"*(You can search this ID in Telegram)*\n"

        # Email if available
        if poster.email:
            contact_text += f"📧 **Email:** `{poster.email}`\n"

        contact_text += (
            f"\n⚠️ **Note:** All negotiations and work happen outside the platform. "
            f"The platform is not responsible for any agreements, payments, or disputes."
        )

        keyboard = [
            [InlineKeyboardButton("🔙 Back to Job", callback_data=f"view_job_{job.job_id}")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
        ]

        await query.edit_message_text(
            contact_text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except Exception as e:
        logger.error(f"Error showing contact info: {e}")
        await query.edit_message_text("❌ Could not retrieve contact information.")
    finally:
        db.close()