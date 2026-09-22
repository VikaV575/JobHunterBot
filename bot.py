import os
from dotenv import load_dotenv
from telegram import Update
from collector import get_jobs
from filters import filter_jobs
from scorer import score_jobs
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")


def select_feed_jobs(ranked_jobs, max_total=10, max_amazon=3):
    selected_jobs = []
    amazon_count = 0

    for job in ranked_jobs:
        is_amazon = job.get("source") == "Amazon Jobs"

        if is_amazon:
            if amazon_count >= max_amazon:
                continue

            amazon_count += 1

        selected_jobs.append(job)

        if len(selected_jobs) >= max_total:
            break

    return selected_jobs


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔍 מחפשת משרות...\n\n"
        "1. Software Student - NVIDIA\n"
        "2. Validation Student - Intel\n"
        "3. Backend Student - Check Point"
    )


async def jobs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("jobs command received")

    await update.message.reply_text("🔍 מחפשת משרות...")

    try:
        print("Calling get_jobs...")
        jobs_list = await get_jobs()

        print(f"Found {len(jobs_list)} total jobs")

        relevant_jobs = filter_jobs(jobs_list)
        print(f"Relevant jobs: {len(relevant_jobs)}")

        ranked_jobs = score_jobs(relevant_jobs)
        feed_jobs = select_feed_jobs(
            ranked_jobs,
            max_total=10,
            max_amazon=3,
        )

        message = "🔍 משרות רלוונטיות שמצאתי:\n\n"

        for job in feed_jobs:
            message += (
                f"🎯 התאמה: {job['score']}%\n"
                f"💼 {job['title']}\n"
                f"🏢 {job['company_name']}\n"
                f"📍 {job['location']}\n"
                f"🌐 {job['source']}\n"
                f"🔗 {job['url']}\n\n"
            )

        await update.message.reply_text(message)

    except Exception as error:
        print("ERROR IN /jobs:", error)
        await update.message.reply_text(
            f"❌ קרתה שגיאה: {type(error).__name__}"
        )


app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("jobs", jobs))
print("Bot is running...")
app.run_polling()
