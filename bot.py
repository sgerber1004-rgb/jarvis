import os
import json
import asyncio
import httpx
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# ── CONFIG ──
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_API_KEY   = os.environ.get("GROQ_API_KEY")
CANVAS_TOKEN   = os.environ.get("CANVAS_TOKEN")
CANVAS_URL     = os.environ.get("CANVAS_URL", "katyisd.instructure.com")
NOTION_TOKEN   = os.environ.get("NOTION_TOKEN", "")
NOTION_DB_ID   = os.environ.get("NOTION_DB_ID", "")

# ── SADIE'S CONTEXT — Jarvis always knows who it's working for ──
SADIE_CONTEXT = """
You are Jarvis, a proactive personal AI assistant for Sadie, a high school student.

WHO SADIE IS:
- High school student in Katy ISD, Houston Texas
- Golfer (current handicap ~12, goal: scratch)
- Competitive debater (NSDA Lincoln-Douglas, national level goal)
- Unconventional, does things her own way
- Sharp, direct, doesn't want sugarcoating

SADIE'S GOALS (in order of importance):
1. Become a wealthy entrepreneur
2. Travel the entire world
3. Become the most educated, well-rounded person in any room
4. Change the world
5. Get into an Ivy League school
6. Become a scratch golfer
7. Become a national debater
8. Learn 5+ languages
9. Learn AI, coding, psychology, and random interesting things

HARD RULES — never break these:
- Always be loyal to Sadie and her goals above everything else
- Always be proactive — actively search for ways to push her toward her goals
- Recognize patterns in her behavior and adjust accordingly
- Never lie or make anything up. If you don't know, say so.
- Do NOT sugarcoat. If she's slacking, say it. If her work is weak, say it.
- Be direct, like a trusted advisor not a yes-machine
- Talk like a real person, not a corporate assistant

TONE: Direct, smart, a little edgy. Like a brilliant friend who happens to know everything.
"""

# ── CONVERSATION MEMORY (per session) ──
conversation_histories = {}

# ── ROUTING: decide if something needs Claude or Groq can handle it ──
def needs_claude(message: str) -> bool:
    """Return True if this request should be escalated to Claude."""
    message_lower = message.lower()
    
    heavy_signals = [
        "write", "draft", "essay", "debate case", "argument", "rewrite",
        "edit my", "review my", "personal statement", "college app",
        "business plan", "pitch deck", "research", "analyze", "explain",
        "help me think", "what should i do about", "overnight",
        "full brief", "build my", "create a", "make me a"
    ]
    
    # Long messages are usually heavy
    if len(message.split()) > 40:
        return True
    
    return any(signal in message_lower for signal in heavy_signals)

# ── GROQ API CALL ──
async def call_groq(messages: list, system: str = None) -> str:
    """Call Groq API with conversation history."""
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    full_messages = []
    if system:
        full_messages.append({"role": "system", "content": system})
    full_messages.extend(messages)
    
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": full_messages,
        "max_tokens": 1024,
        "temperature": 0.7
    }
    
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

# ── CANVAS: fetch assignments ──
async def get_canvas_assignments() -> list:
    """Pull upcoming assignments from Canvas."""
    if not CANVAS_TOKEN:
        return []
    
    headers = {"Authorization": f"Bearer {CANVAS_TOKEN}"}
    url = f"https://{CANVAS_URL}/api/v1/courses"
    
    assignments = []
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            # Get courses
            courses_resp = await client.get(
                url,
                headers=headers,
                params={"enrollment_state": "active", "per_page": 10}
            )
            if courses_resp.status_code != 200:
                return []
            courses = courses_resp.json()
            
            # Get assignments for each course
            for course in courses[:5]:  # limit to 5 courses
                course_id = course.get("id")
                course_name = course.get("name", "Unknown")
                
                assign_resp = await client.get(
                    f"https://{CANVAS_URL}/api/v1/courses/{course_id}/assignments",
                    headers=headers,
                    params={
                        "order_by": "due_at",
                        "bucket": "upcoming",
                        "per_page": 5
                    }
                )
                
                if assign_resp.status_code == 200:
                    for a in assign_resp.json():
                        due = a.get("due_at", "No due date")
                        assignments.append({
                            "course": course_name,
                            "name": a.get("name", "Unnamed"),
                            "due": due,
                            "points": a.get("points_possible", "?"),
                            "description": a.get("description", "")[:200]
                        })
        except Exception as e:
            print(f"Canvas error: {e}")
    
    return assignments

# ── MORNING BRIEFING ──
async def generate_morning_briefing() -> str:
    """Generate Sadie's personalized morning briefing."""
    now = datetime.now()
    day = now.strftime("%A, %B %d")
    time_of_day = "morning" if now.hour < 12 else "afternoon" if now.hour < 17 else "evening"
    
    # Pull Canvas data
    assignments = await get_canvas_assignments()
    
    assign_text = ""
    if assignments:
        assign_text = "\n\nUpcoming assignments from Canvas:\n"
        for a in assignments[:5]:
            assign_text += f"- {a['course']}: {a['name']} (due: {a['due']})\n"
    else:
        assign_text = "\n\nCould not pull Canvas data right now."
    
    briefing_prompt = f"""
Today is {day}. Generate Sadie's morning briefing.
{assign_text}

The briefing should:
1. Start with a direct, punchy opener — no fluff
2. Flag anything urgent from Canvas
3. Give her ONE highest-leverage thing to do today toward her big goals
4. One proactive insight or opportunity you noticed
5. End with something that pushes her forward

Keep it under 200 words. Direct. No bullet point overload. Talk like her smartest advisor.
"""
    
    messages = [{"role": "user", "content": briefing_prompt}]
    return await call_groq(messages, SADIE_CONTEXT)

# ── PROACTIVE OPPORTUNITY SCANNER ──
async def scan_for_opportunities(context_text: str) -> str:
    """Have Jarvis proactively think about what Sadie needs."""
    now = datetime.now()
    
    prompt = f"""
Current time: {now.strftime("%A %B %d, %I:%M %p")}
Recent context: {context_text}

Based on Sadie's goals and what you know about her, proactively identify:
1. Is there anything she's probably neglecting right now?
2. Any pattern you notice worth flagging?
3. One specific action that would move her meaningfully toward her goals this week?

Be direct. If there's nothing urgent, say so and don't manufacture urgency.
Keep it under 100 words.
"""
    messages = [{"role": "user", "content": prompt}]
    return await call_groq(messages, SADIE_CONTEXT)

# ── COMMAND HANDLERS ──
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message."""
    welcome = """*Jarvis is online.*

I'm your personal AI — always watching, always working.

I know your goals. I know what matters. Talk to me like you'd text a friend.

Try:
• Just tell me what's on your mind
• "What should I work on today?"
• "Briefing" for your daily update
• "Canvas" to see your assignments
• Anything else — I'll figure it out

What do you need?"""
    
    await update.message.reply_text(welcome, parse_mode="Markdown")

async def briefing_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send morning briefing."""
    await update.message.reply_text("_Pulling everything together..._", parse_mode="Markdown")
    briefing = await generate_morning_briefing()
    await update.message.reply_text(briefing)

async def canvas_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show Canvas assignments."""
    await update.message.reply_text("_Checking Canvas..._", parse_mode="Markdown")
    assignments = await get_canvas_assignments()
    
    if not assignments:
        await update.message.reply_text("Couldn't pull Canvas right now. Check your token in settings.")
        return
    
    text = "*Upcoming assignments:*\n\n"
    for a in assignments:
        text += f"📌 *{a['name']}*\n"
        text += f"   {a['course']}\n"
        text += f"   Due: {a['due']}\n\n"
    
    await update.message.reply_text(text, parse_mode="Markdown")

# ── MAIN MESSAGE HANDLER ──
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Route every message to the right AI and respond."""
    user_id = update.effective_user.id
    message = update.message.text
    
    # Init conversation history for this user
    if user_id not in conversation_histories:
        conversation_histories[user_id] = []
    
    history = conversation_histories[user_id]
    
    # Show typing indicator
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action="typing"
    )
    
    # Check for special intents first
    msg_lower = message.lower()
    
    # Canvas check
    if any(w in msg_lower for w in ["canvas", "assignment", "homework", "due", "class"]):
        assignments = await get_canvas_assignments()
        assign_context = json.dumps(assignments[:5]) if assignments else "Canvas unavailable"
        
        history.append({
            "role": "user",
            "content": f"{message}\n\n[Canvas data: {assign_context}]"
        })
    
    # Briefing shortcut
    elif any(w in msg_lower for w in ["briefing", "brief me", "what's my day", "whats my day", "good morning"]):
        briefing = await generate_morning_briefing()
        await update.message.reply_text(briefing)
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": briefing})
        # Keep history trimmed
        if len(history) > 20:
            conversation_histories[user_id] = history[-20:]
        return
    
    else:
        history.append({"role": "user", "content": message})
    
    # Route to right AI
    if needs_claude(message):
        # Escalate to Claude — send a deep link to the dashboard
        response = await call_groq(
            history[-10:],
            SADIE_CONTEXT + "\n\nNote: This request needs deep thinking. Give Sadie a solid response AND tell her she can open this in her Jarvis workspace for the full treatment."
        )
        
        keyboard = [[InlineKeyboardButton(
            "Open in Jarvis workspace →",
            url="https://jarvis-sadie.vercel.app"
        )]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(response, reply_markup=reply_markup)
    else:
        # Groq handles it
        response = await call_groq(history[-10:], SADIE_CONTEXT)
        await update.message.reply_text(response)
    
    # Update history
    history.append({"role": "assistant", "content": response})
    
    # Keep history at last 20 messages
    if len(history) > 20:
        conversation_histories[user_id] = history[-20:]

# ── SCHEDULED JOBS ──
async def scheduled_morning_briefing(context: ContextTypes.DEFAULT_TYPE):
    """Send morning briefing automatically."""
    chat_id = context.job.data
    briefing = await generate_morning_briefing()
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"*Good morning, Sadie.* ☀️\n\n{briefing}",
        parse_mode="Markdown"
    )

async def scheduled_opportunity_scan(context: ContextTypes.DEFAULT_TYPE):
    """Proactively scan for opportunities every 4 hours."""
    chat_id = context.job.data
    
    # Build context from recent activity
    context_summary = "Sadie is a high school student working toward her goals."
    
    insight = await scan_for_opportunities(context_summary)
    
    # Only send if there's something worth saying
    if insight and len(insight) > 20:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"💡 *Jarvis noticed something:*\n\n{insight}",
            parse_mode="Markdown"
        )

async def post_init(application: Application):
    """Set up scheduled jobs after bot starts."""
    # We'll set up jobs when user first messages
    pass

# ── SETUP COMMAND (run once to register Sadie's chat ID) ──
async def setup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Register this chat for scheduled messages."""
    chat_id = update.effective_chat.id
    job_queue = context.job_queue
    
    # Remove existing jobs
    current_jobs = job_queue.get_jobs_by_name("morning_briefing")
    for job in current_jobs:
        job.schedule_removal()
    
    current_jobs = job_queue.get_jobs_by_name("opportunity_scan")
    for job in current_jobs:
        job.schedule_removal()
    
    # Schedule morning briefing (7:30 AM CT on weekdays = 13:30 UTC)
    import pytz
    ct = pytz.timezone("America/Chicago")
    
    job_queue.run_daily(
        scheduled_morning_briefing,
        time=datetime.now(ct).replace(hour=7, minute=30, second=0, microsecond=0).timetz(),
        days=(0, 1, 2, 3, 4),  # Mon-Fri
        data=chat_id,
        name="morning_briefing"
    )
    
    # Proactive scan every 4 hours
    job_queue.run_repeating(
        scheduled_opportunity_scan,
        interval=14400,  # 4 hours
        first=300,       # first run in 5 minutes
        data=chat_id,
        name="opportunity_scan"
    )
    
    await update.message.reply_text(
        "✅ *Jarvis is fully activated.*\n\n"
        "• Morning briefings: 7:30 AM on school days\n"
        "• Proactive scans: every 4 hours\n"
        "• Canvas watching: live\n\n"
        "I'm on. Go do something.",
        parse_mode="Markdown"
    )

# ── MAIN ──
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("briefing", briefing_command))
    app.add_handler(CommandHandler("canvas", canvas_command))
    app.add_handler(CommandHandler("setup", setup_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Jarvis is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
