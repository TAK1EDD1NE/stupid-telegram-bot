import csv
import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from telegram import ChatInviteLink
import asyncio
from telegram.error import NetworkError, TelegramError


# ==== LOGGING SETUP ====
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Reduce noise from telegram and httpx libraries
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('telegram').setLevel(logging.WARNING)
logging.getLogger('telegram.ext').setLevel(logging.WARNING)

# ==== CONFIG ====
TELEGRAM_TOKEN = "go-fuck-urself"  # from BotFather
CSV_FILE = "students.csv"
IMAGES_FOLDER = "images"

# Conversation states
WAITING_FOR_PHOTO, WAITING_FOR_NAME = range(2)

# Create images folder if it doesn't exist
os.makedirs(IMAGES_FOLDER, exist_ok=True)

# ==== Load students from CSV into memory ====
def load_students():
    try:
        students = []
        if not os.path.exists(CSV_FILE):
            logger.error(f"CSV file {CSV_FILE} not found!")
            return []
            
        with open(CSV_FILE, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                row["joined"] = row["joined"].lower() == "true"
                students.append(row)
        logger.info(f"Loaded {len(students)} students from CSV")
        return students
    except Exception as e:
        logger.error(f"Error loading students: {e}")
        return []

def save_students(students, filename="students.csv"):
    try:
        with open(filename, mode="w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=["NOM", "PRENOM", "joined"])
            writer.writeheader()
            for s in students:
                writer.writerow({
                    "NOM": s.get("NOM", ""),
                    "PRENOM": s.get("PRENOM", ""),
                    "joined": s.get("joined", False)
                })
        logger.info("Students data saved successfully")
    except Exception as e:
        logger.error(f"Error saving students: {e}")

students = load_students()

# ==== ERROR HANDLER ====
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a telegram message to notify the developer."""
    logger.error(f"Exception while handling an update: {context.error}")
    
    # Try to send a user-friendly message
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ An error occurred. Please try again or contact support."
            )
    except Exception as e:
        logger.error(f"Could not send error message to user: {e}")

# ==== HANDLERS ====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome! Please send me a photo of your student card first."
    )
    return WAITING_FOR_PHOTO

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Check if it's actually a photo
    if not update.message.photo:
        await update.message.reply_text(
            "❌ Please send an image file (photo). Try again."
        )
        return WAITING_FOR_PHOTO
    
    user_id = update.effective_user.id
    
    try:
        # Get the largest photo (best quality)
        photo = update.message.photo[-1]
        
        # Download the photo
        photo_file = await context.bot.get_file(photo.file_id)
        
        # Save with user ID as filename
        image_path = os.path.join(IMAGES_FOLDER, f"{user_id}.jpg")
        await photo_file.download_to_drive(image_path)

        logger.info(f"Photo saved for user {user_id}")
        
        await update.message.reply_text(
            "✅ Student card received! Now please send me your name and family name like this:\nRehail Takie eddine"
        )
        return WAITING_FOR_NAME
        
    except Exception as e:
        await update.message.reply_text(
            "❌ Error saving the image. Please try again."
        )
        return WAITING_FOR_PHOTO

async def handle_non_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # This handles when user sends text or other content when we're expecting a photo
    await update.message.reply_text(
        "📸 Please send a photo of your student card first."
    )
    return WAITING_FOR_PHOTO

GROUP_CHAT_ID = -1003095501562  # Replace with your group's chat ID (NOT invite link!)

async def verify_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Check if message exists and has text
    if not update.message or not update.message.text:
        await update.message.reply_text("⚠️ Please send your name and family name as text.")
        return WAITING_FOR_NAME
    
    full_text = update.message.text.strip()
    parts = full_text.split()

    logger.info(f"User {update.effective_user.id} trying to verify: {full_text}")

    if len(parts) < 2:
        await update.message.reply_text("⚠️ Please send both name and family name (e.g., John Doe).")
        return WAITING_FOR_NAME

    # normalize user input
    name = parts[0].lower()
    surname = " ".join(parts[1:]).lower()

    # Search in students list
    for student in students:
        student_name = student["NOM"].strip().lower()
        student_surname = student["PRENOM"].strip().lower()

        if student_name == name and student_surname == surname:
            if student.get("joined", False):
                await update.message.reply_text("⚠️ You have already joined the group. 7ab tdkhol 10 fois nta m9wd!")
                return ConversationHandler.END

            try:
                # 🔥 Create one-time invite link
                invite: ChatInviteLink = await context.bot.create_chat_invite_link(
                    chat_id=GROUP_CHAT_ID,
                    member_limit=1
                )

                # Send invite link
                await update.message.reply_text(
                    f"✅ Welcome {student['NOM']} {student['PRENOM']}! "
                    f"Here is your personal invite link:\n{invite.invite_link}"
                )

                # Mark as joined and save
                student["joined"] = True
                save_students(students)
                logger.info(f"User {update.effective_user.id} successfully verified as {student['NOM']} {student['PRENOM']}")
                return ConversationHandler.END
                
            except Exception as e:
                await update.message.reply_text("❌ Error creating invite link. Please contact administrator.")
                return ConversationHandler.END

    await update.message.reply_text("❌ Your name was not found in the list. Please try again with the correct name and family name.")
    return WAITING_FOR_NAME

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.reply_text("Operation cancelled. Send /start to begin again.")
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"Error in cancel handler: {e}")
        return ConversationHandler.END

# ==== MAIN ====
def main():
    # Check if students data is loaded
    if not students:
        logger.error("No students data loaded. Please check your CSV file.")
        return
    
    while True:
        try:
            app = Application.builder().token(TELEGRAM_TOKEN).build()

            # Add error handler
            app.add_error_handler(error_handler)

            # Conversation handler
            conv_handler = ConversationHandler(
                entry_points=[CommandHandler("start", start)],
                states={
                    WAITING_FOR_PHOTO: [
                        MessageHandler(filters.PHOTO, handle_photo),
                        MessageHandler(~filters.PHOTO, handle_non_photo)
                    ],
                    WAITING_FOR_NAME: [
                        MessageHandler(filters.TEXT & ~filters.COMMAND, verify_name)
                    ]
                },
                fallbacks=[CommandHandler("cancel", cancel)]
            )

            app.add_handler(conv_handler)

            logger.info("🤖 Bot is starting...")
            app.run_polling(drop_pending_updates=True)
            
        except NetworkError as e:
            logger.error(f"Network error: {e}")
            logger.info("Retrying in 30 seconds...")
            asyncio.sleep(30)
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            logger.info("Retrying in 60 seconds...")
            asyncio.sleep(60)

if __name__ == "__main__":
    main()