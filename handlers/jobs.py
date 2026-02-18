# handlers/jobs.py - FREE JOB POSTING (NO DEPOSIT)
import logging
import uuid
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database.db import create_session
from database.models import User, Job
from config import JOB_CATEGORIES

logger = logging.getLogger(__name__)

# Conversation states
POST_JOB_TITLE, POST_JOB_DESCRIPTION, POST_JOB_OUTCOME, POST_JOB_BUDGET, POST_JOB_TIMELINE, POST_JOB_CATEGORY = range(6)

async def start_job_posting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start job posting process"""
    user_id = update.effective_user.id

    context.user_data['job_flow'] = {
        'step': 'title',
        'job_data': {}
    }

    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "📝 Let's create your job posting!\n\n"
        "First, give your job a clear title:\n"
        "Example: 'Need a Telegram bot for customer support'",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancel", callback_data="menu_main")]
        ])
    )

    return POST_JOB_TITLE

async def receive_job_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    title = update.message.text.strip()
    if len(title) < 10:
        await update.message.reply_text("Please provide a more descriptive title (at least 10 characters).")
        return POST_JOB_TITLE

    context.user_data['job_flow']['job_data']['title'] = title
    context.user_data['job_flow']['step'] = 'description'

    await update.message.reply_text(
        "📋 Great! Now provide a detailed description of the job:\n\n"
        "Include:\n• Specific tasks\n• Technical requirements\n• Any special instructions\n\n"
        "The more details, the better developers can understand your needs.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancel", callback_data="menu_main")]
        ])
    )
    return POST_JOB_DESCRIPTION

async def receive_job_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    description = update.message.text.strip()
    if len(description) < 50:
        await update.message.reply_text("Please provide a more detailed description (at least 50 characters).")
        return POST_JOB_DESCRIPTION

    context.user_data['job_flow']['job_data']['description'] = description
    context.user_data['job_flow']['step'] = 'outcome'

    await update.message.reply_text(
        "🎯 What's the expected outcome?\n\n"
        "Describe what success looks like:\n"
        "• What should be delivered?\n"
        "• How will you know it's complete?\n"
        "• Any specific metrics or requirements?",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancel", callback_data="menu_main")]
        ])
    )
    return POST_JOB_OUTCOME

async def receive_job_outcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    outcome = update.message.text.strip()
    context.user_data['job_flow']['job_data']['expected_outcome'] = outcome
    context.user_data['job_flow']['step'] = 'budget'

    await update.message.reply_text(
        "💰 Set your budget for this job:\n\n"
        "Enter the total amount you're willing to pay (in your currency).\n\n"
        "Example: 150.00\n\n"
        "(You can also write 'Negotiable' or skip by sending '0')",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancel", callback_data="menu_main")]
        ])
    )
    return POST_JOB_BUDGET

async def receive_job_budget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    budget_text = update.message.text.strip()
    try:
        budget = float(budget_text)
        if budget < 0:
            budget = 0.0
    except ValueError:
        budget = 0.0  # treat as negotiable

    context.user_data['job_flow']['job_data']['budget'] = budget
    context.user_data['job_flow']['step'] = 'timeline'

    await update.message.reply_text(
        "⏰ What's your expected timeline?\n\n"
        "Examples:\n• 'Within 7 days'\n• '2-3 weeks'\n• 'ASAP'\n• 'Flexible'",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancel", callback_data="menu_main")]
        ])
    )
    return POST_JOB_TIMELINE

async def receive_job_timeline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    timeline = update.message.text.strip()
    context.user_data['job_flow']['job_data']['timeline'] = timeline
    context.user_data['job_flow']['step'] = 'category'

    keyboard = []
    for i in range(0, len(JOB_CATEGORIES), 2):
        row = []
        row.append(InlineKeyboardButton(JOB_CATEGORIES[i], callback_data=f"job_category_{i}"))
        if i+1 < len(JOB_CATEGORIES):
            row.append(InlineKeyboardButton(JOB_CATEGORIES[i+1], callback_data=f"job_category_{i+1}"))
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="menu_main")])

    await update.message.reply_text(
        "📂 Select a category for your job:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return POST_JOB_CATEGORY

async def select_job_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    category_idx = int(query.data.replace("job_category_", ""))
    category = JOB_CATEGORIES[category_idx]
    job_data = context.user_data['job_flow']['job_data']

    # Preview – NO DEPOSIT INFORMATION
    preview_text = (
        f"📋 <b>Job Posting Preview</b>\n\n"
        f"<b>Title:</b> {job_data['title']}\n"
        f"<b>Category:</b> {category}\n"
        f"<b>Budget:</b> ${job_data.get('budget', 0):.2f}\n"
        f"<b>Timeline:</b> {job_data['timeline']}\n\n"
        f"<b>Description:</b>\n{job_data['description'][:200]}...\n\n"
        f"<b>Expected Outcome:</b>\n{job_data.get('expected_outcome', 'Not specified')[:150]}...\n\n"
        "✅ <b>No deposit required</b> – posting is free.\n"
        "⏳ Your job will be reviewed by an admin and published shortly."
    )

    keyboard = [
        [InlineKeyboardButton("✅ Post Job", callback_data="confirm_job_post")],
        [InlineKeyboardButton("✏️ Edit Details", callback_data="edit_job_details")],
        [InlineKeyboardButton("❌ Cancel", callback_data="menu_main")]
    ]

    context.user_data['job_flow']['job_data']['category'] = category
    context.user_data['job_flow']['step'] = 'confirmation'

    await query.edit_message_text(
        preview_text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    return ConversationHandler.END

async def confirm_job_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Confirm and create job posting – FREE, no payment"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    job_data = context.user_data['job_flow']['job_data']

    db = create_session()
    try:
        user = db.query(User).filter(User.telegram_id == str(user_id)).first()
        if not user:
            await query.edit_message_text("User not found. Please /start again.")
            return

        job = Job(
            job_id=f"JOB{uuid.uuid4().hex[:8].upper()}",
            user_id=user.id,
            title=job_data['title'],
            description=job_data['description'],
            expected_outcome=job_data.get('expected_outcome', ''),
            category=job_data['category'],
            budget=job_data.get('budget', 0.0),
            expected_timeline=job_data['timeline'],
            status='pending_approval',      # admin must approve
            is_public=False                # not visible until approved
        )

        db.add(job)
        db.commit()

        # Clear session data
        context.user_data.pop('job_flow', None)

        await query.edit_message_text(
            f"✅ Job <b>{job.job_id}</b> created!\n\n"
            f"📋 <b>Title:</b> {job.title}\n"
            f"📂 <b>Category:</b> {job.category}\n"
            f"💰 <b>Budget:</b> ${job.budget:.2f}\n"
            f"⏰ <b>Timeline:</b> {job.expected_timeline}\n\n"
            f"Your job has been submitted for admin approval.\n"
            f"You will be notified once it is published.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 My Jobs", callback_data="my_jobs")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
            ])
        )

    except Exception as e:
        logger.error(f"Error creating job: {e}")
        await query.edit_message_text("❌ Error creating job. Please try again.")
        db.rollback()
    finally:
        db.close()

    return ConversationHandler.END

async def cancel_job_posting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel job posting"""
    context.user_data.pop('job_flow', None)

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            "❌ Job posting cancelled.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
            ])
        )
    elif update.message:
        await update.message.reply_text(
            "❌ Job posting cancelled.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
            ])
        )

    return ConversationHandler.END