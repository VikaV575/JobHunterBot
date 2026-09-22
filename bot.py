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


def select_feed_jobs(
    ranked_jobs,
    min_score=50,
    max_amazon=3,
):
    selected_jobs = []
    amazon_count = 0

    for job in ranked_jobs:
        # "Above 50%" means strictly greater than 50.
        if job.get("score", 0) <= min_score:
            continue

        is_amazon = job.get("source") == "Amazon Jobs"

        if is_amazon:
            if amazon_count >= max_amazon:
                continue

            amazon_count += 1

        selected_jobs.append(job)

    return selected_jobs


def format_job_message(job, index):
    matches = job.get("matches", [])
    match_text = (
        ", ".join(matches)
        if matches
        else "technical role"
    )

    return (
        f"{index}. 🎯 התאמה: {job['score']}%\n"
        f"💼 {job['title']}\n"
        f"🏢 {job['company_name']}\n"
        f"📍 {job['location']}\n"
        f"✅ למה: {match_text}\n"
        f"🌐 {job['source']}\n"
        f"🔗 {job['url']}"
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔍 מחפשת משרות...\n\n"
        "שלחי /jobs כדי לקבל את כל המשרות "
        "עם התאמה מעל 50%."
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
            min_score=50,
            max_amazon=3,
        )

        print(
            f"Sending {len(feed_jobs)} jobs above 50% "
            "to Telegram..."
        )

        if not feed_jobs:
            await update.message.reply_text(
                "לא מצאתי כרגע משרות עם התאמה מעל 50%."
            )
            return

        await update.message.reply_text(
            f"🔍 מצאתי {len(feed_jobs)} משרות "
            f"עם התאמה מעל 50%."
        )

        for index, job in enumerate(
            feed_jobs,
            start=1,
        ):
            await update.message.reply_text(
                format_job_message(job, index)
            )

        print("Telegram jobs sent")

    except Exception as error:
        print(
            "ERROR IN /jobs:",
            type(error).__name__,
            error,
        )

        await update.message.reply_text(
            f"❌ קרתה שגיאה: "
            f"{type(error).__name__}: {error}"
        )


app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("jobs", jobs))
print("Bot is running...")
app.run_polling()
