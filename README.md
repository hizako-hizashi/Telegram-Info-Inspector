# ✈️ Telegram Info Inspector

> **High-Performance MTProto Entity Inspector & Profile Visualizer**

![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Pyrogram](https://img.shields.io/badge/Engine-Pyrogram_MTProto-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white)
![UI](https://img.shields.io/badge/UI-Glassmorphism-a855f7?style=for-the-badge)

---

## 📌 Overview

**Telegram Info Inspector** is a fast, asynchronous FastAPI web application powered by **Pyrogram (MTProto)**. It allows developers and users to inspect Telegram entities (Users, Bots, Supergroups, and Channels) by username or ID

---

## 🌟 Key Features

- 🔍 **Comprehensive Entity Lookup**: Query Telegram Users, Bots, Supergroups, and Channels by `@username` or numeric `User ID` / `Chat ID`.
- 🎨 **Visual Profile Card UI**: Real-time rendering of user profile cards with avatars, account badges, bio, and detailed network metadata.
- ⚡ **Multi-Format Output**: Toggle seamlessly between **Visual Card**, **Formatted Text**, and **Raw JSON** responses.
- 🖼️ **Profile Picture Hosting**: Automatic extraction of high-resolution profile photos with temporary cloud upload and auto-cleanup.
- 🌐 **Data Center (DC) Mapping**: Identifies Telegram Data Center locations worldwide (e.g., Miami, Amsterdam, Singapore, Frankfurt).

---

## 🛠️ Project Structure

```
telegram-info-main/
├── config.py           # Obfuscated Base64 security configuration
├── main.py             # FastAPI application & Pyrogram MTProto engine
├── requirements.txt    # Production dependencies
├── Procfile            # Deployment script for Railway / Heroku
├── vercel.json         # Deployment configuration for Vercel Serverless
├── README.md           # Project documentation
└── static/
    └── index.html      # Glassmorphism Web Interface
```

---

## ⚙️ Environment Variables

Set the following environment variables in your deployment dashboard (Vercel / Railway / VPS):

| Variable | Required | Description |
| :--- | :---: | :--- |
| `API_ID` | Yes | Telegram MTProto API ID (from [my.telegram.org](https://my.telegram.org)) |
| `API_HASH` | Yes | Telegram MTProto API Hash |
| `BOT_TOKEN` | Yes | Telegram Bot Token (from [@BotFather](https://t.me/BotFather)) |
| `PORT` | Optional | HTTP Server Port (Default: `5000`) |

---

## 💻 Local Development Setup

### 1. Prerequisites
- Python 3.8+
- Active Telegram Bot Token

### 2. Installation & Execution
```bash
# Clone repository
git clone https://github.com/bbinl/fuck.git
cd telegram-info-main

# Install dependencies
pip install -r requirements.txt

# Run server locally
python main.py
```
Open `http://localhost:5000` in your web browser.

---

## 🌐 Deployment Support

### 🚀 1-Click Deploy to Vercel
Click the button below to import and deploy this project directly on Vercel:

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https%3A%2F%2Fgithub.com%2Fbbinl%2Ffuck)

- **Vercel**: Pre-configured with `vercel.json` for serverless deployment.
- **Railway / Render**: Deploy using the included `Procfile` (`uvicorn main:app --host 0.0.0.0 --port $PORT`).

---

Powered by **Pyrogram MTProto Engine** & **FastAPI**
