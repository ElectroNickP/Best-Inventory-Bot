# Telegram Inventory Bot

Inventory tracking Telegram bot for guides: who took which device, when, and in what condition (with photos), plus an in-bot admin panel for managing categories and items.

## Features

- Equipment catalog by categories (speakers, Wi-Fi routers, etc.).
- Take/return flow with mandatory photo and full history per item and user.
- Admin panel inside Telegram:
  - Overview: what is on hands, what is available.
  - Category and item management (create/rename/delete, mark lost/maintenance).
  - User list and history.
- SQLite storage, ready to be containerized and deployed to a VPS.

## Tech stack

- Python 3.12+
- aiogram 3.x
- SQLAlchemy 2.x (async) + SQLite

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```bash
BOT_TOKEN=your_telegram_bot_token_here
DB_URL=sqlite+aiosqlite:///./inventory.db
INITIAL_ADMIN_IDS=123456789,987654321         # optional, admin by Telegram ID
INITIAL_ADMIN_USERNAMES=Pankonick            # optional, admin by username (no @, comma-separated)
```

Then run:

```bash
python main.py
```

## Docker

A `Dockerfile` and optional `docker-compose.yml` will be provided to run the bot in a container on a VPS.

