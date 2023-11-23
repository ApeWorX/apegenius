import os
import yaml
import datetime
from threading import Lock
from telegram import Update, ParseMode
from telegram.ext import Updater, CommandHandler, CallbackContext
import openai

# Load your OpenAI API key and Telegram token from environment variables or direct string assignment
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')

# Initialize OpenAI client
openai.api_key = OPENAI_API_KEY

# Initialize a lock for thread-safe file writing
file_lock = Lock()

# Load or initialize the admin list and group whitelist
admins = {}
groups = {}
usage_data = {}

def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text('Hello! Ask me anything about ApeWorX!')

knowledge_base = ''
with open('knowledge-base.txt', 'r', encoding="utf-8") as file:
    knowledge_base = file.read()

def load_data():
    global admins, groups, usage_data
    try:
        with open('admins.yml', 'r') as f:
            admins = yaml.safe_load(f) or {}
    except FileNotFoundError:
        admins = {}

    try:
        with open('groups.yml', 'r') as f:
            groups = yaml.safe_load(f) or {}
    except FileNotFoundError:
        groups = {}

    try:
        with open('usage.yml', 'r') as f:
            usage_data = yaml.safe_load(f) or {}
    except FileNotFoundError:
        usage_data = {}

def save_data():
    with file_lock:
        with open('admins.yml', 'w') as f:
            yaml.dump(admins, f)
        with open('groups.yml', 'w') as f:
            yaml.dump(groups, f)
        with open('usage.yml', 'w') as f:
            yaml.dump(usage_data, f)

# Define the command handler to add admins
def add_admin(update: Update, context: CallbackContext) -> None:
    # Only allow the owner to add new admins
    owner_id = '67950696'
    if update.message.from_user.id == int(owner_id):
        new_admin_id = context.args[0] if context.args else ''
        admins[new_admin_id] = True
        save_data()
        update.message.reply_text('Admin added successfully.')
    else:
        update.message.reply_text('You are not authorized to add admins.')

# Define the command handler to add groups to the whitelist
def add_group(update: Update, context: CallbackContext) -> None:
    # Only allow admins to add new groups
    if str(update.message.from_user.id) in admins:
        new_group_id = context.args[0] if context.args else ''
        groups[new_group_id] = {'messages_today': 0, 'last_reset': str(datetime.date.today())}
        save_data()
        update.message.reply_text('Group added to whitelist successfully.')
    else:
        update.message.reply_text('You are not authorized to add groups.')

# Define the message handler
def handle_message(update: Update, context: CallbackContext) -> None:
    group_id = str(update.message.chat_id)
    
    if group_id in groups:
        # Check if the daily limit has been reached
        group_data = groups[group_id]
        if group_data['last_reset'] != str(datetime.date.today()):
            group_data['messages_today'] = 0
            group_data['last_reset'] = str(datetime.date.today())
        if group_data['messages_today'] >= 10:
            update.message.reply_text('GPT limit for this group has been reached (10 msgs a day).')
            return
        
        user_message = update.message.text
        command_to_remove = update.message.text.split()[0]  # This will be either /p or /prompt
        user_message = user_message.replace(command_to_remove, '', 1).strip()

        try:
            response = openai.chat.completions.create(
                model="gpt-4-1106-preview",
                temperature=0,
                messages=[
                    {
                        "role": "system",
                        "content": '''
                        /- You are a bot helping people understand Ape.
                        /- I have prefixed a KNOWLEDGE BASE that help you understand what is Ape.
                        /- The answer must exist within the source files, otherwise don't answer.
                        /- You can use ```language to write code that shows in a pretty way.
                        /- Do not invent anything about ape that is not in source files unless you said you were going creative.
                        /- False certanty about what ape can do is the worse thing you can do, avoid it at all costs.
                        /- ALWAYS Answer the user question using the source files and tell the source of your answer.
                        /- ALWAYS provide a % score of how much of your answer matches the KNOWLEDGE BASE.
                        /- If the task is of creative nature it's ok to go wild and beyond just the sources, but you MUST state that confidence score is -1 in that case.
                        '''
                    },
                    {
                        "role": "user",
                        "content": "---START OF KNOWLEDGE BASE---\n\n" + knowledge_base + "\n\n---END OF KNOWLEDGE BASE---"
                    },
                    {
                        "role": "user",
                        "content": user_message
                    }
                ],
            )

            bot_response = response.choices[0].message.content
            update.message.reply_text(bot_response, parse_mode=ParseMode.MARKDOWN)

            # After getting the response from OpenAI, update the usage
            if not admins.get(str(update.message.from_user.id)):
                groups[group_id]['messages_today'] += 1
            save_data()
        except openai.error.OpenAIError as e:
            # Log the error for debugging purposes
            context.logger.error(f"OpenAIError: {e}")

            # Inform the user that the service is currently unavailable
            update.message.reply_text(f"OpenAIError: {e}")


# Main function to start the bot
def main() -> None:
    load_data()
    updater = Updater(TELEGRAM_TOKEN)

    dispatcher = updater.dispatcher
    dispatcher.add_handler(CommandHandler("prompt", handle_message))
    dispatcher.add_handler(CommandHandler("p", handle_message))
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("add_admin", add_admin))
    dispatcher.add_handler(CommandHandler("add_group", add_group))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()