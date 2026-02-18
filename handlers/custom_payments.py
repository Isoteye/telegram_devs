import sys
import os
import logging
from datetime import datetime
import uuid

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from services.paystack_service import PaystackService
from services.currency_service import currency_service
from handlers.paystack_handler import handle_email_for_paystack

logger = logging.getLogger(__name__)

# ========== CUSTOM REQUEST DEPOSIT – NO JOB CODE ==========

async def handle_pay_deposit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle pay deposit callback – ONLY for custom requests"""
    try:
        query = update.callback_query
        await query.answer()
        logger.info(f"Custom deposit callback: {query.data}")

        # Ensure it's a custom request callback
        if not query.data.startswith('pay_deposit_'):
            await query.edit_message_text("❌ Invalid payment request format.")
            return

        request_id = query.data.replace('pay_deposit_', '')

        # ✅ Accept both CR (new) and REQ (existing) custom request IDs
        if not (request_id.startswith('CR') or request_id.startswith('REQ')):
            await query.edit_message_text(
                f"❌ Unrecognized request format.\n\nID: {request_id}\n\n"
                f"Please contact support."
            )
            return

        logger.info(f"Processing custom request deposit for: {request_id}")

        # Generate UNIQUE Paystack reference
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        random_part = uuid.uuid4().hex[:8].upper()
        unique_ref = f"DEP_{request_id}_{timestamp}_{random_part}"

        from database.db import create_session
        from database.models import CustomRequest, User

        db = create_session()
        try:
            custom_request = db.query(CustomRequest).filter(
                CustomRequest.request_id == request_id
            ).first()

            if not custom_request:
                await query.edit_message_text(f"❌ Custom request '{request_id}' not found.")
                return

            if custom_request.is_deposit_paid:
                await query.edit_message_text(
                    "✅ Deposit already paid. Request is pending admin review."
                )
                return

            user = db.query(User).filter(User.id == custom_request.user_id).first()
            if not user:
                await query.edit_message_text("❌ User not found.")
                return

            # Calculate deposit amounts
            deposit_amount_usd = custom_request.estimated_price * 0.2
            deposit_amount_ghs = currency_service.convert_usd_to_currency(deposit_amount_usd, "GHS")
            user_currency = user.currency if user.currency else "USD"
            local_deposit_amount = currency_service.convert_usd_to_currency(deposit_amount_usd, user_currency)
            local_symbol = currency_service.get_currency_symbol(user_currency)
            ghs_symbol = currency_service.get_currency_symbol("GHS")

            # If user has no email, ask for it
            if not user.email:
                context.user_data['awaiting_email_for_custom_deposit'] = {
                    'request_id': request_id,
                    'deposit_amount_usd': deposit_amount_usd,
                    'deposit_amount_ghs': deposit_amount_ghs,
                    'local_deposit_amount': local_deposit_amount,
                    'local_currency': user_currency,
                    'local_symbol': local_symbol,
                    'request_title': custom_request.title,
                    'unique_ref': unique_ref,
                    'user_id': user.id,
                    'total_price_usd': custom_request.estimated_price
                }
                await query.edit_message_text(
                    f"📧 Deposit Payment for Custom Request\n\n"
                    f"📋 Request: {custom_request.title}\n"
                    f"💰 Total: ${custom_request.estimated_price:.2f} USD\n"
                    f"📊 Deposit (20%): ${deposit_amount_usd:.2f} USD\n\n"
                    f"💱 Conversion:\n"
                    f"Your Currency ({user_currency}): {local_symbol}{local_deposit_amount:.2f}\n"
                    f"🔴 Paystack Ghana (GHS): {ghs_symbol}{deposit_amount_ghs:.2f}\n\n"
                    f"Please enter your email address:"
                )
                return

            # User has email – proceed with payment
            await initialize_custom_deposit_payment(
                query, custom_request, user.email,
                deposit_amount_usd, unique_ref, context,
                local_deposit_amount, user_currency, local_symbol, user
            )

        except Exception as e:
            logger.error(f"Error in handle_pay_deposit_callback: {e}", exc_info=True)
            await query.edit_message_text("❌ Error processing payment request.")
        finally:
            db.close()

    except Exception as e:
        logger.error(f"Outer error: {e}", exc_info=True)


async def initialize_custom_deposit_payment(query, custom_request, email,
                                            deposit_amount_usd, unique_ref, context,
                                            local_deposit_amount, local_currency, local_symbol, user):
    """Initialize Paystack deposit payment (GHS)"""
    from database.db import create_session
    from database.models import Transaction, CustomRequest

    db = create_session()
    try:
        fresh_request = db.query(CustomRequest).filter(
            CustomRequest.id == custom_request.id
        ).first()
        if not fresh_request:
            await query.edit_message_text("❌ Custom request not found.")
            return

        deposit_amount_ghs = currency_service.convert_usd_to_currency(deposit_amount_usd, "GHS")
        paystack = PaystackService()
        success, result = paystack.initialize_transaction(
            email=email,
            amount=deposit_amount_ghs,
            reference=unique_ref,
            currency="GHS",
            callback_url=None
        )

        if not success:
            error_msg = result.get('message', 'Unknown error')
            await query.edit_message_text(f"❌ Payment Failed: {error_msg}")
            return

        payment_data = result.get('data', {})
        authorization_url = payment_data.get('authorization_url')

        # Update custom request
        fresh_request.payment_reference = unique_ref
        fresh_request.deposit_paid = deposit_amount_usd
        fresh_request.payment_metadata = {
            'authorization_url': authorization_url,
            'paystack_response': result,
            'is_deposit': True,
            'usd_amount': deposit_amount_usd,
            'ghs_amount': deposit_amount_ghs,
            'original_currency': local_currency,
            'original_amount': local_deposit_amount
        }

        # Create transaction
        transaction = Transaction(
            transaction_id=unique_ref,
            user_id=fresh_request.user_id,
            amount=deposit_amount_ghs,
            currency="GHS",
            payment_method='paystack',
            status='pending',
            reference=unique_ref,
            transaction_data=result,
            usd_amount=deposit_amount_usd,
            metadata={'request_id': fresh_request.request_id, 'type': 'custom_request_deposit'}
        )
        db.add(transaction)
        db.commit()

        ghs_symbol = currency_service.get_currency_symbol("GHS")
        text = f"""💳 Custom Request Deposit Payment

📋 Request ID: `{fresh_request.request_id}`
📝 Title: {fresh_request.title}
💰 Total: ${fresh_request.estimated_price:.2f} USD
📊 Deposit (20%): ${deposit_amount_usd:.2f} USD

💱 **Paystack Ghana (GHS):** {ghs_symbol}{deposit_amount_ghs:.2f}
Your currency: {local_symbol}{local_deposit_amount:.2f}

📧 Email: {email}
🔖 Reference: `{unique_ref}`

Click below to pay via Paystack.
After payment, use: /verify_deposit {unique_ref}"""

        keyboard = [
            [InlineKeyboardButton("💳 Pay Deposit Now", url=authorization_url)],
            [InlineKeyboardButton("🔄 Verify Payment", callback_data=f"vd_{unique_ref}")],
            [InlineKeyboardButton("📋 My Requests", callback_data="my_requests")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    except Exception as e:
        logger.error(f"Error in initialize_custom_deposit_payment: {e}", exc_info=True)
        db.rollback()
        await query.edit_message_text("❌ Error processing payment. Please try again.")
    finally:
        db.close()

async def handle_custom_deposit_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle email input for custom deposit – FIXED signature"""
    try:
        # 1. Verify this is the right context
        if 'awaiting_email_for_custom_deposit' not in context.user_data:
            # Maybe it's for regular Paystack purchase
            if 'awaiting_email_for_paystack' in context.user_data:
                from handlers.paystack_handler import handle_email_for_paystack
                return await handle_email_for_paystack(update, context)
            return

        # 2. Get and validate email
        if not update.message or not update.message.text:
            return
        email = update.message.text.strip()

        # Simple validation
        if '@' not in email or '.' not in email:
            await update.message.reply_text("❌ Please enter a valid email address (e.g., name@domain.com).")
            return

        # 3. Get stored data and CLEAR IT IMMEDIATELY (prevents double-processing)
        deposit_data = context.user_data.pop('awaiting_email_for_custom_deposit', None)
        if not deposit_data:
            await update.message.reply_text("❌ No pending payment. Please start over.")
            return

        # Extract all required fields
        request_id = deposit_data['request_id']
        deposit_amount_usd = deposit_data['deposit_amount_usd']
        deposit_amount_ghs = deposit_data.get('deposit_amount_ghs', 0)
        local_deposit_amount = deposit_data['local_deposit_amount']
        local_currency = deposit_data['local_currency']
        local_symbol = deposit_data['local_symbol']
        unique_ref = deposit_data['unique_ref']
        total_price_usd = deposit_data.get('total_price_usd', 0)
        request_title = deposit_data.get('request_title', 'Custom Request')

        # Calculate GHS if not provided
        if deposit_amount_ghs == 0:
            from services.currency_service import currency_service
            deposit_amount_ghs = currency_service.convert_usd_to_currency(deposit_amount_usd, "GHS")

        # 4. Process payment in a single DB session
        from database.db import create_session
        from database.models import CustomRequest, User, Transaction
        from services.paystack_service import PaystackService
        from services.currency_service import currency_service

        db = create_session()
        try:
            # Get request and user in one query
            result = db.query(CustomRequest, User).join(
                User, CustomRequest.user_id == User.id
            ).filter(CustomRequest.request_id == request_id).first()

            if not result:
                await update.message.reply_text("❌ Custom request not found.")
                return

            custom_request, user = result

            # Update user's email
            user.email = email

            # Initialize Paystack in GHS
            paystack = PaystackService()
            success, paystack_result = paystack.initialize_transaction(
                email=email,
                amount=deposit_amount_ghs,
                reference=unique_ref,
                currency="GHS",
                callback_url=None
            )

            if not success:
                error_msg = paystack_result.get('message', 'Unknown error')
                db.rollback()
                await update.message.reply_text(
                    f"❌ Payment initialization failed: {error_msg}\n\nPlease try again or contact support."
                )
                return

            payment_data = paystack_result.get('data', {})
            authorization_url = payment_data.get('authorization_url')

            # Update custom request
            custom_request.payment_reference = unique_ref
            custom_request.deposit_paid = deposit_amount_usd
            custom_request.payment_metadata = {
                'authorization_url': authorization_url,
                'paystack_response': paystack_result,
                'is_deposit': True,
                'usd_amount': deposit_amount_usd,
                'ghs_amount': deposit_amount_ghs,
                'original_currency': local_currency,
                'original_amount': local_deposit_amount
            }

            # Create transaction record
            transaction = Transaction(
                transaction_id=unique_ref,
                user_id=user.id,
                amount=deposit_amount_ghs,
                currency="GHS",
                payment_method='paystack',
                status='pending',
                reference=unique_ref,
                transaction_data=paystack_result,
                usd_amount=deposit_amount_usd,
                metadata={'request_id': custom_request.request_id, 'type': 'custom_request_deposit'}
            )
            db.add(transaction)
            db.commit()

            # 5. Send payment link to user
            ghs_symbol = currency_service.get_currency_symbol("GHS")
            text = f"""💳 **Custom Request Deposit Payment**

📋 **Request ID:** `{custom_request.request_id}`
📝 **Title:** {custom_request.title}
💰 **Total Price:** ${total_price_usd:.2f} USD
📊 **Deposit (20%):** ${deposit_amount_usd:.2f} USD

💱 **Currency Information:**
• USD Amount: ${deposit_amount_usd:.2f}
• 🔴 **Paystack Ghana (GHS):** {ghs_symbol}{deposit_amount_ghs:.2f}
• Your currency ({local_currency}): {local_symbol}{local_deposit_amount:.2f}

📧 **Email:** {email}
🔖 **Payment Reference:** `{unique_ref}`

⚠️ **Note:** Paystack Ghana only accepts GHS payments.

Click the button below to pay your deposit via Paystack.

**After payment, use:** `/verify_deposit {unique_ref}`"""

            keyboard = [
                [InlineKeyboardButton("💳 Pay Deposit Now", url=authorization_url)],
                [InlineKeyboardButton("🔄 Verify Payment", callback_data=f"vd_{unique_ref}")],
                [InlineKeyboardButton("📋 My Requests", callback_data="my_requests")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
            ]

            await update.message.reply_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )

        except Exception as e:
            logger.error(f"Error in handle_custom_deposit_email: {e}", exc_info=True)
            db.rollback()
            await update.message.reply_text("❌ An error occurred while processing your payment. Please try again.")
        finally:
            db.close()

    except Exception as e:
        logger.error(f"Outer error in handle_custom_deposit_email: {e}", exc_info=True)
        await update.message.reply_text("❌ Error processing your request. Please try again.")
        


# ========== VERIFY DEPOSIT COMMAND ==========

async def verify_deposit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Verify deposit payment for custom request"""
    try:
        if update.callback_query:
            query = update.callback_query
            await query.answer()
            payment_reference = query.data.replace('vd_', '')
            is_callback = True
        elif update.message and context.args:
            payment_reference = context.args[0]
            is_callback = False
        else:
            if update.message:
                await update.message.reply_text("Usage: /verify_deposit PAYMENT_REFERENCE")
            return

        from order_management import verify_custom_request_deposit
        await verify_custom_request_deposit(update, context, payment_reference, is_callback)

    except Exception as e:
        logger.error(f"Error in verify_deposit_command: {e}", exc_info=True)
        if update.callback_query:
            await update.callback_query.edit_message_text("❌ Error verifying payment.")
        elif update.message:
            await update.message.reply_text("❌ Error verifying payment.")


# ========== SHOW CUSTOM REQUEST DETAILS ==========

async def show_custom_request_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display custom request details – no job code"""
    query = update.callback_query
    await query.answer()

    request_id = query.data.replace('request_', '')
    from database.db import create_session
    from database.models import CustomRequest, RequestStatus, User

    db = create_session()
    try:
        request = db.query(CustomRequest).filter(CustomRequest.request_id == request_id).first()
        if not request:
            await query.edit_message_text("❌ Request not found.")
            return

        user = db.query(User).filter(User.id == request.user_id).first()
        user_currency = user.currency if user and user.currency else "USD"

        deposit_usd = request.estimated_price * 0.2
        deposit_local = currency_service.convert_usd_to_currency(deposit_usd, user_currency)
        local_symbol = currency_service.get_currency_symbol(user_currency)
        deposit_ghs = currency_service.convert_usd_to_currency(deposit_usd, "GHS")
        ghs_symbol = currency_service.get_currency_symbol("GHS")

        status_text = request.status.value.replace('_', ' ').title()
        status_icon = "⏳" if request.status == RequestStatus.NEW else \
                      "💰" if request.status == RequestStatus.PENDING else \
                      "✅" if request.status == RequestStatus.APPROVED else \
                      "❌" if request.status == RequestStatus.REJECTED else "❓"

        text = f"""📋 **Custom Software Request**

**Request ID:** `{request.request_id}`
**Title:** {request.title}
**Status:** {status_icon} {status_text}
**Budget:** {request.budget_tier.title() if request.budget_tier else 'Custom'}

💰 **Financial (USD):**
Total: ${request.estimated_price:.2f}
Deposit (20%): ${deposit_usd:.2f}
Paid: {'✅' if request.is_deposit_paid else '❌'}

💱 **Your currency ({user_currency}):** {local_symbol}{deposit_local:.2f}
🔴 **Paystack Ghana (GHS):** {ghs_symbol}{deposit_ghs:.2f}
"""

        keyboard = []
        if request.status == RequestStatus.NEW and not request.is_deposit_paid:
            keyboard.append([
                InlineKeyboardButton(
                    f"💰 Pay Deposit ({ghs_symbol}{deposit_ghs:.2f} GHS)",
                    callback_data=f"pay_deposit_{request.request_id}"
                )
            ])

        if request.payment_reference and not request.is_deposit_paid:
            keyboard.append([
                InlineKeyboardButton(
                    "🔄 Verify Payment",
                    callback_data=f"vd_{request.payment_reference}"
                )
            ])

        keyboard.extend([
            [InlineKeyboardButton("⬅️ Back to Requests", callback_data="my_requests")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
        ])

        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    except Exception as e:
        logger.error(f"Error in show_custom_request_details: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading request details.")
    finally:
        db.close()