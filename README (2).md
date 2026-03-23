# Jarvis — Sadie's Personal AI

## Deploy to Render

1. Push this repo to GitHub
2. Go to render.com → New → Web Service → connect your GitHub repo
3. Add these environment variables in Render dashboard:
   - TELEGRAM_TOKEN — your bot token from @BotFather
   - GROQ_API_KEY — your Groq API key
   - CANVAS_TOKEN — your Canvas access token
4. Deploy
5. Open Telegram, message your bot, send /start then /setup

## Commands
- /start — wake Jarvis up
- /setup — activate scheduled briefings and scanning
- /briefing — get your morning briefing right now
- /canvas — see upcoming assignments
- Just talk — Jarvis handles everything else naturally

## How routing works
- Short/simple requests → Groq (free, fast)
- Long/complex writing/research → escalates to Claude with a link to your workspace
