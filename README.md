# SuccuBot

A fully-featured Telegram group bot with federation controls, moderation, flirty XP games, summon system, flyers, and admin bypass for owner.

## Features
- Federation: create, manage, ban, link groups (with MongoDB)
- Moderation: warns, mutes, flirty warns (with timers and escalation)
- Fun: XP (“naughty meter”), /bite, /spank, /tease, leaderboard
- Summon: summon one/all, flirty summon, track all
- Flyer system: upload, change, delete, get flyers
- /cancel: abort multi-step commands
- Admin bypass for group owner ID
- Contextual /help (shows only commands users can use)
- Data persists (JSON for most, Mongo for federation)

## Getting Started

1. **Clone repo or copy files**
2. Copy `.env.example` to `.env` and fill in your:
   - BOT_TOKEN
   - API_ID & API_HASH ([get from my.telegram.org](https://my.telegram.org/))
   - MONGO_URI (MongoDB Atlas recommended)
3. Install requirements:
