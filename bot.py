import os
import yaml
import datetime
from threading import Lock
from telegram import Update, ParseMode
from telegram.ext import Updater, CommandHandler, CallbackContext, MessageHandler, Filters
import openai
import requests

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

# Define the preaudit command handler
def preaudit(update: Update, context: CallbackContext) -> None:
    url = context.args[0] if context.args else ''
    if not url:
        update.message.reply_text('Please provide a URL.')
        return

    try:
        response = requests.get(url)
        response.raise_for_status()
        code_content = response.text

        prompt = '''
/- Match the natspec documentation made for each function in the code above with its code, for each function list the differences if they don't match perfectly. Make it a list with function signatures and assessments for parts that do not match. You can NEVER say that code is too long to make a review, you have more context size than the source code to craft your answer so you are allowed to make big analysis.
'''
        messages = [
            {
                "role": "user",
                "content": prompt
            },
            {
                "role": "user",
                "content": code_content
            }
        ]

        openai_response = openai.chat.completions.create(
            model="gpt-4-1106-preview",
            temperature=0,
            messages=messages,
        )

        bot_response = openai_response.choices[0].message.content
        # Split the message into chunks of 4096 characters
        max_length = 4096
        messages = [bot_response[i:i+max_length] for i in range(0, len(bot_response), max_length)]
        for msg in messages:
            update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

    except requests.RequestException as e:
        update.message.reply_text(f"Error fetching data from the URL: {e}")
        

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

        # Prepare the list of messages for OpenAI
        messages = [
            {
                "role": "user",
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
            }
        ]

        # Check if the message is a reply to a previous message
        if update.message.reply_to_message:
            # Include the replied-to message content as an assistant message
            messages.append({
                "role": "assistant",
                "content": update.message.reply_to_message.text
            })

        # Add the user's message
        messages.append({
            "role": "user",
            "content": user_message
        })

        try:
            response = openai.chat.completions.create(
                model="gpt-4-1106-preview",
                temperature=0,
                messages=messages,
            )

            bot_response = response.choices[0].message.content
            # Split the message into chunks of 4096 characters
            max_length = 4096
            messages = [bot_response[i:i+max_length] for i in range(0, len(bot_response), max_length)]
            for msg in messages:
                update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

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
    dispatcher.add_handler(CommandHandler("preaudit", preaudit))
    dispatcher.add_handler(MessageHandler(Filters.text & Filters.regex(r'^y\s'), handle_message))
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()