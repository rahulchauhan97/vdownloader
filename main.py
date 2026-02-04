import os
import json
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# Load bot token and admin IDs from environment variables
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_IDS = list(map(int, os.getenv('ADMIN_IDS', '').split(','))) if os.getenv('ADMIN_IDS') else []
MAX_UPLOAD_MB = int(os.getenv('MAX_UPLOAD_MB', 1900))

# Load state from JSON file
try:
    with open('data/state.json', 'r') as f:
        state = json.load(f)
except FileNotFoundError:
    state = {'admins': ADMIN_IDS, 'bans': [], 'settings': {'max_upload_mb': MAX_UPLOAD_MB}, 'users': [], 'stats': {'downloads': 0, 'bytes': 0}}

# Function to start the bot
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('Hello! I am the vdownloader bot.')

# Command handlers for admin commands
async def admin_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message.from_user.id in state['admins']:
        if context.args:
            user_id = int(context.args[0])
            if user_id not in state['admins']:
                state['admins'].append(user_id)
                await update.message.reply_text(f'User {user_id} added as admin.')
                save_state()  # Save the updated state
            else:
                await update.message.reply_text(f'User {user_id} is already an admin.')
        else:
            await update.message.reply_text('Usage: /admin_add <user_id>')
    else:
        await update.message.reply_text('You are not an admin.')

async def admin_remove(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message.from_user.id in state['admins']:
        if context.args:
            user_id = int(context.args[0])
            if user_id in state['admins']:
                state['admins'].remove(user_id)
                await update.message.reply_text(f'User {user_id} removed from admins.')
                save_state()  # Save the updated state
            else:
                await update.message.reply_text(f'User {user_id} is not an admin.')
        else:
            await update.message.reply_text('Usage: /admin_remove <user_id>')
    else:
        await update.message.reply_text('You are not an admin.')

# Function to save state to JSON file
def save_state() -> None:
    with open('data/state.json', 'w') as f:
        json.dump(state, f)

# Main function to run the bot
def main() -> None:
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('admin_add', admin_add))
    application.add_handler(CommandHandler('admin_remove', admin_remove))
    application.run_polling()

if __name__ == '__main__':
    main()