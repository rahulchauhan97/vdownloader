# vdownloader — Telegram Video Downloader Bot

A powerful Telegram bot that downloads videos from YouTube, Instagram, TikTok, Twitter/X, and 1000+ other sites using yt-dlp.

## Features

- 🎬 **Multi-platform support**: YouTube, Instagram, TikTok, Twitter/X, and many more
- 🎯 **Format selection**: Choose video quality/format via inline buttons
- 📊 **Progress updates**: Real-time download progress with speed and ETA
- ❌ **Cancellable downloads**: Stop downloads anytime with /cancel
- 👥 **User management**: Ban/unban users, admin system
- 📈 **Statistics**: Track downloads, data usage, and user count
- 📢 **Broadcast**: Send messages to all users (admin only)
- 💾 **Persistent state**: JSON-based storage for settings and stats
- 🐳 **Docker ready**: Easy deployment with Docker and docker-compose
- 🔧 **Flexible deployment**: Systemd service, Heroku, or standalone

## Quick Start

### Prerequisites

- Python 3.11+
- FFmpeg (for video processing)
- Telegram Bot Token (from [@BotFather](https://t.me/BotFather))

### Installation (Local/VPS)

1. **Install system dependencies** (Debian/Ubuntu):
   ```bash
   sudo apt update && sudo apt install -y python3 python3-venv python3-pip ffmpeg git
   ```

2. **Clone repository**:
   ```bash
   git clone <your-repo-url> vdownloader
   cd vdownloader
   ```

3. **Create virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

4. **Configure environment**:
   ```bash
   export BOT_TOKEN="your_bot_token_here"
   export ADMIN_IDS="your_telegram_user_id"
   export MAX_UPLOAD_MB=1900
   ```

5. **Run the bot**:
   ```bash
   python main.py
   ```

### Using Docker

#### Build and run with Docker:
```bash
docker build -t vdownloader .
docker run -d \
  -e BOT_TOKEN="your_bot_token" \
  -e ADMIN_IDS="your_user_id" \
  -e MAX_UPLOAD_MB=1900 \
  --name vdownloader \
  vdownloader
```

#### Using docker-compose:
```bash
# Edit docker-compose.yml with your credentials
docker-compose up -d
```

### Using systemd (VPS)

1. **Copy service file**:
   ```bash
   sudo cp deploy/vps-systemd.service /etc/systemd/system/vdownloader.service
   ```

2. **Edit service file**:
   ```bash
   sudo nano /etc/systemd/system/vdownloader.service
   # Update BOT_TOKEN, ADMIN_IDS, and paths
   ```

3. **Enable and start**:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable vdownloader
   sudo systemctl start vdownloader
   sudo systemctl status vdownloader
   ```

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `BOT_TOKEN` | Yes | - | Telegram bot token from BotFather |
| `ADMIN_IDS` | No | 360013457 | Comma-separated admin user IDs |
| `MAX_UPLOAD_MB` | No | 1900 | Maximum file upload size in MB |

### Finding Your Telegram User ID

1. Start a chat with [@userinfobot](https://t.me/userinfobot)
2. Send any message
3. Copy your numeric user ID

## Usage

### User Commands

- `/start` - Show welcome message and available commands
- `/help` - Display help information
- `/cancel` - Cancel current download

### Downloading Videos

1. Send a video URL to the bot
2. Wait for format analysis
3. Choose desired quality/format from buttons
4. Wait for download and upload

### Admin Commands

Only users in `ADMIN_IDS` can use these:

| Command | Description |
|---------|-------------|
| `/admin_add <user_id>` | Add a new admin |
| `/admin_remove <user_id>` | Remove an admin |
| `/admin_list` | List all admins |
| `/ban <user_id>` | Ban a user from using the bot |
| `/unban <user_id>` | Unban a user |
| `/bans` | List all banned users |
| `/active_downloads` | Show active downloads |
| `/stop_download <chat_id>` | Stop a specific download |
| `/set_max_upload <MB>` | Set maximum upload size |
| `/stats` | Show bot statistics |
| `/broadcast <message>` | Broadcast message to all users |
| `/shutdown` | Shutdown the bot (with confirmation) |

## Architecture

### Directory Structure

```
vdownloader/
├── main.py                     # Main bot implementation
├── requirements.txt            # Python dependencies
├── Dockerfile                  # Docker image definition
├── docker-compose.yml          # Docker compose configuration
├── Procfile                    # Heroku/cloud platform config
├── LICENSE                     # MIT License
├── README.md                   # This file
├── .gitignore                  # Git ignore rules
├── data/
│   ├── state.json             # Persistent state storage
│   └── admin_actions.log      # Admin action logs
├── deploy/
│   └── vps-systemd.service    # Systemd service file
└── scripts/
    └── init_repo.sh           # Repository initialization script
```

### State Management

The bot persists state in `data/state.json`:

```json
{
  "admins": [360013457],
  "bans": [],
  "settings": {
    "max_upload_mb": 1900
  },
  "users": {},
  "stats": {
    "downloads": 0,
    "bytes": 0
  }
}
```

### Download Flow

1. **URL Reception**: User sends video URL
2. **Format Extraction**: Bot analyzes available formats using yt-dlp
3. **Format Selection**: User chooses quality via inline keyboard
4. **Download**: Video downloaded with progress updates (~1s intervals)
5. **Upload**: Video uploaded to Telegram
6. **Cleanup**: Temporary files removed

### Cancellation System

- Each download has a `threading.Event` for cancellation
- Progress hook checks event every update
- User can cancel via `/cancel` command
- Admins can stop any download via `/stop_download`

## Deployment

### Heroku

```bash
heroku create your-bot-name
heroku config:set BOT_TOKEN="your_token"
heroku config:set ADMIN_IDS="your_user_id"
git push heroku main
```

### Railway

1. Create new project from GitHub repo
2. Add environment variables in settings
3. Deploy

### DigitalOcean/Linode/AWS

Use the systemd service file in `deploy/vps-systemd.service`.

## Troubleshooting

### Bot doesn't respond
- Check BOT_TOKEN is correct
- Verify bot is running: `systemctl status vdownloader` (systemd)
- Check logs: `journalctl -u vdownloader -f` (systemd)

### Download fails
- Verify FFmpeg is installed
- Check file size doesn't exceed MAX_UPLOAD_MB
- Some sites may require cookies/authentication

### Permission denied
- Ensure bot has write access to `data/` directory
- Check file permissions: `chmod -R 755 data/`

## Security & Legal

⚠️ **Important Notes:**

- **Copyright**: Respect copyright laws and terms of service
- **Public content only**: This bot downloads public content only
- **Rate limits**: Telegram has upload limits (~50MB/file for bots, ~2GB for premium)
- **Responsibility**: Use responsibly and ethically

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) file for details

## Support

- 🐛 **Issues**: Report bugs via GitHub Issues
- 💡 **Feature requests**: Open a discussion or issue
- 📖 **Documentation**: Check this README and code comments

## Acknowledgments

- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) - Telegram Bot API wrapper
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - Video download engine
- [FFmpeg](https://ffmpeg.org/) - Video processing

---

Made with ❤️ by Rahul Chauhan
