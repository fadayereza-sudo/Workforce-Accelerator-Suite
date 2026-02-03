#!/bin/bash
# Quick development helper script

echo "🚀 Workforce Accelerator - Dev Setup"
echo ""

# Check if ngrok is running
if ! curl -s http://localhost:4040/api/tunnels > /dev/null 2>&1; then
    echo "⚠️  Ngrok is not running!"
    echo ""
    echo "Please start ngrok first:"
    echo "  ngrok http 8000"
    echo ""
    exit 1
fi

# Update bot URL
echo "📱 Updating bot menu button URL..."
python3 update_bot_url.py

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Setup complete!"
    echo ""
    echo "Your dev bot is ready to use."
    echo "If the backend is already running, the changes are live."
    echo ""
else
    echo ""
    echo "❌ Setup failed. Check the errors above."
    exit 1
fi
