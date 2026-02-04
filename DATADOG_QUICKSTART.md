# Datadog Configuration Quick Reference

## TL;DR - Choose Your Scenario

### 1. Already have Datadog agent on server? ✅ RECOMMENDED
```bash
# .env file
BOT_TOKEN=your_token
DD_AGENT_HOST=localhost  # or your agent's IP/hostname
DD_SERVICE=vdownloader

# Start
docker-compose up -d
```

### 2. Want bundled Datadog agent container?
```bash
# .env file
BOT_TOKEN=your_token
DD_API_KEY=your_datadog_api_key
DD_AGENT_HOST=datadog-agent

# Start with agent
docker-compose -f docker-compose.yml -f docker-compose.datadog.yml up -d
```

### 3. No Datadog needed?
```bash
# .env file (only bot config)
BOT_TOKEN=your_token

# Start
docker-compose up -d
```

## Common DD_AGENT_HOST Values

| Environment | DD_AGENT_HOST Value | Use Case |
|------------|---------------------|----------|
| Existing server agent | `localhost` | Datadog agent installed on same server |
| Existing server agent (containerized bot) | Host IP or `host.docker.internal` | Bot in container, agent on host |
| Bundled agent container | `datadog-agent` | Using docker-compose.datadog.yml |
| Kubernetes | `status.hostIP` | DaemonSet agent on each node |
| Remote agent | IP or hostname | Centralized agent on different server |

## Port Requirements

- **8125/UDP**: DogStatsD (metrics)
- **8126/TCP**: APM Trace Agent (traces)

## Verification Commands

```bash
# Check if bot can reach agent (from inside bot container)
docker exec vdownloader nc -zv $DD_AGENT_HOST 8125

# Check agent logs (if using bundled agent)
docker logs datadog-agent | grep -i "listening"

# Check bot logs for Datadog initialization
docker logs vdownloader | grep -i datadog
```

## Troubleshooting

### Bot can't connect to agent
```bash
# Check agent is running
docker ps | grep datadog
# or
systemctl status datadog-agent

# Check network connectivity
docker exec vdownloader ping -c 3 $DD_AGENT_HOST

# Check firewall allows ports 8125 and 8126
```

### No metrics appearing in Datadog
1. Verify DD_AGENT_HOST is correct
2. Check agent can receive metrics: `docker logs datadog-agent | grep statsd`
3. Ensure bot has DATADOG_ENABLED=true (check logs)

### No traces appearing in Datadog
1. Verify DD_TRACE_AGENT_URL is correct
2. Check APM is enabled on agent: `docker logs datadog-agent | grep apm`
3. Ensure ddtrace package is installed

## See Also

- [DATADOG_SETUP.md](DATADOG_SETUP.md) - Full setup guide with detailed instructions
- [README.md](README.md) - General bot documentation
- [.env.example](.env.example) - Environment variable template
