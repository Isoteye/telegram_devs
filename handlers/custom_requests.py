import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from telegram.ext import ConversationHandler
from utils.budget_helpers import validate_budget_amount, calculate_deposit_amount, get_delivery_time_for_tier
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import logging
logger = logging.getLogger(__name__)

REQUEST_SOFTWARE_DESCRIPTION = 1
REQUEST_SOFTWARE_FEATURES = 2
REQUEST_SOFTWARE_BUDGET = 3
REQUEST_SOFTWARE_TIMELINE = 4


async def request_custom_bot_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start custom software request process"""
    try:
        query = update.callback_query
        await query.answer()
        
        # CLEAR all context data
        context.user_data.clear()
        
        text = """⚙️ REQUEST CUSTOM SOFTWARE

Let's create your custom software! I'll ask you a few questions:

1. What type of software do you need? (e.g., Web App, Mobile App, Bot, Desktop Software)
2. What does it need to do? (Description)
3. What specific features do you want?
4. What's your budget range? (You'll enter the exact amount)
5. When do you need it?

Please describe what type of software you need:"""
        
        keyboard = [
            [InlineKeyboardButton("❌ Cancel", callback_data="menu_main")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup)
        
        return REQUEST_SOFTWARE_DESCRIPTION
        
    except Exception as e:
        logger.error(f"Error in request_custom_bot_start: {e}", exc_info=True)
        return ConversationHandler.END

async def handle_bot_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle software description"""
    try:
        if not update.message:
            return REQUEST_SOFTWARE_DESCRIPTION
        
        context.user_data['custom_software'] = {
            'type': update.message.text,
            'description': update.message.text
        }
        
        await update.message.reply_text(
            "✅ Got it! Now, please describe what your software needs to do in detail:\n\n"
            "Be specific about:\n"
            "- Target audience\n"
            "- Main functionality\n"
            "- Problems it should solve\n"
            "- Any special requirements\n\n"
            "Please provide a detailed description:"
        )
        
        return REQUEST_SOFTWARE_FEATURES
        
    except Exception as e:
        logger.error(f"Error in handle_bot_description: {e}", exc_info=True)
        await update.message.reply_text("❌ Error. Please try /menu to start over.")
        return ConversationHandler.END

async def handle_bot_features(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle software features"""
    try:
        if not update.message:
            return REQUEST_SOFTWARE_FEATURES
        
        # Store the detailed description
        if 'description_detail' not in context.user_data.get('custom_software', {}):
            context.user_data['custom_software']['description_detail'] = update.message.text
            context.user_data['custom_software']['description'] = update.message.text[:100] + "..."
        
        await update.message.reply_text(
            "✅ Great! Now, please list the specific features you want:\n\n"
            "Example for different types:\n"
            "Web App:\n- User authentication\n- Database integration\n- Payment processing\n- Admin dashboard\n\n"
            "Mobile App:\n- Push notifications\n- GPS integration\n- Camera access\n- In-app purchases\n\n"
            "Telegram Bot:\n- User registration\n- Database storage\n- Payment integration\n- Admin commands\n\n"
            "Desktop Software:\n- Offline functionality\n- File system access\n- System integration\n- Auto-updates\n\n"
            "Please list one feature per line:"
        )
        
        # Set a flag to know we're expecting features next
        context.user_data['custom_software']['expecting_features'] = True
        
        return REQUEST_SOFTWARE_FEATURES
        
    except Exception as e:
        logger.error(f"Error in handle_bot_features: {e}", exc_info=True)
        await update.message.reply_text("❌ Error. Please try /menu to start over.")
        return ConversationHandler.END

async def handle_software_features_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle actual features input"""
    try:
        if not update.message:
            return REQUEST_SOFTWARE_FEATURES
        
        context.user_data['custom_software']['features'] = update.message.text
        context.user_data['custom_software'].pop('expecting_features', None)
        
        await update.message.reply_text(
            "💰 **Budget Range**\n\n"
            "Please enter your budget amount in USD (e.g., 500):\n\n"
            "Based on your budget, we'll recommend the best option:\n"
            "• **Basic**: $299+ - Simple software with basic features\n"
            "• **Standard**: $799+ - Advanced software with more features\n"
            "• **Premium**: $1499+ - Complex software with custom integrations\n"
            "• **Enterprise**: $2999+ - Large-scale business solutions\n\n"
            "Enter your exact budget amount:"
        )
        
        return REQUEST_SOFTWARE_BUDGET
        
    except Exception as e:
        logger.error(f"Error in handle_software_features_input: {e}", exc_info=True)
        await update.message.reply_text("❌ Error. Please try /menu to start over.")
        return ConversationHandler.END

async def handle_budget_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle custom budget amount input with enhanced validation and currency info"""
    try:
        if not update.message:
            return REQUEST_SOFTWARE_BUDGET
        
        budget_text = update.message.text.strip()
        
        # Try different parsing methods
        try:
            # Remove currency symbols and commas
            cleaned = budget_text.replace('$', '').replace(',', '').replace('USD', '').strip()
            
            # Try to parse as float
            budget_amount = float(cleaned)
            
            # Validate budget using helper
            from utils.budget_helpers import validate_budget_amount, calculate_deposit_amount, get_delivery_time_for_tier
            validation = validate_budget_amount(budget_amount)
            
            if not validation['valid']:
                await update.message.reply_text(validation['message'])
                return REQUEST_SOFTWARE_BUDGET
            
            # Calculate deposit in USD (defined here to be available in exception handler)
            deposit_usd = budget_amount * 0.2
            
            # Get user currency info
            from database.db import create_session
            from database.models import User
            from services.currency_service import currency_service
            
            db = create_session()
            try:
                user = db.query(User).filter(
                    User.telegram_id == str(update.effective_user.id)
                ).first()
                
                if user and user.currency:
                    user_currency = user.currency
                else:
                    user_currency = "USD"
                
                # Convert to user's currency
                total_local = currency_service.convert_usd_to_currency(budget_amount, user_currency)
                total_symbol = currency_service.get_currency_symbol(user_currency)
                deposit_local = currency_service.convert_usd_to_currency(deposit_usd, user_currency)
                
            except Exception as e:
                logger.error(f"Error getting currency info: {e}")
                user_currency = "USD"
                total_symbol = "$"
                total_local = budget_amount
                deposit_local = deposit_usd
            finally:
                db.close()
            
            # Get tier and delivery time
            tier = validation['tier']
            delivery_time = get_delivery_time_for_tier(tier)
            
            # Calculate deposit
            deposit_info = calculate_deposit_amount(budget_amount)
            
            # Store in context
            context.user_data['custom_software'].update({
                'budget_amount': budget_amount,
                'budget_tier': tier,
                'price': budget_amount,
                'delivery_time': delivery_time,
                'deposit_info': deposit_info,
                'tier_description': validation.get('tier_description', ''),
                'examples': validation.get('examples', []),
                'user_currency': user_currency,
                'total_local': total_local,
                'total_symbol': total_symbol,
                'deposit_local': deposit_local,
                'deposit_usd': deposit_usd
            })
            
            # Show confirmation and timeline options with currency info
            text = f"""✅ **Budget Confirmed!**

💰 **Your Budget:** ${budget_amount:.2f} USD
💱 **In your currency ({user_currency}):** {total_symbol}{total_local:.2f}

📊 **Recommended Tier:** {tier.title()}
📋 **Description:** {validation.get('tier_description', '')}
🚀 **Estimated Delivery:** {delivery_time}

💳 **Payment Breakdown:**
Total: ${budget_amount:.2f} USD
Deposit (20%): ${deposit_info['deposit_amount']:.2f} USD
Remaining: ${deposit_info['remaining_amount']:.2f} USD

💱 **In your currency ({user_currency}):**
Total: {total_symbol}{total_local:.2f}
Deposit: {total_symbol}{deposit_local:.2f}
Remaining: {total_symbol}{total_local - deposit_local:.2f}

📅 **When do you need this completed?**

Select your preferred timeline:"""
            
            keyboard = [
                [
                    InlineKeyboardButton("🚀 ASAP (Priority)", callback_data="timeline_asap"),
                    InlineKeyboardButton("📅 1-2 Weeks", callback_data="timeline_2weeks")
                ],
                [
                    InlineKeyboardButton("🗓️ 3-4 Weeks", callback_data="timeline_month"),
                    InlineKeyboardButton("📆 1-2 Months", callback_data="timeline_2months")
                ],
                [InlineKeyboardButton("🔙 Change Budget", callback_data="back_to_budget")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(text, reply_markup=reply_markup)
            
            return REQUEST_SOFTWARE_TIMELINE
            
        except ValueError:
            # Show helpful error message
            await update.message.reply_text(
                "❌ **Invalid amount format.**\n\n"
                "Please enter a valid number (e.g.):\n"
                "• 500\n"
                "• $500\n"
                "• 500.00\n"
                "• $500 USD\n\n"
                "Minimum budget: $100 USD\n"
                "Enter your budget amount:"
            )
            return REQUEST_SOFTWARE_BUDGET
        
    except Exception as e:
        logger.error(f"Error in handle_budget_input: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ Error processing budget. Please try again with a valid amount (e.g., 500):"
        )
        return REQUEST_SOFTWARE_BUDGET
    

async def handle_timeline_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle timeline selection and show payment option with currency conversion"""
    try:
        query = update.callback_query
        await query.answer()
        
        timeline = query.data.replace('timeline_', '')
        
        # Map timeline to readable text
        timeline_map = {
            'asap': 'ASAP (Priority) - 1-3 days',
            'week': '1 Week',
            '2weeks': '2 Weeks',
            'month': '1 Month',
            '2months': '2 Months'
        }
        
        custom_data = context.user_data['custom_software']
        timeline_text = timeline_map.get(timeline, timeline.replace('_', ' ').title())
        custom_data['timeline'] = timeline_text
        
        # Get user for currency info
        from database.db import create_session
        from database.models import User
        from services.currency_service import currency_service
        
        db = create_session()
        try:
            user = db.query(User).filter(
                User.telegram_id == str(query.from_user.id)
            ).first()
            
            if user and user.currency:
                user_currency = user.currency
            else:
                user_currency = "USD"
            
            # Get amounts
            budget_amount = custom_data.get('budget_amount', 0.0)
            deposit_usd = budget_amount * 0.2
            remaining_usd = budget_amount - deposit_usd
            
            # Convert amounts to user's currency
            total_local = currency_service.convert_usd_to_currency(budget_amount, user_currency)
            total_symbol = currency_service.get_currency_symbol(user_currency)
            deposit_local = currency_service.convert_usd_to_currency(deposit_usd, user_currency)
            remaining_local = currency_service.convert_usd_to_currency(remaining_usd, user_currency)
            
        except Exception as e:
            logger.error(f"Error getting currency info: {e}")
            user_currency = "USD"
            total_symbol = "$"
            budget_amount = custom_data.get('budget_amount', 0.0)
            total_local = budget_amount
            deposit_usd = budget_amount * 0.2
            deposit_local = deposit_usd
            remaining_usd = budget_amount - deposit_usd
            remaining_local = remaining_usd
        finally:
            db.close()
        
        # Show examples if available
        examples_text = ""
        if custom_data.get('examples'):
            examples = custom_data['examples']
            examples_text = "\n\n📋 **Similar projects in this range:**\n"
            for example in examples[:3]:  # Show max 3 examples
                examples_text += f"• {example}\n"
        
        text = f"""🎉 **Custom Software Request Ready!**

📋 **Request Summary:**
🚀 **Type:** {custom_data.get('type', 'Software')}
💰 **Your Budget:** ${budget_amount:.2f} USD
📊 **Tier:** {custom_data.get('budget_tier', 'Custom').title()}
⏱️ **Delivery Estimate:** {custom_data.get('delivery_time', '2-4 weeks')}
📅 **Your Timeline:** {timeline_text}

💳 **Payment Breakdown (USD):**
Total Project: ${budget_amount:.2f}
Required Deposit (20%): ${deposit_usd:.2f}
Balance Due Upon Completion: ${remaining_usd:.2f}

💱 **Currency Conversion ({user_currency}):**
Total: {total_symbol}{total_local:.2f}
Deposit: {total_symbol}{deposit_local:.2f}
Balance: {total_symbol}{remaining_local:.2f}
{examples_text}

✅ **Why pay a deposit?**
• Secures your spot in our development queue
• Shows commitment to the project
• Gets priority in developer assignment
• Deposit is applied to final payment

📝 **What happens next?**
1. Pay 20% deposit to submit request
2. Admin reviews your requirements (24-48 hours)
3. Once approved, developers can claim your project
4. Development begins when claimed
5. Pay remaining 80% upon completion and delivery

⚠️ **Note:** You'll be paying in {user_currency}

Click **"Pay Deposit"** to proceed:"""
        
        keyboard = [
            [InlineKeyboardButton(f"💰 Pay Deposit ({total_symbol}{deposit_local:.2f} {user_currency})", callback_data="submit_with_deposit")],
            [
                InlineKeyboardButton("🔙 Change Timeline", callback_data="back_to_budget"),
                InlineKeyboardButton("❌ Cancel", callback_data="menu_main")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup)
        
        # Store the request data in context for later use
        context.user_data['pending_custom_request'] = custom_data
        
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Error in handle_timeline_selection: {e}", exc_info=True)
        await query.edit_message_text("❌ Error. Please try /menu to start over.")
        return ConversationHandler.END

async def handle_submit_with_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle deposit payment submission"""
    try:
        query = update.callback_query
        await query.answer()
        
        custom_data = context.user_data.get('pending_custom_request')
        if not custom_data:
            await query.edit_message_text("❌ Request data not found. Please start over.")
            return
        
        # Get the customer's budget amount
        budget_amount = custom_data.get('budget_amount', 0.0)
        deposit_amount = budget_amount * 0.2
        
        # Save custom request to database (without deposit paid yet)
        from database.db import create_session
        from database.models import User, CustomRequest, RequestStatus
        from utils.helpers import generate_request_id
        
        db = create_session()
        try:
            # Get user
            user = db.query(User).filter(User.telegram_id == str(update.effective_user.id)).first()
            if not user:
                await query.edit_message_text("❌ User not found. Please use /start first.")
                return
            
            # Create custom request with customer's budget
            request_id = generate_request_id()
            
            custom_request = CustomRequest(
                request_id=request_id,
                user_id=user.id,
                title=f"Custom {custom_data.get('type', 'Software')}",
                description=custom_data.get('description_detail', custom_data.get('description', 'No description')),
                features=custom_data.get('features', 'No features specified'),
                budget_tier=custom_data.get('budget_tier', 'custom'),
                estimated_price=budget_amount,  # Use customer's budget amount
                deposit_paid=0.0,
                is_deposit_paid=False,
                delivery_time=custom_data.get('delivery_time', '2-3 weeks'),
                timeline=custom_data.get('timeline', 'Within 1 month'),
                status=RequestStatus.NEW
            )
            
            db.add(custom_request)
            db.commit()
            
            # Clear pending data
            context.user_data.pop('pending_custom_request', None)
            context.user_data.pop('custom_software', None)
            
            # Show payment option
            text = f"""📋 Custom Request Created!

Request ID: {request_id}
Title: {custom_request.title}
**Your Budget: ${budget_amount:.2f}**
**Required Deposit (20%): ${deposit_amount:.2f}**

To proceed, please pay the 20% deposit.

Click the button below to pay:"""
            
            keyboard = [
                [InlineKeyboardButton("💰 Pay Deposit", callback_data=f"pay_deposit_{request_id}")],
                [InlineKeyboardButton("📋 My Requests", callback_data="my_requests")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup)
            
        except Exception as e:
            logger.error(f"Error saving custom request: {e}", exc_info=True)
            db.rollback()
            await query.edit_message_text("❌ Error creating request. Please try again.")
        finally:
            db.close()
        
    except Exception as e:
        logger.error(f"Error in handle_submit_with_deposit: {e}", exc_info=True)
        await query.edit_message_text("❌ Error. Please try /menu to start over.")

async def handle_back_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle back button in conversation"""
    try:
        query = update.callback_query
        await query.answer()
        
        action = query.data
        
        if action == "back_to_description":
            # Go back to description
            text = "Please describe what you want your software to do:"
            await query.edit_message_text(text)
            return REQUEST_SOFTWARE_DESCRIPTION
            
        elif action == "back_to_budget":
            # Go back to budget input
            text = "💰 **Budget Range**\n\nPlease enter your budget amount in USD (e.g., 500):"
            await query.edit_message_text(text)
            return REQUEST_SOFTWARE_BUDGET
            
    except Exception as e:
        logger.error(f"Error in handle_back_button: {e}", exc_info=True)
        return ConversationHandler.END
    

async def cancel_custom_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel custom request conversation"""
    try:
        # Clear context
        context.user_data.pop('custom_software', None)
        
        if update.callback_query:
            query = update.callback_query
            await query.answer()
            await query.edit_message_text(
                "❌ Custom software request cancelled.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
                ])
            )
        elif update.message:
            await update.message.reply_text(
                "❌ Custom software request cancelled.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
                ])
            )
        
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Error in cancel_custom_request: {e}", exc_info=True)
        return ConversationHandler.END