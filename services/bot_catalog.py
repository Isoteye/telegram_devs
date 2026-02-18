from database.models import Bot
from typing import List, Optional, Dict
import logging

logger = logging.getLogger(__name__)

class BotCatalog:
    def __init__(self, db_session):
        self.db = db_session
    
    def get_all_bots(self, category: Optional[str] = None) -> List[Bot]:
        """Get all available bots, optionally filtered by category"""
        try:
            query = self.db.query(Bot).filter(Bot.is_available == True)
            
            if category and category != "all":
                query = query.filter(Bot.category == category)
            
            return query.order_by(Bot.name).all()
        except Exception as e:
            logger.error(f"Error getting all bots: {e}")
            return []
    
    def get_bot_by_id(self, bot_id: int) -> Optional[Bot]:
        """Get a specific bot by ID"""
        try:
            return self.db.query(Bot).filter(Bot.id == bot_id).first()
        except Exception as e:
            logger.error(f"Error getting bot by ID {bot_id}: {e}")
            return None
    
    def get_categories(self) -> Dict[str, int]:
        """Get list of all categories with bot counts"""
        try:
            categories = {}
            bots = self.get_all_bots()
            
            for bot in bots:
                if bot.category not in categories:
                    categories[bot.category] = 0
                categories[bot.category] += 1
            
            return categories
        except Exception as e:
            logger.error(f"Error getting categories: {e}")
            return {}
    
    def format_bot_details(self, bot: Bot) -> str:
        """Format bot details for display"""
        try:
            features = bot.features.split('\n') if bot.features else []
            features_text = '\n'.join([f"• {feature.strip()}" for feature in features if feature.strip()])
            
            return f"""
🤖 *{bot.name}*

{bot.description}

⚙️ *Features:*
{features_text}

💰 *Price:* ${bot.price:.2f}
⏱ *Delivery:* {bot.delivery_time}
🏷️ *Category:* {bot.category.title()}
            """
        except Exception as e:
            logger.error(f"Error formatting bot details: {e}")
            return f"Error loading bot details."
    
    def add_bot(self, name: str, description: str, features: str, price: float, 
                category: str, delivery_time: str) -> Optional[Bot]:
        """Add new bot to catalog"""
        try:
            bot = Bot(
                name=name,
                description=description,
                features=features,
                price=price,
                category=category,
                delivery_time=delivery_time
            )
            self.db.add(bot)
            self.db.commit()
            self.db.refresh(bot)
            logger.info(f"Added new bot: {bot.name}")
            return bot
        except Exception as e:
            logger.error(f"Error adding bot: {e}")
            self.db.rollback()
            return None
    
    def update_bot(self, bot_id: int, **kwargs) -> Optional[Bot]:
        """Update bot details"""
        try:
            bot = self.get_bot_by_id(bot_id)
            if not bot:
                return None
            
            for key, value in kwargs.items():
                if hasattr(bot, key) and value is not None:
                    setattr(bot, key, value)
            
            self.db.commit()
            self.db.refresh(bot)
            logger.info(f"Updated bot {bot_id}")
            return bot
        except Exception as e:
            logger.error(f"Error updating bot {bot_id}: {e}")
            self.db.rollback()
            return None

def initialize_sample_bots(db):
    """Initialize sample bots if database is empty"""
    try:
        if db.query(Bot).count() == 0:
            sample_bots = [
                Bot(
                    name="Auto Responder Pro",
                    description="Automatically respond to messages and comments. Perfect for customer service.",
                    features="Keyword-based responses\nMultiple response templates\nScheduling\nAnalytics",
                    price=49.99,
                    category="business",
                    delivery_time="24 hours"
                ),
                Bot(
                    name="Crypto Price Tracker",
                    description="Monitor cryptocurrency prices and get instant alerts.",
                    features="Real-time price tracking\nCustom alerts\nPortfolio tracking\nMultiple exchanges",
                    price=29.99,
                    category="crypto",
                    delivery_time="12 hours"
                ),
                Bot(
                    name="Community Manager",
                    description="Manage your Telegram group with automated moderation.",
                    features="Auto-moderation\nWelcome/Goodbye messages\nUser analytics\nSpam detection",
                    price=39.99,
                    category="community",
                    delivery_time="48 hours"
                ),
            ]
            
            for bot in sample_bots:
                db.add(bot)
            
            db.commit()
            logger.info("Initialized sample bots")
    except Exception as e:
        logger.error(f"Error initializing sample bots: {e}")
        db.rollback()