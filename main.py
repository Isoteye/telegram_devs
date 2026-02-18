
import logging
import sys
import os
import traceback
import time
from datetime import datetime
from telegram import Update



# Add current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler(f"bot_{datetime.now().strftime('%Y%m%d')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def main():
    """Main function"""
    print("=" * 60)
    print("🚀 Software Marketplace - Professional Edition")
    print("=" * 60)
    print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Import database functions from new location
    from database.db_init import test_database_connection, initialize_database
    
    # Test database connection first
    if not test_database_connection():
        print("⚠️ Database connection test failed. Attempting to reinitialize...")
    
    # Initialize database
    if not initialize_database():
        print("⚠️ Database initialization had issues, but continuing...")
    
    # Import application creation from new location
    from application import create_application
    application = create_application()
    if not application:
        print("❌ Failed to create application. Exiting.")
        return
    
    print("\n✅ Bot is ready and fully configured!")
    print("\n📱 Available Commands:")
    print("   /start - Start the bot and create account")
    print("   /menu - Show main menu with all options")
    print("   /help - Show help information")
    print("   /debug - Check bot status")
    print("   /admin - Admin panel (super admin only)")
    print("   /developer - Developer dashboard (if registered)")
    print("   /verify ORDER_ID - Verify Paystack payment")
    print("   /verify_deposit PAYMENT_REF - Verify custom request deposit")
    print("   /refund ORDER_ID [REASON] - Process manual refund (admin only)")
    print("\n🔄 Custom Request Payment Flow:")
    print("   1. /menu → Request Custom Software")
    print("   2. Fill out request details")
    print("   3. Click 'Pay Deposit'")
    print("   4. Enter email (if not saved)")
    print("   5. Complete Paystack payment")
    print("   6. Verify with /verify_deposit")
    print("\n⏰ Automatic Refund Policy:")
    print("   - Orders unclaimed by developers within 48 hours → Full refund")
    print("   - Custom requests unapproved within 48 hours → Deposit refund")
    print("   - Refunds processed automatically every hour")
    print("\n⚡ Starting Telegram Bot...")
    print("🔄 Starting automatic refund checker...")
    
    # Start the refund checker thread
    try:
        from order_management import start_refund_checker
        start_refund_checker()
        print("✅ Automatic refund checker started successfully")
    except ImportError as e:
        print(f"⚠️ Could not import order_management module: {e}")
        print("⚠️ Automatic refunds will not be available")
    except Exception as e:
        print(f"⚠️ Could not start refund checker: {e}")
        print("⚠️ Automatic refunds will not be available")
    
    print("   Press Ctrl+C to stop")
    print("=" * 60)
    
    try:
        # Start the bot
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
    except KeyboardInterrupt:
        print("\n👋 Bot stopped by user")
        print(f"End Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception as e:
        logger.error(f"❌ Bot crashed: {e}", exc_info=True)
        print(f"❌ Bot crashed: {e}")
        traceback.print_exc()
        print("\n🔄 Attempting to restart in 10 seconds...")
        time.sleep(10)
        main()  # Restart

if __name__ == '__main__':
    main()
