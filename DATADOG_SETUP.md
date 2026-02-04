# Datadog Setup Guide for VDownloader

This guide explains how to set up Datadog monitoring for the VDownloader Telegram bot.

## Overview

VDownloader includes optional integration with Datadog for:
- **Application Performance Monitoring (APM)**: Distributed tracing of downloads and format extraction
- **Custom Metrics**: Real-time metrics for downloads, errors, and performance
- **Structured Logging**: JSON logs with rich context for debugging
- **Error Tracking**: Automatic categorization and alerting

## Prerequisites

1. A Datadog account (free trial available at https://www.datadoghq.com/)
2. Docker and docker-compose installed (for container deployment)
3. Your Datadog API key from https://app.datadoghq.com/organization-settings/api-keys (if using bundled agent)

## Deployment Scenarios

Choose the scenario that matches your infrastructure:

### Scenario 1: Using Existing Datadog Agent on Server

**Use this if:** You already have Datadog agent installed and running on your server.

**Advantages:**
- No need to run additional container
- Reuse existing agent configuration
- Centralized agent management
- Lower resource usage

**Setup:**

1. Create `.env` file:
```bash
# Bot configuration
BOT_TOKEN=your_bot_token_from_botfather
ADMIN_IDS=your_telegram_user_id

# Point to your existing Datadog agent
DD_AGENT_HOST=localhost  # or IP/hostname of your Datadog agent
DD_AGENT_PORT=8125
DD_TRACE_AGENT_URL=http://localhost:8126
DD_SERVICE=vdownloader
DD_ENV=production
DD_VERSION=1.0.0
```

2. Start the bot:
```bash
docker-compose up -d
```

The bot will connect to your existing Datadog agent at the specified host.

### Scenario 2: Using Bundled Datadog Agent Container

**Use this if:** You don't have Datadog agent on your server or want isolated monitoring.

**Advantages:**
- Self-contained setup
- No system-level agent required
- Easy to manage and remove
- Good for testing/development

**Setup:**

1. Create `.env` file with your Datadog API key:
```bash
# Bot configuration
BOT_TOKEN=your_bot_token_from_botfather
ADMIN_IDS=your_telegram_user_id

# Datadog API key (required for bundled agent)
DD_API_KEY=your_datadog_api_key_here
DD_SITE=datadoghq.com  # or datadoghq.eu for EU region
DD_SERVICE=vdownloader
DD_ENV=production
DD_VERSION=1.0.0
```

2. Start both bot and Datadog agent:
```bash
docker-compose -f docker-compose.yml -f docker-compose.datadog.yml up -d
```

This starts both the bot and a containerized Datadog agent.

### Scenario 3: No Datadog (Standard Logging)

**Use this if:** You don't need Datadog monitoring or want to use a different monitoring solution.

**Setup:**

1. Create `.env` file with only bot configuration:
```bash
BOT_TOKEN=your_bot_token_from_botfather
ADMIN_IDS=your_telegram_user_id
MAX_UPLOAD_MB=1900
```

2. Start the bot:
```bash
docker-compose up -d
```

The bot will run with standard logging to stdout.

## Verification

### 3. Verify in Datadog

1. Go to https://app.datadoghq.com/apm/traces
2. Look for traces from the `vdownloader` service
3. Go to https://app.datadoghq.com/metric/explorer
4. Search for metrics starting with `vdownloader.*`

## Using with Kubernetes or Other Orchestrators

If you're deploying with Kubernetes or another orchestrator:

1. **Ensure Datadog agent is deployed** as a DaemonSet or similar
2. **Set environment variables** in your pod/container spec:
   ```yaml
   env:
     - name: DD_AGENT_HOST
       valueFrom:
         fieldRef:
           fieldPath: status.hostIP
     - name: DD_SERVICE
       value: "vdownloader"
     - name: DD_ENV
       value: "production"
   ```
3. **Enable APM** in your Datadog agent configuration
4. **Deploy the bot** with the configured environment variables

The bot will automatically discover and connect to the Datadog agent.

## Configuration Reference

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DD_SERVICE` | No | vdownloader | Service name in Datadog |
| `DD_ENV` | No | production | Environment (dev/staging/production) |
| `DD_VERSION` | No | 1.0.0 | Application version |
| `DD_AGENT_HOST` | No | localhost | Datadog agent hostname/IP |
| `DD_AGENT_PORT` | No | 8125 | DogStatsD port |
| `DD_TRACE_AGENT_URL` | No | http://localhost:8126 | APM trace agent URL |
| `DD_API_KEY` | Only for bundled agent | - | Datadog API key |
| `DD_SITE` | Only for bundled agent | datadoghq.com | Datadog site |

### Network Requirements

The bot needs network access to:
- **Port 8125/UDP** (DogStatsD) - for metrics
- **Port 8126/TCP** (APM) - for traces

If using firewall rules, ensure these ports are accessible between the bot and Datadog agent.

## Running Without Docker

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Start Datadog Agent

Option A: Docker container
```bash
docker run -d --name datadog-agent \
  -e DD_API_KEY=<YOUR_API_KEY> \
  -e DD_SITE=datadoghq.com \
  -e DD_APM_ENABLED=true \
  -e DD_APM_NON_LOCAL_TRAFFIC=true \
  -e DD_DOGSTATSD_NON_LOCAL_TRAFFIC=true \
  -v /var/run/docker.sock:/var/run/docker.sock:ro \
  -v /proc/:/host/proc/:ro \
  -v /sys/fs/cgroup/:/host/sys/fs/cgroup:ro \
  -p 8125:8125/udp \
  -p 8126:8126/tcp \
  gcr.io/datadoghq/agent:7
```

Option B: Install natively (see https://docs.datadoghq.com/agent/)

### 3. Run the Bot with Datadog

```bash
export BOT_TOKEN="your_bot_token"
export DD_SERVICE=vdownloader
export DD_ENV=production
export DD_AGENT_HOST=localhost

# Run with ddtrace
ddtrace-run python main.py
```

## Available Metrics

### Command Metrics
- `vdownloader.command.start` - Count of /start commands
- `vdownloader.user.new` - New user registrations

### Download Metrics
- `vdownloader.url.received` - URLs submitted for download
- `vdownloader.url.rejected` - URLs rejected (already downloading, banned user)
- `vdownloader.url.error` - Errors during URL processing

### Performance Metrics
- `vdownloader.extract_formats.duration` - Time to extract video formats (histogram)
- `vdownloader.extract_formats.success` - Successful format extractions
- `vdownloader.extract_formats.error` - Failed format extractions
- `vdownloader.download.duration` - Download time (histogram)
- `vdownloader.download.size` - Downloaded file size (histogram)
- `vdownloader.download.success` - Successful downloads
- `vdownloader.download.error` - Failed downloads
- `vdownloader.upload.duration` - Upload time to Telegram (histogram)
- `vdownloader.upload.success` - Successful uploads

### Stats Metrics (Gauges)
- `vdownloader.stats.total_downloads` - Total downloads counter
- `vdownloader.stats.total_bytes` - Total bytes transferred

### Admin Metrics
- `vdownloader.admin.action` - Admin actions logged

## Structured Logging

All logs include contextual information:

```json
{
  "asctime": "2024-01-01T12:00:00.000Z",
  "name": "vdownloader",
  "levelname": "INFO",
  "message": "Video downloaded successfully",
  "user_id": 12345,
  "chat_id": 12345,
  "url": "https://youtube.com/watch?v=...",
  "format_id": "best",
  "filesize_mb": 45.2,
  "duration_ms": 5432.1,
  "title": "Example Video"
}
```

## APM Traces

The following operations are automatically traced:

1. **extract_formats**: Video format extraction from URL
2. **download_video**: Video download process

Each trace includes:
- Execution time
- Success/failure status
- URL being processed
- Error details (if failed)

## Dashboards and Alerts

### Recommended Dashboards

1. **Download Performance**
   - Download duration (p50, p95, p99)
   - Upload duration
   - File sizes
   - Success rate

2. **User Activity**
   - New users over time
   - Commands per hour
   - Active downloads

3. **Errors**
   - Error rate by type
   - Failed downloads by reason
   - Top error messages

### Recommended Alerts

1. **High Error Rate**: Alert when error rate > 10%
2. **Slow Downloads**: Alert when p95 download time > 60s
3. **Service Down**: Alert when no metrics received for 5 minutes

## Troubleshooting

### Bot Runs Without Datadog Integration

This is normal! The bot has graceful degradation and will work fine without Datadog.

To enable Datadog:
1. Ensure packages are installed: `pip install ddtrace datadog python-json-logger`
2. Set `DD_API_KEY` environment variable
3. Ensure Datadog agent is running and accessible

### No Traces Appearing

Check:
1. Datadog agent is running: `docker ps | grep datadog`
2. Agent can receive traces: `docker logs datadog-agent | grep trace`
3. Environment variables are set correctly
4. Bot is using `ddtrace-run` or has `DD_TRACE_ENABLED=true`

### No Metrics Appearing

Check:
1. Datadog agent is running and accessible at `DD_AGENT_HOST:DD_AGENT_PORT`
2. Agent logs show metric reception: `docker logs datadog-agent | grep statsd`
3. Port 8125/udp is open and accessible

### JSON Logs Not Formatted Correctly

Check:
1. `python-json-logger` is installed
2. Check bot logs for "Datadog APM and logging initialized" message
3. If seeing plain text logs, Datadog packages may not be installed

## Disabling Datadog

To run without Datadog monitoring:

1. Remove or comment out `DD_API_KEY` from environment
2. Or stop the Datadog agent: `docker-compose stop datadog-agent`
3. Or start only the bot: `docker-compose up -d vdownloader`

The bot will automatically fall back to standard logging.

## Cost Considerations

Datadog pricing depends on:
- Number of hosts (agents)
- APM traces ingested
- Custom metrics sent
- Log volume

For a single bot instance:
- Estimated metrics: ~50 custom metrics
- Estimated trace volume: Low (depends on usage)
- May fit within free tier for development

See https://www.datadoghq.com/pricing/ for current pricing.

## Resources

- Datadog Documentation: https://docs.datadoghq.com/
- Python APM Guide: https://docs.datadoghq.com/tracing/setup_overview/setup/python/
- Custom Metrics Guide: https://docs.datadoghq.com/metrics/custom_metrics/
- Log Collection: https://docs.datadoghq.com/logs/log_collection/python/
