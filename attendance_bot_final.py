from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from datetime import datetime

TOKEN = "8759921788:AAHsO6ba2HHGWirLNAvYKfrUb0zQRdAQK1Q"

active_breaks = {}
break_start_times = {}
break_types = {}
daily_counts = {}
work_sessions = {}
total_break_time = {}

keyboard = [
    ["🚀 Start Work", "🚻 WC"],
    ["🚬 Smoke", "🍽️ Eat"],
    ["↩️ Back", "🔴 Off Work"]
]
reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_user(update):
    u = update.effective_user
    return u.username if u.username else u.first_name

def working(username):
    return username in work_sessions

async def break_warning(context):
    d = context.job.data
    await context.bot.send_message(
        chat_id=d["chat_id"],
        text=f"⚠️ @{d['username']} exceeded {d['break_type']} limit."
    )

async def startwork(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = get_user(update)
    daily_counts.setdefault(username, {"wc":0,"smoke":0,"eat":0})
    work_sessions[username] = datetime.now()
    total_break_time.setdefault(username, 0)

    await update.message.reply_text(
        f"✅ @{username} Start Work recorded\n🕒 {datetime.now().strftime('%I:%M %p')}",
        reply_markup=reply_markup
    )

async def start_break(update, context, kind, label, max_count, duration_sec):
    username = get_user(update)

    if not working(username):
        await update.message.reply_text(f"❌ @{username}, you must Start Work first.", reply_markup=reply_markup)
        return

    if username in break_types:
        await update.message.reply_text(f"⚠️ @{username}, you already have an active {break_types[username]} break.\nPlease press Back first.", reply_markup=reply_markup)
        return

    daily_counts.setdefault(username, {"wc":0,"smoke":0,"eat":0})
    if daily_counts[username][kind] >= max_count:
        await update.message.reply_text(f"⚠️ @{username} {label} limit reached ({max_count})", reply_markup=reply_markup)
        return

    daily_counts[username][kind] += 1
    break_start_times[username] = datetime.now()
    break_types[username] = label

    job = context.job_queue.run_once(
        break_warning,
        duration_sec,
        data={"username": username, "break_type": label, "chat_id": update.effective_chat.id}
    )
    active_breaks[username] = job

    used = daily_counts[username][kind]
    remaining = max_count - used

    await update.message.reply_text(
        f"{label} @{username} started\n🕒 {datetime.now().strftime('%I:%M %p')}\n📊 Used: {used}/{max_count} ({remaining} remaining)",
        reply_markup=reply_markup
    )

async def wc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_break(update, context, "wc", "WC", 5, 900)

async def smoke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_break(update, context, "smoke", "Smoke", 5, 900)

async def eat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_break(update, context, "eat", "Meal", 2, 2400)

async def back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = get_user(update)

    if not working(username):
        await update.message.reply_text(f"❌ @{username}, you are currently Off Work.", reply_markup=reply_markup)
        return

    if username not in break_start_times:
        await update.message.reply_text(f"⚠️ @{username} has no active break.", reply_markup=reply_markup)
        return

    duration = datetime.now() - break_start_times[username]
    secs = int(duration.total_seconds())
    total_break_time[username] = total_break_time.get(username, 0) + secs

    if username in active_breaks:
        active_breaks[username].schedule_removal()
        del active_breaks[username]

    del break_start_times[username]
    del break_types[username]

    await update.message.reply_text(
        f"↩️ @{username} Back To Seat\n⏱️ Duration: {secs//60} min {secs%60} sec",
        reply_markup=reply_markup
    )

async def offwork(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = get_user(update)

    if not working(username):
        await update.message.reply_text("❌ Start Work first", reply_markup=reply_markup)
        return

    shift_sec = int((datetime.now() - work_sessions[username]).total_seconds())
    brk_sec = total_break_time.get(username, 0)
    work_sec = max(0, shift_sec - brk_sec)

    await update.message.reply_text(
        f"🔴 @{username} Off Work\n\n"
        f"🕒 Total Shift: {shift_sec//3600}h {(shift_sec%3600)//60}m\n"
        f"🚻 WC Used: {daily_counts[username]['wc']}/5\n"
        f"🚬 Smoke Used: {daily_counts[username]['smoke']}/5\n"
        f"🍽️ Eat Used: {daily_counts[username]['eat']}/2\n"
        f"⏳ Total Break: {brk_sec//3600}h {(brk_sec%3600)//60}m\n"
        f"✅ Working Time: {work_sec//3600}h {(work_sec%3600)//60}m",
        reply_markup=reply_markup
    )

    # Cleanup
    work_sessions.pop(username, None)
    break_start_times.pop(username, None)
    break_types.pop(username, None)
    active_breaks.pop(username, None)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🚀 Start Work": await startwork(update, context)
    elif text == "🚻 WC": await wc(update, context)
    elif text == "🚬 Smoke": await smoke(update, context)
    elif text == "🍽️ Eat": await eat(update, context)
    elif text == "↩️ Back": await back(update, context)
    elif text == "🔴 Off Work": await offwork(update, context)

app = Application.builder().token(TOKEN).build()
app.add_handler(CommandHandler("startwork", startwork))
app.add_handler(CommandHandler("wc", wc))
app.add_handler(CommandHandler("smoke", smoke))
app.add_handler(CommandHandler("eat", eat))
app.add_handler(CommandHandler("back", back))
app.add_handler(CommandHandler("offwork", offwork))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, button_handler))

print("Bot Running...")
app.run_polling()
