# webhook_server.py – CLEANED, NO JOB CODE
from flask import Flask, request, jsonify
from services.paystack_service import PaystackService
from database.db import create_session
from database.models import Order, OrderStatus, PaymentStatus, Transaction, CustomRequest, RequestStatus
from datetime import datetime
import logging
import json

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

@app.route('/webhook/paystack', methods=['POST'])
def paystack_webhook():
    try:
        payload = request.get_data()
        signature = request.headers.get('X-Paystack-Signature', '')
        paystack = PaystackService()

        if not paystack.validate_webhook(payload, signature):
            return jsonify({"status": "error", "message": "Invalid signature"}), 401

        data = request.json
        event = data.get('event')
        payment_data = data.get('data', {})
        reference = payment_data.get('reference')

        logging.info(f"Paystack webhook: {event}, ref: {reference}")

        if event == 'charge.success':
            amount = payment_data.get('amount', 0) / 100
            db = create_session()
            try:
                # ===== REGULAR ORDER (BOT PURCHASE) =====
                order = db.query(Order).filter(Order.order_id == reference).first()
                if order:
                    order.status = OrderStatus.PENDING_REVIEW
                    order.payment_status = PaymentStatus.VERIFIED
                    order.paid_at = datetime.now()
                    order.payment_metadata = payment_data

                    transaction = db.query(Transaction).filter(
                        Transaction.reference == reference
                    ).first()
                    if transaction:
                        transaction.status = 'successful'
                        transaction.gateway_response = json.dumps(data)
                        transaction.transaction_data = payment_data

                    db.commit()
                    logging.info(f"Order {reference} updated")
                    send_telegram_notification(f"💰 Payment for Order {reference}")
                    return jsonify({"status": "success"}), 200

                # ===== CUSTOM REQUEST DEPOSIT =====
                if reference and reference.startswith('DEP_'):
                    custom_request = db.query(CustomRequest).filter(
                        CustomRequest.payment_reference == reference
                    ).first()
                    if custom_request:
                        custom_request.is_deposit_paid = True
                        custom_request.status = RequestStatus.PENDING_REVIEW
                        custom_request.payment_metadata = payment_data
                        custom_request.deposit_paid_at = datetime.now()

                        transaction = db.query(Transaction).filter(
                            Transaction.reference == reference
                        ).first()
                        if transaction:
                            transaction.status = 'successful'
                            transaction.gateway_response = json.dumps(data)
                            transaction.transaction_data = payment_data

                        db.commit()
                        logging.info(f"Custom deposit {reference} updated")
                        send_telegram_notification(f"💰 Deposit paid for Custom Request {custom_request.request_id}")
                        return jsonify({"status": "success"}), 200

                # No matching record
                logging.warning(f"No match for reference: {reference}")
                return jsonify({"status": "received", "message": "No matching record"}), 200

            except Exception as e:
                logging.error(f"Webhook DB error: {e}", exc_info=True)
                db.rollback()
                return jsonify({"status": "error", "message": str(e)}), 500
            finally:
                db.close()

        # Acknowledge other events
        return jsonify({"status": "received", "event": event}), 200

    except Exception as e:
        logging.error(f"Webhook error: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500


def send_telegram_notification(message):
    """Send admin notification"""
    try:
        from telegram import Bot
        from config import TELEGRAM_TOKEN, SUPER_ADMIN_ID
        if TELEGRAM_TOKEN and SUPER_ADMIN_ID:
            bot = Bot(token=TELEGRAM_TOKEN)
            bot.send_message(chat_id=SUPER_ADMIN_ID, text=message)
    except Exception as e:
        logging.error(f"Failed to send Telegram notification: {e}")


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)