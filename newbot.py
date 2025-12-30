import logging
import config
import handlers
import db
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

def main():
    if not config.BOT_TOKEN:
        logger.error("No BOT_TOKEN found in config!")
        return
    
    # Initialize DB
    db.init_db()

    app = ApplicationBuilder().token(config.BOT_TOKEN).build()

    # Handlers from handlers.py
    app.add_handler(CommandHandler("start", handlers.start_command))
    app.add_handler(CommandHandler("broadcast", handlers.broadcast_command))
    app.add_handler(CommandHandler("broadcast_unpaid", handlers.broadcast_unpaid_command))
    app.add_handler(CommandHandler("stats", handlers.admin_stats_command))
    app.add_handler(CommandHandler("funnel", handlers.admin_funnel_command))
    app.add_handler(CommandHandler("add_coupon", handlers.admin_add_coupon))
    app.add_handler(CommandHandler("add_gift", handlers.admin_add_gift))
    app.add_handler(CommandHandler("del_coupon", handlers.admin_del_coupon))
    app.add_handler(CommandHandler("coupons", handlers.admin_list_coupons))
    app.add_handler(CommandHandler("cancel", handlers.cancel_broadcast_command))
    app.add_handler(CallbackQueryHandler(handlers.handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_text))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handlers.handle_receipt))
    
    # Jobs (disabled temporarily - requires python-telegram-bot[job-queue])
    # job_queue = app.job_queue
    # job_queue.run_repeating(handlers.check_abandoned_users_job, interval=3600, first=60)

    print("🤖 Bot (Refactored) is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
