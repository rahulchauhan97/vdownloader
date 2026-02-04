#!/usr/bin/env python3
"""
vdownloader - Telegram Video Downloader Bot
Uses yt-dlp to download videos from various platforms
"""

import os
import json
import asyncio
import threading
import tempfile
import shutil
import time
import logging
import re
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

# Datadog imports
try:
    from ddtrace import tracer, patch_all
    from datadog import initialize as dd_initialize, statsd
    from pythonjsonlogger import jsonlogger
    DATADOG_ENABLED = True
except ImportError:
    DATADOG_ENABLED = False
    tracer = None
    statsd = None

# Configure logging
logger = logging.getLogger(__name__)

# Initialize Datadog if enabled
DD_SERVICE = os.getenv('DD_SERVICE', 'vdownloader')
DD_ENV = os.getenv('DD_ENV', 'production')
DD_VERSION = os.getenv('DD_VERSION', '1.0.0')
# DD_AGENT_HOST can be:
# - 'localhost' for local agent or when running directly on host
# - 'datadog-agent' for bundled agent container (docker-compose)
# - IP address or hostname of existing Datadog agent
# - 'host.docker.internal' for Docker Desktop on Mac/Windows to reach host
DD_AGENT_HOST = os.getenv('DD_AGENT_HOST', 'localhost')
DD_AGENT_PORT = int(os.getenv('DD_AGENT_PORT', '8125'))

if DATADOG_ENABLED:
    # Initialize Datadog APM
    patch_all()
    
    # Initialize Datadog StatsD client
    dd_options = {
        'statsd_host': DD_AGENT_HOST,
        'statsd_port': DD_AGENT_PORT,
    }
    dd_initialize(**dd_options)
    
    # Configure JSON logging for Datadog
    logHandler = logging.StreamHandler()
    formatter = jsonlogger.JsonFormatter(
        '%(asctime)s %(name)s %(levelname)s %(message)s',
        timestamp=True
    )
    logHandler.setFormatter(formatter)
    
    # Set up root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(logHandler)
    
    logger.info("Datadog APM and logging initialized", extra={
        'dd.service': DD_SERVICE,
        'dd.env': DD_ENV,
        'dd.version': DD_VERSION
    })
else:
    # Fallback to basic logging if Datadog is not available
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    logger.warning("Datadog not available, using basic logging")

# Configuration from environment
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_IDS_ENV = os.getenv('ADMIN_IDS', '')
MAX_UPLOAD_MB = int(os.getenv('MAX_UPLOAD_MB', 1900))

# User-Agent for better compatibility with video platforms
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'

# Global state
state_lock = asyncio.Lock()
active_downloads = {}  # chat_id -> download_info
executor = ThreadPoolExecutor(max_workers=5)

# Ensure data directory exists
Path('data').mkdir(exist_ok=True)


async def load_state():
    """Load state from JSON file with async locking"""
    async with state_lock:
        try:
            # Using sync I/O is acceptable here for simplicity since state file is small
            with open('data/state.json', 'r') as f:
                state = json.load(f)
        except FileNotFoundError:
            # Initialize with admin IDs from environment
            admin_ids = []
            if ADMIN_IDS_ENV:
                admin_ids = [int(x.strip()) for x in ADMIN_IDS_ENV.split(',') if x.strip()]
            
            state = {
                'admins': admin_ids if admin_ids else [360013457],
                'bans': [],
                'settings': {'max_upload_mb': MAX_UPLOAD_MB},
                'users': {},
                'stats': {'downloads': 0, 'bytes': 0}
            }
            # Save initial state
            with open('data/state.json', 'w') as f:
                json.dump(state, f, indent=2)
        
        return state


async def save_state(state):
    """Save state to JSON file with async locking"""
    async with state_lock:
        # Using sync I/O is acceptable here for simplicity since state file is small
        with open('data/state.json', 'w') as f:
            json.dump(state, f, indent=2)


def log_admin_action(admin_id, action):
    """Log admin action to file (synchronous, called from async contexts)"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        with open('data/admin_actions.log', 'a') as f:
            f.write(f"[{timestamp}] {admin_id}: {action}\n")
        
        # Send metric to Datadog
        if DATADOG_ENABLED and statsd:
            statsd.increment('vdownloader.admin.action', tags=[f'action:{action}'])
            
        logger.info("Admin action logged", extra={
            'admin_id': admin_id,
            'action': action
        })
    except Exception as e:
        logger.error(f"Failed to log admin action: {e}", extra={
            'admin_id': admin_id,
            'action': action,
            'error': str(e)
        })


def send_metric(metric_name, value=1, metric_type='increment', tags=None):
    """Send metric to Datadog if enabled"""
    if not DATADOG_ENABLED or not statsd:
        return
    
    try:
        if tags is None:
            tags = []
        
        # Add default tags
        tags.extend([
            f'service:{DD_SERVICE}',
            f'env:{DD_ENV}',
            f'version:{DD_VERSION}'
        ])
        
        if metric_type == 'increment':
            statsd.increment(metric_name, value=value, tags=tags)
        elif metric_type == 'gauge':
            statsd.gauge(metric_name, value, tags=tags)
        elif metric_type == 'histogram':
            statsd.histogram(metric_name, value, tags=tags)
        elif metric_type == 'timing':
            statsd.timing(metric_name, value, tags=tags)
    except Exception as e:
        logger.warning(f"Failed to send metric {metric_name}: {e}")


def is_admin(user_id, state):
    """Check if user is admin"""
    return user_id in state['admins']


def is_banned(user_id, state):
    """Check if user is banned"""
    return user_id in state['bans']


def is_url(text):
    """
    Check if text contains a URL.
    
    Supports http://, https://, www. prefixes and domain patterns.
    Performs case-insensitive matching.
    
    Args:
        text: Input text to check
        
    Returns:
        True if text appears to contain a URL, False otherwise
    """
    # Pattern to match common URL formats
    url_pattern = re.compile(
        r'(?:https?://|'  # http:// or https://
        r'(?:^|\s)www\.)'  # www. at start or after whitespace
        r'[\w\-\.]+\.\w+',  # domain.tld
        re.IGNORECASE
    )
    return bool(url_pattern.search(text))


def is_greeting(text):
    """
    Check if text is a common greeting.
    
    Strips whitespace and performs case-insensitive exact matching
    against a predefined set of greetings including: hi, hello, hey,
    hola, howdy, greetings, good morning, good afternoon, good evening,
    sup, yo, hii, heya, hiya.
    
    Args:
        text: Input text to check
        
    Returns:
        True if text matches a known greeting, False otherwise
    """
    greetings = {
        'hi', 'hello', 'hey', 'hola', 'howdy', 'greetings',
        'good morning', 'good afternoon', 'good evening',
        'sup', 'yo', 'hii', 'heya', 'hiya'
    }
    text_lower = text.lower().strip()
    return text_lower in greetings


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user_id = update.effective_user.id
    state = await load_state()
    
    # Send metric
    send_metric('vdownloader.command.start', tags=['command:start'])
    
    if is_banned(user_id, state):
        logger.warning("Banned user tried to access bot", extra={
            'user_id': user_id,
            'command': 'start'
        })
        await update.message.reply_text("You are banned from using this bot.")
        return
    
    # Track user
    is_new_user = str(user_id) not in state['users']
    if is_new_user:
        state['users'][str(user_id)] = {
            'first_seen': datetime.now().isoformat(),
            'username': update.effective_user.username or ''
        }
        await save_state(state)
        
        # Send metric for new user
        send_metric('vdownloader.user.new', tags=['event:new_user'])
        logger.info("New user registered", extra={
            'user_id': user_id,
            'username': update.effective_user.username
        })
    
    welcome_text = (
        "🎥 Welcome to VDownloader Bot!\n\n"
        "Send me a video URL from YouTube, Instagram, TikTok, Twitter/X, or other supported sites.\n\n"
        "Commands:\n"
        "/start - Show this message\n"
        "/cancel - Cancel current download\n"
        "/help - Show help\n"
    )
    
    if is_admin(user_id, state):
        welcome_text += "\nAdmin commands: /admin_list, /ban, /unban, /stats, /broadcast, /shutdown"
    
    await update.message.reply_text(welcome_text)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_text = (
        "📚 How to use:\n\n"
        "1. Send me a video URL\n"
        "2. Choose format/quality from the list\n"
        "3. Wait for download and upload\n"
        "4. Use /cancel to stop download\n\n"
        "Supported sites: YouTube, Instagram, TikTok, Twitter/X, and 1000+ more!"
    )
    await update.message.reply_text(help_text)


def extract_formats(url):
    """Extract available formats from URL using yt-dlp"""
    start_time = time.time()
    
    # Add span for tracing
    if DATADOG_ENABLED and tracer:
        with tracer.trace("extract_formats", service=DD_SERVICE) as span:
            span.set_tag("url", url)
            result = _extract_formats_impl(url, start_time)
            span.set_tag("success", result is not None)
            return result
    else:
        return _extract_formats_impl(url, start_time)


def _extract_formats_impl(url, start_time):
    """Implementation of format extraction"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'socket_timeout': 30,
        'http_chunk_size': 10485760,  # 10MB chunks
        'user_agent': USER_AGENT,
        # Instagram specific options
        'http_headers': {
            'User-Agent': USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-us,en;q=0.5',
            'Sec-Fetch-Mode': 'navigate',
        }
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = info.get('formats', [])
            
            # Filter and sort formats
            video_formats = []
            for f in formats:
                if f.get('vcodec') != 'none' and f.get('filesize'):
                    video_formats.append({
                        'format_id': f['format_id'],
                        'ext': f.get('ext', 'mp4'),
                        'quality': f.get('format_note', 'unknown'),
                        'filesize': f.get('filesize', 0),
                        'resolution': f.get('resolution', 'unknown')
                    })
            
            # Sort by filesize
            video_formats.sort(key=lambda x: x['filesize'], reverse=True)
            
            # Send metrics
            duration = (time.time() - start_time) * 1000  # Convert to milliseconds
            send_metric('vdownloader.extract_formats.duration', value=duration, metric_type='histogram')
            send_metric('vdownloader.extract_formats.success', tags=['status:success'])
            
            logger.info("Formats extracted successfully", extra={
                'url': url,
                'format_count': len(video_formats),
                'duration_ms': duration
            })
            
            return {
                'title': info.get('title', 'video'),
                'formats': video_formats[:10]  # Limit to 10 formats
            }
    except Exception as e:
        duration = (time.time() - start_time) * 1000
        send_metric('vdownloader.extract_formats.duration', value=duration, metric_type='histogram')
        send_metric('vdownloader.extract_formats.error', tags=['status:error', f'error_type:{type(e).__name__}'])
        
        logger.error("Error extracting formats", extra={
            'url': url,
            'error': str(e),
            'error_type': type(e).__name__,
            'duration_ms': duration
        })
        return None


async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle video URL messages"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    state = await load_state()
    
    if is_banned(user_id, state):
        logger.warning("Banned user tried to download", extra={
            'user_id': user_id,
            'event': 'url_received'
        })
        await update.message.reply_text("You are banned from using this bot.")
        return
    
    text = update.message.text.strip()
    
    # Check if message is a greeting
    if is_greeting(text):
        await update.message.reply_text(
            "👋 Hello! Send me a video URL from YouTube, Instagram, TikTok, Twitter/X, or other supported sites to download."
        )
        return
    
    # Check if message is a URL
    if not is_url(text):
        await update.message.reply_text(
            "Please send a valid video URL. Use /help for more information."
        )
        return
    
    url = text
    
    # Send metric
    send_metric('vdownloader.url.received', tags=['event:url_received'])
    
    logger.info("URL received for processing", extra={
        'user_id': user_id,
        'chat_id': chat_id,
        'url': url
    })
    
    # Check if already downloading
    if chat_id in active_downloads:
        send_metric('vdownloader.url.rejected', tags=['reason:already_downloading'])
        await update.message.reply_text("You already have an active download. Use /cancel to stop it first.")
        return
    
    # Send processing message
    msg = await update.message.reply_text("🔍 Analyzing video...")
    
    # Extract formats in executor
    loop = asyncio.get_event_loop()
    try:
        info = await loop.run_in_executor(executor, extract_formats, url)
    except Exception as e:
        send_metric('vdownloader.url.error', tags=['stage:extract', f'error_type:{type(e).__name__}'])
        logger.error("Error during format extraction", extra={
            'user_id': user_id,
            'url': url,
            'error': str(e),
            'error_type': type(e).__name__
        })
        await msg.edit_text(f"❌ Error: {str(e)}")
        return
    
    if not info or not info['formats']:
        send_metric('vdownloader.url.error', tags=['stage:extract', 'reason:no_formats'])
        logger.warning("No formats found for URL", extra={
            'user_id': user_id,
            'url': url
        })
        await msg.edit_text("❌ No formats found or unsupported URL.")
        return
    
    # Create inline keyboard with format options
    keyboard = []
    
    # Add best option
    keyboard.append([InlineKeyboardButton("⭐ Best Quality", callback_data=f"dl:best:{url}")])
    
    # Add format options
    for fmt in info['formats'][:9]:  # Limit to 9 + best = 10 total
        size_mb = fmt['filesize'] / (1024 * 1024)
        label = f"{fmt['resolution']} ({fmt['quality']}) - {size_mb:.1f}MB"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"dl:{fmt['format_id']}:{url}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await msg.edit_text(
        f"📹 *{info['title']}*\n\nSelect format/quality:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def handle_format_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle format selection callback"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    state = await load_state()
    
    if is_banned(user_id, state):
        await query.message.edit_text("You are banned from using this bot.")
        return
    
    # Parse callback data
    parts = query.data.split(':', 2)
    if len(parts) != 3 or parts[0] != 'dl':
        return
    
    format_id = parts[1]
    url = parts[2]
    
    # Check if already downloading
    if chat_id in active_downloads:
        await query.message.edit_text("You already have an active download. Use /cancel to stop it first.")
        return
    
    # Start download
    await query.message.edit_text("📥 Starting download...")
    
    # Create cancellation event
    cancel_event = threading.Event()
    
    # Store download info
    active_downloads[chat_id] = {
        'cancel_event': cancel_event,
        'url': url,
        'format_id': format_id,
        'started_at': time.time(),
        'message_id': query.message.message_id
    }
    
    # Download in executor
    loop = asyncio.get_event_loop()
    
    try:
        result = await loop.run_in_executor(
            executor,
            download_video,
            url,
            format_id,
            cancel_event,
            chat_id,
            context.bot,
            query.message.message_id,
            state['settings']['max_upload_mb']
        )
        
        if result['success']:
            # Upload file
            upload_start = time.time()
            await query.message.edit_text("📤 Uploading...")
            
            with open(result['file_path'], 'rb') as f:
                await context.bot.send_video(
                    chat_id=chat_id,
                    video=f,
                    caption=result['title'],
                    supports_streaming=True
                )
            
            upload_duration = (time.time() - upload_start) * 1000
            
            # Send metrics
            send_metric('vdownloader.upload.duration', value=upload_duration, metric_type='histogram')
            send_metric('vdownloader.upload.success', tags=['status:success'])
            send_metric('vdownloader.video.complete', tags=['status:success'])
            
            await query.message.edit_text("✅ Download complete!")
            
            logger.info("Video uploaded successfully", extra={
                'user_id': user_id,
                'chat_id': chat_id,
                'filesize': result['filesize'],
                'upload_duration_ms': upload_duration,
                'title': result['title']
            })
            
            # Update stats
            state['stats']['downloads'] += 1
            state['stats']['bytes'] += result['filesize']
            await save_state(state)
            
            # Update gauge metrics
            send_metric('vdownloader.stats.total_downloads', value=state['stats']['downloads'], metric_type='gauge')
            send_metric('vdownloader.stats.total_bytes', value=state['stats']['bytes'], metric_type='gauge')
            
            # Cleanup
            try:
                os.remove(result['file_path'])
                if result.get('temp_dir'):
                    shutil.rmtree(result['temp_dir'], ignore_errors=True)
            except Exception as e:
                logger.warning(f"Cleanup error: {e}")
        else:
            await query.message.edit_text(f"❌ {result['error']}")
    
    except Exception as e:
        logger.error(f"Download error: {e}")
        await query.message.edit_text(f"❌ Error: {str(e)}")
    
    finally:
        # Remove from active downloads
        if chat_id in active_downloads:
            del active_downloads[chat_id]


def download_video(url, format_id, cancel_event, chat_id, bot, message_id, max_upload_mb):
    """Download video using yt-dlp (runs in thread)"""
    start_time = time.time()
    temp_dir = tempfile.mkdtemp()
    last_update = [0]  # Mutable for closure
    
    # Add tracing if Datadog is enabled
    if DATADOG_ENABLED and tracer:
        with tracer.trace("download_video", service=DD_SERVICE) as span:
            span.set_tag("url", url)
            span.set_tag("format_id", format_id)
            span.set_tag("chat_id", chat_id)
            result = _download_video_impl(url, format_id, cancel_event, temp_dir, max_upload_mb, start_time)
            span.set_tag("success", result.get('success', False))
            if not result.get('success'):
                span.set_tag("error", result.get('error', 'unknown'))
            return result
    else:
        return _download_video_impl(url, format_id, cancel_event, temp_dir, max_upload_mb, start_time)


def _download_video_impl(url, format_id, cancel_event, temp_dir, max_upload_mb, start_time):
    """Implementation of video download"""
    
    # Note: Progress updates from thread are best-effort only
    # Due to thread safety concerns with asyncio, we skip live progress updates
    # The download will complete silently and then upload
    
    def progress_hook(d):
        # Check cancellation
        if cancel_event.is_set():
            raise Exception("Download cancelled by user")
    
    ydl_opts = {
        'format': format_id if format_id != 'best' else 'bestvideo+bestaudio/best',
        'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
        'progress_hooks': [progress_hook],
        'merge_output_format': 'mp4',
        'quiet': True,
        'no_warnings': True,
        'socket_timeout': 30,
        'http_chunk_size': 10485760,  # 10MB chunks to prevent 413 errors
        'fragment_retries': 5,
        'skip_unavailable_fragments': True,
        'user_agent': USER_AGENT,
        'http_headers': {
            'User-Agent': USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-us,en;q=0.5',
            'Sec-Fetch-Mode': 'navigate',
        },
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            
            # Find downloaded file
            filename = ydl.prepare_filename(info)
            
            # Check file size
            filesize = os.path.getsize(filename)
            filesize_mb = filesize / (1024 * 1024)
            
            # Send metrics
            duration = (time.time() - start_time) * 1000
            send_metric('vdownloader.download.duration', value=duration, metric_type='histogram', 
                       tags=[f'format:{format_id}'])
            send_metric('vdownloader.download.size', value=filesize, metric_type='histogram')
            
            if filesize_mb > max_upload_mb:
                send_metric('vdownloader.download.error', tags=['reason:file_too_large'])
                logger.warning("Downloaded file too large", extra={
                    'url': url,
                    'filesize_mb': filesize_mb,
                    'max_upload_mb': max_upload_mb,
                    'duration_ms': duration
                })
                return {
                    'success': False,
                    'error': f'File too large ({filesize_mb:.1f}MB > {max_upload_mb}MB)'
                }
            
            send_metric('vdownloader.download.success', tags=['status:success'])
            logger.info("Video downloaded successfully", extra={
                'url': url,
                'format_id': format_id,
                'filesize_mb': filesize_mb,
                'duration_ms': duration,
                'title': info.get('title', 'video')
            })
            
            return {
                'success': True,
                'file_path': filename,
                'temp_dir': temp_dir,
                'title': info.get('title', 'video'),
                'filesize': filesize
            }
    
    except Exception as e:
        duration = (time.time() - start_time) * 1000
        send_metric('vdownloader.download.duration', value=duration, metric_type='histogram',
                   tags=[f'format:{format_id}', 'status:error'])
        send_metric('vdownloader.download.error', tags=[f'error_type:{type(e).__name__}'])
        
        logger.error("Video download failed", extra={
            'url': url,
            'format_id': format_id,
            'error': str(e),
            'error_type': type(e).__name__,
            'duration_ms': duration
        })
        
        shutil.rmtree(temp_dir, ignore_errors=True)
        return {
            'success': False,
            'error': str(e)
        }


async def cancel_download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /cancel command"""
    chat_id = update.effective_chat.id
    
    if chat_id not in active_downloads:
        await update.message.reply_text("No active download to cancel.")
        return
    
    # Set cancel event
    active_downloads[chat_id]['cancel_event'].set()
    await update.message.reply_text("🛑 Cancelling download...")


# Admin Commands

async def admin_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /admin_add command"""
    user_id = update.effective_user.id
    state = await load_state()
    
    if not is_admin(user_id, state):
        await update.message.reply_text("❌ Admin only command.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /admin_add <user_id>")
        return
    
    try:
        new_admin_id = int(context.args[0])
        if new_admin_id not in state['admins']:
            state['admins'].append(new_admin_id)
            await save_state(state)
            log_admin_action(user_id, f"Added admin {new_admin_id}")
            await update.message.reply_text(f"✅ User {new_admin_id} added as admin.")
        else:
            await update.message.reply_text(f"User {new_admin_id} is already an admin.")
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID.")


async def admin_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /admin_remove command"""
    user_id = update.effective_user.id
    state = await load_state()
    
    if not is_admin(user_id, state):
        await update.message.reply_text("❌ Admin only command.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /admin_remove <user_id>")
        return
    
    try:
        admin_id = int(context.args[0])
        if admin_id in state['admins']:
            state['admins'].remove(admin_id)
            await save_state(state)
            log_admin_action(user_id, f"Removed admin {admin_id}")
            await update.message.reply_text(f"✅ User {admin_id} removed from admins.")
        else:
            await update.message.reply_text(f"User {admin_id} is not an admin.")
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID.")


async def admin_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /admin_list command"""
    user_id = update.effective_user.id
    state = await load_state()
    
    if not is_admin(user_id, state):
        await update.message.reply_text("❌ Admin only command.")
        return
    
    admins = ', '.join(map(str, state['admins']))
    await update.message.reply_text(f"👥 Admins: {admins}")


async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /ban command"""
    user_id = update.effective_user.id
    state = await load_state()
    
    if not is_admin(user_id, state):
        await update.message.reply_text("❌ Admin only command.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /ban <user_id>")
        return
    
    try:
        ban_id = int(context.args[0])
        if ban_id not in state['bans']:
            state['bans'].append(ban_id)
            await save_state(state)
            log_admin_action(user_id, f"Banned user {ban_id}")
            await update.message.reply_text(f"✅ User {ban_id} banned.")
        else:
            await update.message.reply_text(f"User {ban_id} is already banned.")
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID.")


async def unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /unban command"""
    user_id = update.effective_user.id
    state = await load_state()
    
    if not is_admin(user_id, state):
        await update.message.reply_text("❌ Admin only command.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /unban <user_id>")
        return
    
    try:
        unban_id = int(context.args[0])
        if unban_id in state['bans']:
            state['bans'].remove(unban_id)
            await save_state(state)
            log_admin_action(user_id, f"Unbanned user {unban_id}")
            await update.message.reply_text(f"✅ User {unban_id} unbanned.")
        else:
            await update.message.reply_text(f"User {unban_id} is not banned.")
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID.")


async def bans_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /bans command"""
    user_id = update.effective_user.id
    state = await load_state()
    
    if not is_admin(user_id, state):
        await update.message.reply_text("❌ Admin only command.")
        return
    
    if not state['bans']:
        await update.message.reply_text("No banned users.")
    else:
        bans = ', '.join(map(str, state['bans']))
        await update.message.reply_text(f"🚫 Banned users: {bans}")


async def active_downloads_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /active_downloads command"""
    user_id = update.effective_user.id
    state = await load_state()
    
    if not is_admin(user_id, state):
        await update.message.reply_text("❌ Admin only command.")
        return
    
    if not active_downloads:
        await update.message.reply_text("No active downloads.")
    else:
        text = "📊 Active downloads:\n\n"
        for chat_id, info in active_downloads.items():
            elapsed = int(time.time() - info['started_at'])
            text += f"Chat {chat_id}: {elapsed}s\n"
        await update.message.reply_text(text)


async def stop_download_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stop_download command"""
    user_id = update.effective_user.id
    state = await load_state()
    
    if not is_admin(user_id, state):
        await update.message.reply_text("❌ Admin only command.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /stop_download <chat_id>")
        return
    
    try:
        chat_id = int(context.args[0])
        if chat_id in active_downloads:
            active_downloads[chat_id]['cancel_event'].set()
            log_admin_action(user_id, f"Stopped download for chat {chat_id}")
            await update.message.reply_text(f"✅ Download for chat {chat_id} cancelled.")
        else:
            await update.message.reply_text(f"No active download for chat {chat_id}.")
    except ValueError:
        await update.message.reply_text("❌ Invalid chat ID.")


async def set_max_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /set_max_upload command"""
    user_id = update.effective_user.id
    state = await load_state()
    
    if not is_admin(user_id, state):
        await update.message.reply_text("❌ Admin only command.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /set_max_upload <MB>")
        return
    
    try:
        max_mb = int(context.args[0])
        state['settings']['max_upload_mb'] = max_mb
        await save_state(state)
        log_admin_action(user_id, f"Set max upload to {max_mb}MB")
        await update.message.reply_text(f"✅ Max upload size set to {max_mb}MB.")
    except ValueError:
        await update.message.reply_text("❌ Invalid number.")


async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats command"""
    user_id = update.effective_user.id
    state = await load_state()
    
    if not is_admin(user_id, state):
        await update.message.reply_text("❌ Admin only command.")
        return
    
    total_users = len(state['users'])
    total_downloads = state['stats']['downloads']
    total_bytes = state['stats']['bytes']
    total_gb = total_bytes / (1024 ** 3)
    
    text = (
        f"📊 Bot Statistics:\n\n"
        f"👥 Total users: {total_users}\n"
        f"📥 Total downloads: {total_downloads}\n"
        f"💾 Total data: {total_gb:.2f} GB\n"
        f"🔒 Admins: {len(state['admins'])}\n"
        f"🚫 Bans: {len(state['bans'])}\n"
        f"⚡ Active downloads: {len(active_downloads)}"
    )
    await update.message.reply_text(text)


async def broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /broadcast command"""
    user_id = update.effective_user.id
    state = await load_state()
    
    if not is_admin(user_id, state):
        await update.message.reply_text("❌ Admin only command.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /broadcast <message>")
        return
    
    message = ' '.join(context.args)
    
    # Store broadcast data in context
    context.user_data['broadcast_message'] = message
    
    # Ask for confirmation
    keyboard = [
        [
            InlineKeyboardButton("✅ Confirm", callback_data="broadcast:confirm"),
            InlineKeyboardButton("❌ Cancel", callback_data="broadcast:cancel")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"📢 Broadcast to {len(state['users'])} users?\n\nMessage:\n{message}",
        reply_markup=reply_markup
    )


async def broadcast_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle broadcast confirmation callback"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    state = await load_state()
    
    if not is_admin(user_id, state):
        await query.message.edit_text("❌ Admin only command.")
        return
    
    action = query.data.split(':')[1]
    
    if action == 'cancel':
        await query.message.edit_text("❌ Broadcast cancelled.")
        return
    
    message = context.user_data.get('broadcast_message')
    if not message:
        await query.message.edit_text("❌ No message found.")
        return
    
    await query.message.edit_text("📢 Broadcasting...")
    
    sent = 0
    failed = 0
    
    for chat_id in state['users'].keys():
        try:
            await context.bot.send_message(chat_id=int(chat_id), text=message)
            sent += 1
        except Exception as e:
            logger.debug(f"Failed to send to {chat_id}: {e}")
            failed += 1
        
        # Small delay to avoid rate limits
        await asyncio.sleep(0.05)
    
    log_admin_action(user_id, f"Broadcast to {sent} users")
    await query.message.edit_text(f"✅ Broadcast complete!\nSent: {sent}\nFailed: {failed}")


async def shutdown_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /shutdown command"""
    user_id = update.effective_user.id
    state = await load_state()
    
    if not is_admin(user_id, state):
        await update.message.reply_text("❌ Admin only command.")
        return
    
    # Ask for confirmation
    keyboard = [
        [
            InlineKeyboardButton("✅ Confirm Shutdown", callback_data="shutdown:confirm"),
            InlineKeyboardButton("❌ Cancel", callback_data="shutdown:cancel")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "⚠️ Are you sure you want to shutdown the bot?",
        reply_markup=reply_markup
    )


async def shutdown_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle shutdown confirmation callback"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    state = await load_state()
    
    if not is_admin(user_id, state):
        await query.message.edit_text("❌ Admin only command.")
        return
    
    action = query.data.split(':')[1]
    
    if action == 'cancel':
        await query.message.edit_text("❌ Shutdown cancelled.")
        return
    
    log_admin_action(user_id, "Initiated shutdown")
    await query.message.edit_text("🛑 Shutting down bot...")
    
    # Stop application
    asyncio.create_task(stop_application(context.application))


async def stop_application(application):
    """Stop the bot application"""
    await asyncio.sleep(1)
    await application.stop()
    await application.shutdown()


def main():
    """Main function"""
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN environment variable not set!")
        return
    
    # Create application
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # Command handlers
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(CommandHandler('cancel', cancel_download))
    
    # Admin commands
    application.add_handler(CommandHandler('admin_add', admin_add))
    application.add_handler(CommandHandler('admin_remove', admin_remove))
    application.add_handler(CommandHandler('admin_list', admin_list))
    application.add_handler(CommandHandler('ban', ban_user))
    application.add_handler(CommandHandler('unban', unban_user))
    application.add_handler(CommandHandler('bans', bans_list))
    application.add_handler(CommandHandler('active_downloads', active_downloads_cmd))
    application.add_handler(CommandHandler('stop_download', stop_download_cmd))
    application.add_handler(CommandHandler('set_max_upload', set_max_upload))
    application.add_handler(CommandHandler('stats', stats_cmd))
    application.add_handler(CommandHandler('broadcast', broadcast_cmd))
    application.add_handler(CommandHandler('shutdown', shutdown_cmd))
    
    # Callback handlers
    application.add_handler(CallbackQueryHandler(handle_format_selection, pattern=r'^dl:'))
    application.add_handler(CallbackQueryHandler(broadcast_callback, pattern=r'^broadcast:'))
    application.add_handler(CallbackQueryHandler(shutdown_callback, pattern=r'^shutdown:'))
    
    # URL handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    
    # Start bot
    logger.info("Starting bot...")
    application.run_polling()


if __name__ == '__main__':
    main()