
import sys
import os
import traceback
import logging
import re

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

logger = logging.getLogger(__name__)

def create_application():
    """Create and configure the Telegram application"""
    try:
        from config import TELEGRAM_TOKEN

        if not TELEGRAM_TOKEN or TELEGRAM_TOKEN == "YOUR_BOT_TOKEN_HERE":
            print("❌ ERROR: Please set your Telegram bot token in .env file")
            if not os.path.exists(".env"):
                with open(".env", "w") as f:
                    f.write("TELEGRAM_TOKEN=YOUR_BOT_TOKEN_HERE\n")
                print("   Created .env file. Please edit it with your bot token.")
            return None

        print(f"✅ Using bot token: {TELEGRAM_TOKEN[:10]}...")

        application = (
            ApplicationBuilder()
            .token(TELEGRAM_TOKEN)
            .read_timeout(30)
            .write_timeout(30)
            .connect_timeout(30)
            .pool_timeout(30)
            .get_updates_read_timeout(30)
            .get_updates_write_timeout(30)
            .get_updates_connect_timeout(30)
            .get_updates_pool_timeout(30)
            .build()
        )

        # ========== IMPORT HANDLERS ==========
        print("DEBUG: Importing handlers...")

        # Basic commands
        from handlers.commands import start_command, menu_command, help_command, debug_command
        from handlers.developer_commands import developer_command, claim_command
        from handlers.admin import admin_command, admin_panel as full_admin_panel
        from handlers.payment import verify_command
        from handlers.custom_payments import verify_deposit_command
        from order_management import manual_refund_command, confirm_refund_callback

        # Job marketplace imports (FREE VERSION)
        try:
            from handlers.jobs import (
                start_job_posting, receive_job_title, receive_job_description,
                receive_job_outcome, receive_job_budget, receive_job_timeline,
                select_job_category, confirm_job_post, cancel_job_posting,
                POST_JOB_TITLE, POST_JOB_DESCRIPTION, POST_JOB_OUTCOME,
                POST_JOB_BUDGET, POST_JOB_TIMELINE, POST_JOB_CATEGORY
            )
            print("✅ Job posting handlers imported successfully")
        except ImportError as e:
            print(f"⚠️ Could not import job posting handlers: {e}")
            start_job_posting = cancel_job_posting = None
            POST_JOB_TITLE = POST_JOB_DESCRIPTION = POST_JOB_OUTCOME = None
            POST_JOB_BUDGET = POST_JOB_TIMELINE = POST_JOB_CATEGORY = None
            receive_job_title = receive_job_description = receive_job_outcome = None
            receive_job_budget = receive_job_timeline = select_job_category = confirm_job_post = None

        # Job board handlers
        try:
            from handlers.job_board import (
                show_job_board, view_job_details, handle_job_board_navigation
            )
            print("✅ Job board handlers imported successfully")
        except ImportError as e:
            print(f"⚠️ Could not import job board handlers: {e}")
            show_job_board = view_job_details = handle_job_board_navigation = None

        # My jobs handlers
        try:
            from handlers.my_jobs import show_my_jobs, my_job_details, cancel_my_job
            print("✅ My jobs handlers imported successfully")
        except ImportError as e:
            print(f"⚠️ Could not import my_jobs handlers: {e}")
            show_my_jobs = my_job_details = cancel_my_job = None

        # NEW: Contact poster handler (replaces claim_job)
        try:
            from handlers.job_contact import contact_poster
            print("✅ Contact poster handler imported successfully")
        except ImportError as e:
            print(f"⚠️ Could not import contact_poster: {e}")
            contact_poster = None

        # Custom request conversation
        from handlers.custom_requests import (
            request_custom_bot_start, handle_bot_description, handle_bot_features,
            handle_software_features_input, handle_budget_input, handle_timeline_selection,
            handle_submit_with_deposit, handle_back_button, cancel_custom_request,
            REQUEST_SOFTWARE_DESCRIPTION, REQUEST_SOFTWARE_FEATURES,
            REQUEST_SOFTWARE_BUDGET, REQUEST_SOFTWARE_TIMELINE
        )

        # Payment handlers (for bot purchases and custom requests)
        from handlers.payment import handle_paystack_payment, handle_bank_transfer, handle_email_for_paystack
        from handlers.custom_payments import handle_pay_deposit_callback, handle_custom_deposit_email

        # Currency handlers
        from handlers.currency import handle_country_selection, handle_change_currency, handle_set_currency

        # Menu callbacks
        from handlers.menu_callbacks import (
            handle_menu_main, handle_buy_bot, show_bot_categories, show_bot_details,
            show_buy_options, show_featured_bots, show_user_orders, show_order_details,
            show_my_requests, become_developer_callback, show_support, show_about,
            generic_callback   # ⚠️ This will be placed LAST
        )

        # Custom request details
        from handlers.custom_payments import show_custom_request_details

        # Developer dashboard
        from handlers.developer import (
            developer_dashboard, dev_my_orders, dev_order_detail, dev_start_order,
            dev_complete_order, dev_earnings, dev_edit_profile_start, dev_toggle_availability,
            dev_request_payout, dev_update_email_start, get_developer_conversation_handler,
            handle_dev_available_orders
        )

        # ========== BASIC COMMAND HANDLERS ==========
        print("DEBUG: Adding basic command handlers...")
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("menu", menu_command))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("debug", debug_command))
        application.add_handler(CommandHandler("developer", developer_command))
        application.add_handler(CommandHandler("claim", claim_command))
        application.add_handler(CommandHandler("admin", admin_command))
        application.add_handler(CommandHandler("verify", verify_command))
        # /verify_deposit REMOVED – no longer needed for jobs
        application.add_handler(CommandHandler("refund", manual_refund_command))

        # ========== CONVERSATION HANDLERS ==========
        # 1. Job posting conversation (FREE, no deposit)
        if start_job_posting and cancel_job_posting:
            print("DEBUG: Adding job posting conversation handler...")
            try:
                job_posting_conv_handler = ConversationHandler(
                    entry_points=[CallbackQueryHandler(start_job_posting, pattern="^post_job$")],
                    states={
                        POST_JOB_TITLE: [
                            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_job_title),
                            CallbackQueryHandler(cancel_job_posting, pattern="^menu_main$")
                        ],
                        POST_JOB_DESCRIPTION: [
                            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_job_description),
                            CallbackQueryHandler(cancel_job_posting, pattern="^menu_main$")
                        ],
                        POST_JOB_OUTCOME: [
                            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_job_outcome),
                            CallbackQueryHandler(cancel_job_posting, pattern="^menu_main$")
                        ],
                        POST_JOB_BUDGET: [
                            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_job_budget),
                            CallbackQueryHandler(cancel_job_posting, pattern="^menu_main$")
                        ],
                        POST_JOB_TIMELINE: [
                            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_job_timeline),
                            CallbackQueryHandler(cancel_job_posting, pattern="^menu_main$")
                        ],
                        POST_JOB_CATEGORY: [
                            CallbackQueryHandler(select_job_category, pattern="^job_category_"),
                            CallbackQueryHandler(cancel_job_posting, pattern="^menu_main$")
                        ],
                    },
                    fallbacks=[
                        CallbackQueryHandler(cancel_job_posting, pattern="^menu_main$"),
                        CallbackQueryHandler(confirm_job_post, pattern="^confirm_job_post$"),
                        CommandHandler("cancel", cancel_job_posting)
                    ],
                    allow_reentry=True
                )
                application.add_handler(job_posting_conv_handler)
                print("✅ Job posting conversation handler registered")
            except Exception as e:
                print(f"⚠️ Could not register job posting handler: {e}")

        # 2. Custom request conversation (unchanged, with deposit)
        print("DEBUG: Adding custom request conversation handler...")
        custom_request_conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(request_custom_bot_start, pattern="^start_custom_request$")],
            states={
                REQUEST_SOFTWARE_DESCRIPTION: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, handle_bot_description)
                ],
                REQUEST_SOFTWARE_FEATURES: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        lambda update, context: (
                            handle_software_features_input(update, context)
                            if context.user_data.get('custom_software', {}).get('expecting_features')
                            else handle_bot_features(update, context)
                        )
                    )
                ],
                REQUEST_SOFTWARE_BUDGET: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, handle_budget_input),
                    CallbackQueryHandler(handle_back_button, pattern="^back_to_description$")
                ],
                REQUEST_SOFTWARE_TIMELINE: [
                    CallbackQueryHandler(handle_timeline_selection, pattern="^timeline_"),
                    CallbackQueryHandler(handle_back_button, pattern="^back_to_budget$")
                ],
            },
            fallbacks=[
                CallbackQueryHandler(cancel_custom_request, pattern="^menu_main$"),
                CallbackQueryHandler(handle_submit_with_deposit, pattern="^submit_with_deposit$"),
                CommandHandler("cancel", cancel_custom_request)
            ],
            allow_reentry=True
        )
        application.add_handler(custom_request_conv_handler)
        print("✅ Custom request conversation handler registered")

        # 3. Developer application conversation (unchanged)
        print("DEBUG: Adding developer application handlers...")
        try:
            from developer_handlers import (
                start_developer_application, receive_developer_skills, receive_portfolio,
                receive_github, receive_hourly_rate, cancel_developer_application,
                dev_application_status, DEV_APP_SKILLS, DEV_APP_PORTFOLIO,
                DEV_APP_GITHUB, DEV_APP_HOURLY_RATE
            )
            dev_application_conv_handler = ConversationHandler(
                entry_points=[
                    CallbackQueryHandler(start_developer_application, pattern="^start_developer_application$")
                ],
                states={
                    DEV_APP_SKILLS: [
                        MessageHandler(filters.TEXT & ~filters.COMMAND, receive_developer_skills)
                    ],
                    DEV_APP_PORTFOLIO: [
                        MessageHandler(filters.TEXT & ~filters.COMMAND, receive_portfolio)
                    ],
                    DEV_APP_GITHUB: [
                        MessageHandler(filters.TEXT & ~filters.COMMAND, receive_github)
                    ],
                    DEV_APP_HOURLY_RATE: [
                        MessageHandler(filters.TEXT & ~filters.COMMAND, receive_hourly_rate)
                    ],
                },
                fallbacks=[
                    CallbackQueryHandler(cancel_developer_application, pattern="^menu_main$"),
                    CommandHandler("cancel", cancel_developer_application)
                ],
                allow_reentry=True
            )
            application.add_handler(dev_application_conv_handler)
            application.add_handler(CallbackQueryHandler(dev_application_status, pattern="^dev_application_status$"))
            print("✅ Developer application handlers registered")
        except ImportError as e:
            print(f"⚠️ Could not import developer_handlers: {e}")

        # 4. Developer edit profile conversation (unchanged)
        print("DEBUG: Registering developer conversation handler for editing profile...")
        try:
            dev_conversation_handler = get_developer_conversation_handler()
            application.add_handler(dev_conversation_handler)
            print("✅ Developer conversation handler registered")
        except Exception as e:
            print(f"⚠️ Could not register developer conversation handler: {e}")

        # ========== PAYMENT CALLBACK HANDLERS ==========
        # These are for bot purchases and custom request deposits – NOT for jobs
        print("DEBUG: Adding payment callback handlers...")
        application.add_handler(CallbackQueryHandler(handle_paystack_payment, pattern="^paystack_bot_"))
        application.add_handler(CallbackQueryHandler(handle_bank_transfer, pattern="^bank_transfer_"))
        application.add_handler(CallbackQueryHandler(handle_pay_deposit_callback, pattern="^pay_deposit_"))
        application.add_handler(CallbackQueryHandler(handle_submit_with_deposit, pattern="^submit_with_deposit$"))
        # NOTE: verify_deposit_command callback ("^vd_") and job deposit handlers are REMOVED

        async def handle_payment_email_only(update: Update, context: ContextTypes.DEFAULT_TYPE):
            try:
                text = update.message.text.strip()
                email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
                is_payment_flow = (
                    context.user_data.get('awaiting_email') or
                    context.user_data.get('awaiting_paystack_email') or
                    context.user_data.get('awaiting_deposit_email') or
                    context.user_data.get('awaiting_email_for_custom_deposit')   # ✅ ADD THIS LINE
                )
                if is_payment_flow and re.match(email_pattern, text):
                    # Only custom deposit email handler
                    return await handle_custom_deposit_email(update, context)
                return
            except Exception as e:
                logger.error(f"Error in payment email handler: {e}")       

        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_payment_email_only
        ))

        # ========== CURRENCY HANDLERS ==========
        application.add_handler(CallbackQueryHandler(handle_country_selection, pattern="^country_"))
        application.add_handler(CallbackQueryHandler(handle_change_currency, pattern="^change_currency$"))
        application.add_handler(CallbackQueryHandler(handle_set_currency, pattern="^set_currency_"))

        # ========== JOB MARKETPLACE CALLBACK HANDLERS ==========
        print("DEBUG: Adding job marketplace callback handlers...")
        if show_job_board:
            application.add_handler(CallbackQueryHandler(show_job_board, pattern="^job_board$"))
            application.add_handler(CallbackQueryHandler(show_job_board, pattern="^job_board_"))
        if view_job_details:
            application.add_handler(CallbackQueryHandler(view_job_details, pattern="^view_job_"))
        if show_my_jobs:
            application.add_handler(CallbackQueryHandler(show_my_jobs, pattern="^my_jobs$"))
        if my_job_details:
            application.add_handler(CallbackQueryHandler(my_job_details, pattern="^my_job_"))
        if cancel_my_job:
            application.add_handler(CallbackQueryHandler(cancel_my_job, pattern="^cancel_job_"))
        if handle_job_board_navigation:
            application.add_handler(CallbackQueryHandler(handle_job_board_navigation, pattern="^job_board_page_"))
        if confirm_job_post:
            application.add_handler(CallbackQueryHandler(confirm_job_post, pattern="^confirm_job_post$"))

        # NEW: Contact poster handler – replaces claim_job
        if contact_poster:
            application.add_handler(CallbackQueryHandler(contact_poster, pattern="^contact_poster_"))
            print("✅ Contact poster handler registered")

        # ========== OTHER CALLBACK HANDLERS ==========
        print("DEBUG: Adding other callback handlers...")
        application.add_handler(CallbackQueryHandler(handle_menu_main, pattern="^menu_main$"))
        application.add_handler(CallbackQueryHandler(handle_buy_bot, pattern="^buy_bot$"))
        application.add_handler(CallbackQueryHandler(show_bot_categories, pattern="^category_"))
        application.add_handler(CallbackQueryHandler(show_bot_details, pattern="^view_bot_"))
        application.add_handler(CallbackQueryHandler(show_buy_options, pattern="^buy_options_"))
        application.add_handler(CallbackQueryHandler(show_featured_bots, pattern="^featured_bots$"))
        application.add_handler(CallbackQueryHandler(show_user_orders, pattern="^my_orders$"))
        application.add_handler(CallbackQueryHandler(show_order_details, pattern="^order_"))
        application.add_handler(CallbackQueryHandler(show_my_requests, pattern="^my_requests$"))
        application.add_handler(CallbackQueryHandler(show_custom_request_details, pattern="^request_"))
        application.add_handler(CallbackQueryHandler(show_support, pattern="^support$"))
        application.add_handler(CallbackQueryHandler(show_about, pattern="^about$"))

        # ========== DEVELOPER DASHBOARD HANDLERS ==========
        print("DEBUG: Registering developer dashboard handlers...")
        application.add_handler(CallbackQueryHandler(developer_dashboard, pattern="^dev_dashboard$"))
        application.add_handler(CallbackQueryHandler(dev_my_orders, pattern="^dev_my_orders$"))
        application.add_handler(CallbackQueryHandler(dev_order_detail, pattern="^dev_order_detail_"))
        application.add_handler(CallbackQueryHandler(dev_start_order, pattern="^dev_start_order_"))
        application.add_handler(CallbackQueryHandler(dev_complete_order, pattern="^dev_complete_order_"))
        application.add_handler(CallbackQueryHandler(dev_edit_profile_start, pattern="^dev_edit_profile_start$"))
        application.add_handler(CallbackQueryHandler(dev_earnings, pattern="^dev_earnings$"))
        application.add_handler(CallbackQueryHandler(dev_toggle_availability, pattern="^dev_toggle_availability$"))
        application.add_handler(CallbackQueryHandler(dev_request_payout, pattern="^dev_request_payout$"))
        application.add_handler(CallbackQueryHandler(dev_update_email_start, pattern="^dev_update_email_"))
        application.add_handler(CallbackQueryHandler(handle_dev_available_orders, pattern="^dev_available_orders$"))

        # ========== ADMIN PANEL ==========
        application.add_handler(CallbackQueryHandler(full_admin_panel, pattern="^admin_panel$"))
        application.add_handler(CallbackQueryHandler(debug_command, pattern="^admin_debug$"))

        # ========== REFUND CONFIRMATION ==========
        application.add_handler(CallbackQueryHandler(confirm_refund_callback, pattern="^confirm_refund_"))
        application.add_handler(CallbackQueryHandler(confirm_refund_callback, pattern="^cancel_refund$"))

        # ========== VERIFY PAYMENT HANDLERS ==========
        application.add_handler(CallbackQueryHandler(verify_command, pattern="^verify_payment_"))

        # ========== ADMIN CALLBACKS – FULLY REGISTERED ==========
        print("DEBUG: Registering ALL admin callbacks...")
        from handlers.admin import (
            # Main panels
            admin_stats, admin_stats_detailed,
            admin_orders, admin_view_orders, admin_order_detail,
            admin_approve_payment, admin_reject_payment,
            admin_assign_developer, admin_assign_dev_confirm, admin_complete_order,
            admin_orders_pending, admin_orders_completed, admin_orders_cancelled,
            admin_orders_assigned, admin_search_order,
            admin_developers, admin_view_developers, admin_developer_detail,
            admin_active_developers, admin_inactive_developers,
            admin_remove_developer, admin_developer_stats,
            admin_dev_busy, admin_dev_deactivate, admin_dev_activate,
            admin_dev_edit, admin_dev_earnings, admin_dev_payout,
            admin_remove_dev,
            admin_developer_requests, admin_dev_requests_pending,
            admin_dev_review_request, admin_dev_approve_request, admin_dev_reject_request,
            admin_dev_requests_approved, admin_dev_requests_rejected,
            admin_dev_requests_stats, admin_dev_notes, admin_dev_contact,
            admin_custom_requests, admin_custom_requests_pending,
            admin_custom_request_detail, admin_custom_approve,
            admin_custom_requests_review, admin_custom_requests_approved,
            admin_custom_requests_rejected, admin_custom_requests_stats,
            admin_custom_review, admin_custom_reject, admin_custom_assign,
            admin_custom_notes, admin_custom_contact,
            admin_broadcast_start, admin_broadcast_confirm, admin_broadcast_cancel,
            admin_bots, admin_view_bots, admin_bot_detail,
            admin_bot_disable, admin_bot_enable, admin_bot_feature, admin_bot_unfeature,
            admin_edit_bot, admin_disable_bot, admin_enable_bot,
            admin_featured_bots, admin_bot_analytics, admin_bot_analytics_detail,
            admin_add_bot_start,
            admin_users, admin_view_users, admin_user_detail,
            admin_user_make_admin, admin_user_remove_admin,
            admin_make_admin, admin_remove_admin,
            admin_user_activity, admin_search_user,
            admin_user_make_dev, admin_user_add_balance, admin_user_orders,
            admin_finance, admin_finance_overview,
            admin_pending_payments, admin_verified_payments, admin_rejected_payments,
            admin_developer_payouts,
            # JOB MANAGEMENT (keep for admin approval)
            admin_job_management,
            admin_jobs_pending_list,
            admin_jobs_approved,
            admin_jobs_active,
            admin_jobs_stats,
            admin_jobs_search,
            admin_review_job,
            admin_approve_job,
            admin_reject_job,
        )

        admin_callbacks = [
            ('admin_stats', admin_stats),
            ('admin_stats_detailed', admin_stats_detailed),
            ('admin_orders', admin_orders),
            ('admin_view_orders', admin_view_orders),
            ('admin_order_detail_', admin_order_detail),
            ('admin_approve_payment_', admin_approve_payment),
            ('admin_reject_payment_', admin_reject_payment),
            ('admin_assign_developer_', admin_assign_developer),
            ('admin_assign_dev_', admin_assign_dev_confirm),
            ('admin_complete_order_', admin_complete_order),
            ('admin_orders_pending', admin_orders_pending),
            ('admin_orders_completed', admin_orders_completed),
            ('admin_orders_cancelled', admin_orders_cancelled),
            ('admin_orders_assigned', admin_orders_assigned),
            ('admin_search_order', admin_search_order),
            ('admin_developers', admin_developers),
            ('admin_view_developers', admin_view_developers),
            ('admin_developer_detail_', admin_developer_detail),
            ('admin_active_developers', admin_active_developers),
            ('admin_inactive_developers', admin_inactive_developers),
            ('admin_remove_developer', admin_remove_developer),
            ('admin_developer_stats', admin_developer_stats),
            ('admin_dev_busy_', admin_dev_busy),
            ('admin_dev_deactivate_', admin_dev_deactivate),
            ('admin_dev_activate_', admin_dev_activate),
            ('admin_dev_edit_', admin_dev_edit),
            ('admin_dev_earnings_', admin_dev_earnings),
            ('admin_dev_payout_', admin_dev_payout),
            ('admin_remove_dev_', admin_remove_dev),
            ('admin_developer_requests', admin_developer_requests),
            ('admin_dev_requests_pending', admin_dev_requests_pending),
            ('admin_dev_review_', admin_dev_review_request),
            ('admin_dev_approve_', admin_dev_approve_request),
            ('admin_dev_reject_', admin_dev_reject_request),
            ('admin_dev_requests_approved', admin_dev_requests_approved),
            ('admin_dev_requests_rejected', admin_dev_requests_rejected),
            ('admin_dev_requests_stats', admin_dev_requests_stats),
            ('admin_dev_notes_', admin_dev_notes),
            ('admin_dev_contact_', admin_dev_contact),
            ('admin_custom_requests', admin_custom_requests),
            ('admin_custom_requests_pending', admin_custom_requests_pending),
            ('admin_custom_request_detail_', admin_custom_request_detail),
            ('admin_custom_approve_', admin_custom_approve),
            ('admin_custom_requests_review', admin_custom_requests_review),
            ('admin_custom_requests_approved', admin_custom_requests_approved),
            ('admin_custom_requests_rejected', admin_custom_requests_rejected),
            ('admin_custom_requests_stats', admin_custom_requests_stats),
            ('admin_custom_review_', admin_custom_review),
            ('admin_custom_reject_', admin_custom_reject),
            ('admin_custom_assign_', admin_custom_assign),
            ('admin_custom_notes_', admin_custom_notes),
            ('admin_custom_contact_', admin_custom_contact),
            ('admin_broadcast', admin_broadcast_start),
            ('admin_broadcast_confirm', admin_broadcast_confirm),
            ('admin_broadcast_cancel', admin_broadcast_cancel),
            ('admin_bots', admin_bots),
            ('admin_view_bots', admin_view_bots),
            ('admin_bot_detail_', admin_bot_detail),
            ('admin_bot_disable_', admin_bot_disable),
            ('admin_bot_enable_', admin_bot_enable),
            ('admin_bot_feature_', admin_bot_feature),
            ('admin_bot_unfeature_', admin_bot_unfeature),
            ('admin_edit_bot', admin_edit_bot),
            ('admin_disable_bot', admin_disable_bot),
            ('admin_enable_bot', admin_enable_bot),
            ('admin_featured_bots', admin_featured_bots),
            ('admin_bot_analytics', admin_bot_analytics),
            ('admin_bot_analytics_', admin_bot_analytics_detail),
            ('admin_add_bot', admin_add_bot_start),
            ('admin_users', admin_users),
            ('admin_view_users', admin_view_users),
            ('admin_user_detail_', admin_user_detail),
            ('admin_user_make_admin_', admin_user_make_admin),
            ('admin_user_remove_admin_', admin_user_remove_admin),
            ('admin_make_admin', admin_make_admin),
            ('admin_remove_admin', admin_remove_admin),
            ('admin_user_activity', admin_user_activity),
            ('admin_search_user', admin_search_user),
            ('admin_user_make_dev_', admin_user_make_dev),
            ('admin_user_add_balance_', admin_user_add_balance),
            ('admin_user_orders_', admin_user_orders),
            ('admin_finance', admin_finance),
            ('admin_finance_overview', admin_finance_overview),
            ('admin_pending_payments', admin_pending_payments),
            ('admin_verified_payments', admin_verified_payments),
            ('admin_rejected_payments', admin_rejected_payments),
            ('admin_developer_payouts', admin_developer_payouts),
            # JOB MANAGEMENT
            ('admin_job_management', admin_job_management),
            ('admin_jobs_pending_list', admin_jobs_pending_list),
            ('admin_jobs_approved', admin_jobs_approved),
            ('admin_jobs_active', admin_jobs_active),
            ('admin_jobs_stats', admin_jobs_stats),
            ('admin_jobs_search', admin_jobs_search),
            ('admin_review_job_', admin_review_job),
            ('admin_approve_job_', admin_approve_job),
            ('admin_reject_job_', admin_reject_job),
        ]

        for pattern, handler in admin_callbacks:
            if pattern.endswith('_'):
                application.add_handler(CallbackQueryHandler(handler, pattern=f"^{pattern}"))
            else:
                application.add_handler(CallbackQueryHandler(handler, pattern=f"^{pattern}$"))

        print("✅ ALL admin callbacks registered successfully!")

        # ========== TEST COMMANDS ==========
        async def test_jobs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
            keyboard = [
                [InlineKeyboardButton("📝 Post a Job", callback_data="post_job")],
                [InlineKeyboardButton("🔍 Browse Jobs", callback_data="job_board")],
                [InlineKeyboardButton("👀 My Jobs", callback_data="my_jobs")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
            ]
            await update.message.reply_text(
                "🧪 Job Marketplace Test\n\nTest the job marketplace features:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        application.add_handler(CommandHandler("testjobs", test_jobs_command))

        # ========== FALLBACK HANDLER – MUST BE ABSOLUTELY LAST ==========
        print("DEBUG: Adding fallback handler (generic_callback) – LAST")
        application.add_handler(CallbackQueryHandler(generic_callback))

        async def fallback_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
            if update.message:
                if 'job_flow' in context.user_data or 'custom_software' in context.user_data:
                    return
                await update.message.reply_text(
                    "I didn't understand that. Use /menu to see available options."
                )
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            fallback_message_handler
        ))

        # ========== ERROR HANDLER ==========
        async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
            logger.error(f"Update {update} caused error {context.error}", exc_info=True)
            try:
                error_message = "❌ An error occurred. Please try /menu to return to main menu."
                if update.callback_query:
                    await update.callback_query.answer()
                    await update.callback_query.edit_message_text(
                        error_message,
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
                        ])
                    )
                elif update.message:
                    await update.message.reply_text(
                        error_message,
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
                        ])
                    )
            except Exception as e:
                logger.error(f"Error in error handler: {e}")
        application.add_error_handler(error_handler)

        print("✅ All handlers registered successfully!")
        return application

    except Exception as e:
        print(f"❌ Error creating application: {e}")
        traceback.print_exc()
        return None