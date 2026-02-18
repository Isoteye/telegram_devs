from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database.db import create_session
from database.models import User, CustomRequest, RequestStatus
from keyboards.main_menu import get_back_keyboard
import logging

logger = logging.getLogger(__name__)

async def start_custom_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start custom bot request"""
    try:
        query = update.callback_query
        await query.answer()
        
        # Clear any previous data
        context.user_data.clear()
        
        text = """
🧠 *Custom Bot Request*

Let's create your custom bot! Please provide the following details:

1. *Description* - What should your bot do?
2. *Platform* - Where will it run?
3. *Budget* - How much are you willing to spend?
4. *Deadline* - When do you need it?
5. *Notes* - Any additional requirements?

Let's start with a description of what you want your bot to do:
        """
        
        keyboard = [
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel_request")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        return 10  # REQUEST_DESCRIPTION
        
    except Exception as e:
        logger.error(f"Error in start_custom_request: {e}")
        if update.callback_query:
            await update.callback_query.edit_message_text(
                "❌ Error starting request.",
                reply_markup=get_back_keyboard("menu_main")
            )
        return ConversationHandler.END

async def handle_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle bot description"""
    try:
        description = update.message.text
        context.user_data['description'] = description
        
        text = """
*Platform Selection*

Where will your bot run? Select a platform:
        """
        
        keyboard = [
            [InlineKeyboardButton("🤖 Telegram", callback_data="platform_telegram")],
            [InlineKeyboardButton("🌐 Web App", callback_data="platform_web")],
            [InlineKeyboardButton("📱 Mobile App", callback_data="platform_mobile")],
            [InlineKeyboardButton("💬 Discord", callback_data="platform_discord")],
            [InlineKeyboardButton("⚙️ Other Platform", callback_data="platform_other")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel_request")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        return 11  # REQUEST_PLATFORM
        
    except Exception as e:
        logger.error(f"Error in handle_description: {e}")
        await update.message.reply_text(
            "❌ Error saving description. Please try again.",
            reply_markup=get_back_keyboard("menu_main")
        )
        return ConversationHandler.END

async def handle_platform(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle platform selection"""
    try:
        query = update.callback_query
        await query.answer()
        
        platform = query.data.replace('platform_', '')
        context.user_data['platform'] = platform
        
        text = """
*Budget Selection*

What's your budget for this project? Select an option:

💰 *Standard Ranges:*
- $20-50: Simple bots with basic functionality
- $50-100: Medium complexity with custom features
- $100-200: Advanced bots with complex logic
- $200+: Enterprise-grade solutions

🎯 *Custom Budget:*
If your project doesn't fit these ranges, select "Custom Budget" and enter your amount.
        """
        
        keyboard = [
            [InlineKeyboardButton("$20 - $50", callback_data="budget_20_50")],
            [InlineKeyboardButton("$50 - $100", callback_data="budget_50_100")],
            [InlineKeyboardButton("$100 - $200", callback_data="budget_100_200")],
            [InlineKeyboardButton("$200+", callback_data="budget_200_plus")],
            [InlineKeyboardButton("💎 Custom Budget", callback_data="budget_custom")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel_request")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        return 12  # REQUEST_BUDGET
        
    except Exception as e:
        logger.error(f"Error in handle_platform: {e}")
        await query.edit_message_text(
            "❌ Error saving platform.",
            reply_markup=get_back_keyboard("menu_main")
        )
        return ConversationHandler.END

async def handle_budget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle budget selection"""
    try:
        query = update.callback_query
        await query.answer()
        
        budget_data = query.data.replace('budget_', '')
        
        # Check if custom budget was selected
        if budget_data == "custom":
            # Ask for custom budget amount
            context.user_data['awaiting_custom_budget'] = True
            
            await query.edit_message_text(
                "💎 *Custom Budget*\n\n"
                "Please enter your budget amount in USD (e.g., 150, 299.99):\n\n"
                "Enter just the number (no dollar sign needed).",
                parse_mode='Markdown'
            )
            return 12  # Stay in REQUEST_BUDGET state
            
        # Handle predefined budgets
        budget_map = {
            "20_50": "$20 - $50",
            "50_100": "$50 - $100",
            "100_200": "$100 - $200",
            "200_plus": "$200+"
        }
        
        budget_display = budget_map.get(budget_data, "Custom Budget")
        context.user_data['budget'] = budget_display
        
        text = f"""
✅ *Budget:* {budget_display}

*Deadline*

When do you need this bot completed?

Examples:
- ASAP (As Soon As Possible)
- 1 week
- 2 weeks
- 1 month
- Specific date (e.g., "January 15, 2024")

Please enter your deadline:
        """
        
        keyboard = [
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel_request")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        return 13  # REQUEST_DEADLINE
        
    except Exception as e:
        logger.error(f"Error in handle_budget: {e}")
        await query.edit_message_text(
            "❌ Error saving budget.",
            reply_markup=get_back_keyboard("menu_main")
        )
        return ConversationHandler.END

async def handle_deadline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle deadline input"""
    try:
        # Check if this is a custom budget input
        if context.user_data.get('awaiting_custom_budget'):
            custom_amount = update.message.text
            
            # Validate it's a number
            try:
                amount = float(custom_amount)
                if amount < 10:
                    await update.message.reply_text(
                        "❌ Minimum budget is $10. Please enter a higher amount:"
                    )
                    return 12  # Stay in budget state
                
                context.user_data['budget'] = f"${amount:.2f} (Custom)"
                context.user_data.pop('awaiting_custom_budget', None)
                
                # Now ask for deadline
                text = f"""
✅ *Budget:* ${amount:.2f} (Custom)

*Deadline*

When do you need this bot completed?

Examples:
- ASAP (As Soon As Possible)
- 1 week
- 2 weeks
- 1 month
- Specific date (e.g., "January 15, 2024")

Please enter your deadline:
                """
                
                keyboard = [
                    [InlineKeyboardButton("❌ Cancel", callback_data="cancel_request")]
                ]
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    text,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
                
                return 13  # REQUEST_DEADLINE
                
            except ValueError:
                await update.message.reply_text(
                    "❌ Please enter a valid number (e.g., 150 or 299.99). Try again:"
                )
                return 12  # Stay in budget state
        
        # Normal deadline input
        deadline = update.message.text
        context.user_data['deadline'] = deadline
        
        text = f"""
✅ *Deadline:* {deadline}

*Additional Notes* (Optional)

Do you have any additional requirements, preferences, or notes?

Examples:
- Specific features you want
- Integration requirements
- Design preferences
- Technical specifications

If you don't have any notes, click "Skip Notes".
        """
        
        keyboard = [
            [InlineKeyboardButton("✅ Skip Notes", callback_data="skip_notes")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel_request")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        return 14  # REQUEST_NOTES
        
    except Exception as e:
        logger.error(f"Error in handle_deadline: {e}")
        await update.message.reply_text(
            "❌ Error saving deadline.",
            reply_markup=get_back_keyboard("menu_main")
        )
        return ConversationHandler.END

async def handle_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle notes input or skip"""
    try:
        notes = ""
        
        if update.callback_query and update.callback_query.data == "skip_notes":
            query = update.callback_query
            await query.answer()
            notes = "No additional notes provided."
        elif update.message:
            notes = update.message.text
        
        context.user_data['notes'] = notes
        
        # Create the custom request
        db = create_session()
        try:
            telegram_id = update.effective_user.id
            
            # Get user
            user = db.query(User).filter(User.telegram_id == telegram_id).first()
            if not user:
                if update.callback_query:
                    await update.callback_query.edit_message_text(
                        "❌ User not found. Please use /start first.",
                        reply_markup=get_back_keyboard("menu_main")
                    )
                else:
                    await update.message.reply_text(
                        "❌ User not found. Please use /start first.",
                        reply_markup=get_back_keyboard("menu_main")
                    )
                return ConversationHandler.END
            
            # Create custom request
            custom_request = CustomRequest(
                user_id=user.id,
                description=context.user_data.get('description', ''),
                platform=context.user_data.get('platform', ''),
                budget_range=context.user_data.get('budget', ''),
                deadline=context.user_data.get('deadline', ''),
                extra_notes=notes,
                status=RequestStatus.NEW
            )
            
            db.add(custom_request)
            db.commit()
            
            # Clear context data
            context.user_data.clear()
            
            # Show success message
            success_text = f"""
✅ *Custom Request Submitted!*

Thank you for your request! Here's a summary:

*Description:*
{context.user_data.get('description', 'N/A')[:200]}...

*Platform:* {context.user_data.get('platform', 'N/A').title()}
*Budget:* {context.user_data.get('budget', 'N/A')}
*Deadline:* {context.user_data.get('deadline', 'N/A')}

*Request ID:* `CR{custom_request.id:06d}`

Our team will review your request within 24 hours and get back to you with a quote.

You'll be notified when we have updates about your request.
            """
            
            from keyboards.main_menu import get_main_menu_keyboard
            
            if update.callback_query:
                await update.callback_query.edit_message_text(
                    success_text,
                    parse_mode='Markdown',
                    reply_markup=get_main_menu_keyboard(telegram_id)
                )
            else:
                await update.message.reply_text(
                    success_text,
                    parse_mode='Markdown',
                    reply_markup=get_main_menu_keyboard(telegram_id)
                )
            
            logger.info(f"✅ Custom request created: ID {custom_request.id} for user {user.id}")
            
        except Exception as e:
            logger.error(f"Error creating custom request: {e}", exc_info=True)
            if update.callback_query:
                await update.callback_query.edit_message_text(
                    "❌ Error submitting request. Please try again.",
                    reply_markup=get_back_keyboard("menu_main")
                )
            else:
                await update.message.reply_text(
                    "❌ Error submitting request. Please try again.",
                    reply_markup=get_back_keyboard("menu_main")
                )
        finally:
            db.close()
        
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Error in handle_notes: {e}")
        if update.callback_query:
            await update.callback_query.edit_message_text(
                "❌ Error saving notes.",
                reply_markup=get_back_keyboard("menu_main")
            )
        else:
            await update.message.reply_text(
                "❌ Error saving notes.",
                reply_markup=get_back_keyboard("menu_main")
            )
        return ConversationHandler.END

async def cancel_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel custom request"""
    try:
        context.user_data.clear()
        
        from keyboards.main_menu import get_main_menu_keyboard
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                "❌ Custom request cancelled.",
                reply_markup=get_main_menu_keyboard(update.effective_user.id)
            )
        else:
            await update.message.reply_text(
                "Custom request cancelled.",
                reply_markup=get_main_menu_keyboard(update.effective_user.id)
            )
        
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Error in cancel_request: {e}")
        return ConversationHandler.END