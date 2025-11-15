# 🧠 Homelab Dashboard

This is a Flask-based dashboard for my homelab services.

## 🚀 Goal

A self-hosted control panel to monitor and manage Docker containers and service health — eventually integrated with a Discord bot.

## 📦 Tech

- Python + Flask (backend)
- Docker SDK
- HTML + JS frontend
- Deployed via Docker
## .env Variables:
- DONT_USE_DOCKER: Mainly for testing, uses mock containers instead  of live Docker

## 🔧 Local Setup

```bash
pip install -r requirements.txt
python backend/app.py
