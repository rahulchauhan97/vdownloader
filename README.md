# vdownloader — Telegram Social Video Downloader

A Telegram bot that downloads videos from Instagram, X (Twitter), TikTok, YouTube and many other sites using yt-dlp. Includes:

- Format selection (quality/format) using inline buttons
- Progress updates while downloading
- Cancellable downloads (/cancel or Cancel button)
- Admin commands to manage bot users and settings
- Simple JSON persistence for admins, bans and settings
- Docker + docker-compose + systemd guidance for VPS

Security & legal
- Use responsibly and respect copyright and each site's Terms of Service.
- This bot downloads only public content; handling private/protected content requires cookies/credentials and may violate terms.

Quick setup (local / VPS)
1. Create a private GitHub repo named `vdownloader` (optional) and push the files from this repository.
2. Install system packages (Debian/Ubuntu example):
   ```
   sudo apt update && sudo apt install -y python3 python3-venv python3-pip ffmpeg git
   ```
3. Clone on your server (or copy files), create venv:
   ```
   git clone <your-repo-url> vdownloader
   cd vdownloader
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
4. Configure environment variables:
   - BOT_TOKEN (required): Bot token from BotFather
   - ADMIN_IDS (optional, recommended): comma-separated numeric Telegram user ids (e.g. `12345678,87654321`)
     - Alternatively, edit `data/state.json` and add numeric ids under \"admins\" before first run.
   - MAX_UPLOAD_MB (optional): maximum upload size in MB (default 1900)
   Example:
   ```
   export BOT_TOKEN="123456:ABC-def..."
   export ADMIN_IDS="12345678"
   export MAX_UPLOAD_MB=1900
   ```
5. Start the bot:
   ```
   python main.py
   ```

Using Docker
1. Build:
   ```
   docker build -t vdownloader .
   ```
2. Run:
   ```
   docker run -e BOT_TOKEN="..." -e ADMIN_IDS="12345678" -e MAX_UPLOAD_MB=1900 -d --name vdownloader vdownloader
   ```

Using systemd (VPS)
- See `deploy/vps-systemd.service` for an example unit. Edit the ExecStart path and Environment to include your BOT_TOKEN and ADMIN_IDS.

Admin workflow
- Admins are identified by numeric Telegram user id. Use ADMIN_IDS env var or `data/state.json`.
- Admin commands (admin-only):
  - /admin_add <user_id>
  - /admin_remove <user_id>
  - /admin_list
  - /ban <user_id>
  - /unban <user_id>
  - /bans
  - /active_downloads
  - /stop_download <chat_id>
  - /set_max_upload <MB>
  - /stats
  - /broadcast <message> (requires confirmation via inline button)
  - /shutdown (requires confirmation)

Persistence
- State persisted in `data/state.json`:
  - admins: list of numeric ids
  - bans: list of banned numeric ids
  - settings: contains runtime settings like `max_upload_mb`
  - users: minimal user history for stats/broadcast
  - stats: counters for total downloads/bytes

If you want:
- I can create a ZIP of the repository for download now.
- I can push these files to a GitHub private repo if you create the empty repo and give me the remote URL (or add me to the repo).
- I can add a small systemd install script or help configure automatic updates.