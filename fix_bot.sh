#!/bin/bash
# fix_bot.sh

echo "🔄 Fixing bot marketplace..."

# Stop any running bot
pkill -f "python main.py" 2>/dev/null

# Remove old database
rm -f bot_marketplace.db

# Remove old logs
rm -f bot_*.log

echo "✅ Cleanup complete"
echo "🔄 Starting bot..."

python main.py