# 🧠 Homelab Dashboard

This is a Flask-based dashboard for my homelab services.

## 🚀 Goal

A self-hosted control panel for Docker containers, container widgets, and DNS/reverse-proxy management.

## 📦 Tech

- Python + Flask (backend)
- Docker SDK
- HTML + JS frontend
- Deployed via Docker
## Environment Variables

- `TESTING_MODE`: Set to `1` to use mock containers instead of live Docker (for development/testing)

## 🔧 Local Setup

```bash
pip install -r requirements.txt
python backend/app.py
