#!/bin/bash
# Start support agent with all channels (WhatsApp + Web)

echo "========================================"
echo "Starting Support Agent (All Channels)"
echo "========================================"
echo ""
echo "This will start:"
echo "  - WhatsApp channel (via bridge)"
echo "  - Web chat interface (http://localhost:8000)"
echo ""
echo "Make sure:"
echo "  1. Baileys bridge is running (cd bridge && npm run dev)"
echo "  2. Ollama/LLM service is running"
echo "  3. WhatsApp is linked (python scripts/show_qr.py)"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run the application
python -m support_agent.main_all_channels
