#!/bin/bash
echo "=========================================="
echo " Bot Marketplace - Complete Installation"
echo "=========================================="

# Clean up old files
echo "  Cleaning old files..."
rm -f bot_marketplace.db
rm -f *.log
rm -f *.pyc
rm -rf __pycache__

# Create virtual environment if not exists
if [ ! -d "venv" ]; then
    echo " Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "⚡ Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo " Installing dependencies..."
pip install --upgrade pip
pip install python-telegram-bot sqlalchemy python-dotenv requests

# Create directory structure
echo "Creating directories..."
mkdir -p database handlers services utils

# Create __init__.py files
touch database/__init__.py
touch handlers/__init__.py
touch services/__init__.py
touch utils/__init__.py

# Create the fixed files from above
echo "Creating config.py..."
cat > config.py << 'EOF'
# config.py
import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "YOUR_BOT_TOKEN_HERE")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./bot_marketplace.db")
SUPER_ADMIN_ID = int(os.getenv("SUPER_ADMIN_ID", "1273357133"))

PAYMENT_METHODS = {
    "paystack": {
        "name": "💳 Paystack",
        "instructions": "Pay via Paystack",
        "is_active": True
    },
    "bank_transfer": {
        "account": "0123456789",
        "name": "Bot Marketplace",
        "instructions": "Bank transfer",
        "is_active": True
    }
}
EOF

echo "📝 Creating .env file..."
cat > .env << 'EOF'
TELEGRAM_TOKEN=YOUR_BOT_TOKEN_HERE
SUPER_ADMIN_ID=1273357133
DATABASE_URL=sqlite:///./bot_marketplace.db
EOF

echo "📝 Creating database models..."
cat > database/models.py << 'EOF'
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, Boolean, ForeignKey, Enum, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from database.db import Base

class OrderStatus(str, enum.Enum):
    PENDING_PAYMENT = "pending_payment"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    COMPLETED = "completed"

class PaymentMethod(str, enum.Enum):
    PAYSTACK = "paystack"
    BANK_TRANSFER = "bank_transfer"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, unique=True, index=True)
    username = Column(String(100), nullable=True)
    first_name = Column(String(100))
    last_name = Column(String(100), nullable=True)
    is_admin = Column(Boolean, default=False)
    is_developer = Column(Boolean, default=False)
    balance = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    orders = relationship("Order", back_populates="user")

class Bot(Base):
    __tablename__ = "bots"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    features = Column(Text)
    price = Column(Float, nullable=False)
    category = Column(String(100))
    delivery_time = Column(String(50))
    is_available = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    orders = relationship("Order", back_populates="bot")

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(String(50), unique=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    bot_id = Column(Integer, ForeignKey("bots.id"), nullable=True)
    status = Column(Enum(OrderStatus), default=OrderStatus.PENDING_PAYMENT)
    amount = Column(Float, nullable=False)
    payment_method = Column(Enum(PaymentMethod), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    user = relationship("User", back_populates="orders")
    bot = relationship("Bot", back_populates="orders")
EOF

echo "📝 Creating database initialization..."
cat > database/db.py << 'EOF'
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.ext.declarative import declarative_base
from config import DATABASE_URL
import logging

logger = logging.getLogger(__name__)

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))
Base = declarative_base()

def init_db():
    """Initialize database"""
    try:
        from database.models import User, Bot, Order
        
        Base.metadata.create_all(bind=engine)
        
        from config import SUPER_ADMIN_ID
        session = SessionLocal()
        
        # Create admin user
        admin = session.query(User).filter(User.telegram_id == SUPER_ADMIN_ID).first()
        if not admin:
            admin = User(
                telegram_id=SUPER_ADMIN_ID,
                username="admin",
                first_name="Admin",
                is_admin=True
            )
            session.add(admin)
        
        # Create sample bots
        if session.query(Bot).count() == 0:
            bots = [
                Bot(
                    name="Customer Support Bot",
                    description="Automated customer support",
                    features="FAQ, Tickets, Live Chat",
                    price=199.99,
                    category="Service",
                    delivery_time="3-5 days"
                ),
                Bot(
                    name="E-commerce Bot",
                    description="Online store bot",
                    features="Products, Cart, Payments",
                    price=299.99,
                    category="E-commerce",
                    delivery_time="5-7 days"
                )
            ]
            session.add_all(bots)
        
        session.commit()
        session.close()
        print("✅ Database initialized successfully")
        return True
    except Exception as e:
        print(f" Database error: {e}")
        return False

def create_session():
    return SessionLocal()
EOF

echo "Creating simple main.py..."
cat > main.py << 'EOF'
#!/usr/bin/env python3
"""
Bot Marketplace - Simple Working Version
"""
import logging
import os
import sys
from datetime import datetime

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(f"👋 Welcome {user.first_name}!\nUse /menu to start.")

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🛒 Buy Bot", callback_data="buy")],
        [InlineKeyboardButton("📦 Orders", callback_data="orders")],
        [InlineKeyboardButton("📞 Support", callback_data="support")]
    ]
    await update.message.reply_text("Main Menu:", reply_markup=InlineKeyboardMarkup(keyboard))

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "buy":
        try:
            from database.db import create_session
            from database.models import Bot
            
            db = create_session()
            bots = db.query(Bot).filter(Bot.is_available == True).all()
            db.close()
            
            if bots:
                text = " Available Bots:\n\n"
                for bot in bots[:3]:
                    text += f"✨ {bot.name}\n💰 ${bot.price:.2f}\n\n"
            else:
                text = "No bots available yet."
            
            await query.edit_message_text(text)
        except Exception as e:
            await query.edit_message_text("❌ Error loading bots")
    else:
        await query.edit_message_text(f"✨ {query.data.replace('_', ' ').title()} feature")

def main():
    from config import TELEGRAM_TOKEN
    from database.db import init_db
    
    print("Initializing...")
    init_db()
    
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CallbackQueryHandler(callback_handler))
    
    print("✅ Bot ready!")
    app.run_polling()

if __name__ == "__main__":
    main()
EOF

# Make scripts executable
chmod +x INSTALL_AND_RUN.sh

echo ""
echo "=========================================="
echo "INSTALLATION COMPLETE!"
echo "=========================================="
echo ""
echo " NEXT STEPS:"
echo "1. Edit .env file and add your bot token"
echo "   nano .env  # or any text editor"
echo ""
echo "2. Run the bot:"
echo "   python main.py"
echo ""
echo "3. If you have issues, delete and recreate:"
echo "   rm -f bot_marketplace.db"
echo "   python main.py"
echo ""
echo "✨ Your bot should now work perfectly!"
