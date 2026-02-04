#!/bin/bash

# Initialize vdownloader repository
# This script sets up the directory structure and initializes data files

set -e

echo "Initializing vdownloader repository..."

# Create directories
mkdir -p data deploy scripts downloads temp

# Create state.json if it doesn't exist
if [ ! -f data/state.json ]; then
    echo "Creating data/state.json..."
    cat > data/state.json << 'EOF'
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
EOF
fi

# Create admin_actions.log if it doesn't exist
if [ ! -f data/admin_actions.log ]; then
    echo "Creating data/admin_actions.log..."
    cat > data/admin_actions.log << 'EOF'
# Admin actions log
# Format: [timestamp] admin_id: action
EOF
fi

echo "Repository initialized successfully!"
echo "Next steps:"
echo "1. Set BOT_TOKEN environment variable"
echo "2. (Optional) Update ADMIN_IDS or edit data/state.json"
echo "3. Run: python main.py"
