# Support Agent

AI-powered support agent for server infrastructure with **multi-channel support**. Receive queries via **WhatsApp** (text or voice) or **Web Chat**, powered by local LLMs with extensible tool support for server management tasks.

## 🌟 Features

- **Multi-Channel Support**: WhatsApp + Web Chat Interface
- **WhatsApp Integration**: Receive and respond to messages via WhatsApp (device linking via QR code)
- **Web Chat UI**: Browser-based chat interface with real-time responses
- **Voice Support**: Automatic transcription of voice messages using Whisper (WhatsApp only)
- **LLM Powered**: Support for Ollama (local) and OpenAI-compatible APIs
- **Knowledge Base**: Customizable permanent memory system for the LLM
- **Tool System**: Extensible tools for server SSH access, database queries, and custom operations
- **Contact Whitelist**: Security through contact authorization (WhatsApp)
- **Per-Channel Contexts**: Separate conversation histories for each channel

## 📐 Architecture

```
┌─────────────────┐         ┌──────────────────┐
│   WhatsApp      │         │   Web Browser    │
│   (Mobile)      │         │   (Desktop)      │
└────────┬────────┘         └────────┬─────────┘
         │                           │
         ▼                           ▼
┌─────────────────┐         ┌──────────────────┐
│ Baileys Bridge  │         │  FastAPI Server  │
│   (Node.js)     │         │   + WebSocket    │
└────────┬────────┘         └────────┬─────────┘
         │                           │
         └───────────┬───────────────┘
                     ▼
         ┌───────────────────────┐
         │   Support Agent Core  │
         │                       │
         │ • Knowledge Base      │
         │ • LLM (Ollama/OpenAI) │
         │ • Tool System         │
         │ • Voice Transcription │
         │ • Per-Channel Context │
         └───────────────────────┘
```

## 🔧 Prerequisites

### System Requirements
- Python 3.10 or higher
- Node.js 18 or higher
- ffmpeg (for voice processing)

### Services
- **Ollama** (recommended for local LLM) OR OpenAI-compatible API
- WhatsApp account (for WhatsApp channel only)

## 📥 Installation

### 1. Clone and Setup

```bash
cd support-agent
```

### 2. Install Python Dependencies

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e .
```

### 3. Install Node.js Dependencies (For WhatsApp Bridge)

Use latest node version greater than 20.

```bash
cd bridge
npm install
cd ..
```

### 4. Install ffmpeg (For Voice Processing)

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt-get install ffmpeg

# Windows
# Download from https://ffmpeg.org/download.html
```

### 5. Install Ollama (Recommended for Local LLM)

Below steps are for installing ollama in MacOS/Linux.
For linux you can also install it using HomeBrew.
For Windows, you can download it from [ollama website](https://ollama.com/)

```bash
# macOS/Linux
curl -fsSL https://ollama.com/install.sh | sh

# Pull a model
ollama pull glm-4.7-flash:latest
```

## ⚙️ Configuration

### 1. Create Environment File

```bash
cp .env.example .env
```

Edit `.env`:

```bash
# Baileys Bridge (for WhatsApp)
BRIDGE_URL=http://localhost:3000

# LLM Configuration
LLM_PROVIDER=ollama
LLM_MODEL=glm-4.7-flash:latest
LLM_BASE_URL=http://localhost:11434

# Whisper Configuration (for voice messages)
WHISPER_MODEL=base
WHISPER_DEVICE=cpu

# Logging
LOG_LEVEL=INFO
```

### 2. Configure Knowledge Base

Edit `config/knowledge.md` to customize the LLM's permanent memory:
- Add your server details
- Define common procedures
- Customize response templates
- Add specific instructions

Example:
```markdown
## Custom Instructions

- Production servers: server1.example.com, server2.example.com
- Database: PostgreSQL on db.example.com
- Common restart command: sudo systemctl restart my-server-app
- Log location: /var/log/my-server-app/
```

### 3. Configure Settings

Make a copy of `config/settings-template.yaml` to `config/settings.yaml`

Edit `config/settings.yaml` to set 

- Tool configurations
- Jump server and database server access details
- Custom system prompts

## 🚀 Running the Application

### Option 1: All Channels (WhatsApp + Web) - Recommended

This runs both WhatsApp and Web chat simultaneously.

#### Step 1: Start Baileys Bridge (WhatsApp)

In **Terminal 1**:
```bash
cd bridge
npm run dev
```

You should see: `WhatsApp Bridge server running on port 3000`

#### Step 2: Link WhatsApp Account

Use python 3.x

In **Terminal 2**:
```bash
source venv/bin/activate
python scripts/show_qr.py
```

This will:
1. Generate and display a QR code
2. Open the QR code image automatically
3. Wait for you to scan it

To scan:
1. Open WhatsApp on your phone
2. Go to **Settings → Linked Devices**
3. Tap **Link a Device**
4. Scan the QR code

#### Step 3: Add WhatsApp Contacts to Whitelist

```bash
# Send a test message from your WhatsApp first
# Then check the logs to see your identifier (e.g., 125438848454740@lid)

python scripts/add_contact.py 'YOUR_IDENTIFIER_HERE'

# Examples:
python scripts/add_contact.py '125438848454740@lid'
```

**Note**: Use the **exact identifier** shown in the logs. WhatsApp uses the `@lid` format instead of phone numbers and make sure you send a test message to find the lid for your number and add that as a trusted contact.

#### Step 4: Start All Channels

Make sure you have started the Whatsapp Bridge before running the all channels script.

In **Terminal 3**:
```bash
source venv/bin/activate
bash scripts/start_all_channels.sh
```

You should see:
```
All channels ready!
  - WhatsApp: Connected to bridge
  - Web Chat: Starting on http://0.0.0.0:8000
```

#### Step 5: Start Using!

- **WhatsApp**: Send messages from your linked mobile device
- **Web Chat**: Open http://localhost:8000 in your browser

### Option 2: WhatsApp Only

```bash
# Terminal 1: Start bridge
cd bridge && npm run dev

# Terminal 2: Link WhatsApp (first time only)
python scripts/show_qr.py

# Terminal 3: Add contacts
python scripts/add_contact.py 'YOUR_IDENTIFIER'

# Terminal 4: Start agent
python -m support_agent.main
```

### Option 3: Web Chat Only

```bash
# Just start the all-channels script without the bridge
python -m support_agent.main_all_channels
```

Then open http://localhost:8000

## 💬 Usage

### WhatsApp Channel

From a **whitelisted WhatsApp contact**, send:

**Text Messages:**
```
What's the server1 status?
```

```
Run uptime command on server1
```

**Voice Messages:**
Just record and send - automatic transcription with Whisper!

### Web Chat Interface

1. Open http://localhost:8000 in your browser
2. Type your message in the input box
3. Press Enter or click "Send"
4. See real-time responses from the agent

**Features:**
- Real-time WebSocket communication
- Typing indicators
- Conversation history
- Auto-reconnect
- Beautiful gradient UI

### Available Tools

Built-in tools that the agent can use:
- `get_system_status`: Get CPU, memory, disk usage
- `execute_ssh_command`: Run commands on remote servers via SSH

The agent automatically decides when to use tools based on your query.

## 🛠️ Customization

### Adding Custom Tools

Create a new tool in `src/support_agent/tools/builtin/`:

```python
from pydantic import BaseModel, Field
from ..base import tool

class MyToolArgs(BaseModel):
    param1: str = Field(description="Description of param1")

@tool(
    name="my_custom_tool",
    description="What this tool does",
    args_schema=MyToolArgs
)
async def my_custom_tool(param1: str) -> dict:
    # Your implementation
    return {"result": "success"}
```

Register in `src/support_agent/tools/builtin/__init__.py`:

```python
def register_builtin_tools(registry):
    from .my_tool import my_custom_tool
    registry.register(my_custom_tool)
```

### Customizing the Knowledge Base

Edit `config/knowledge.md` to add:
- Server-specific information
- Common procedures and commands
- Response templates
- Custom instructions

The agent will have access to this information for every query.

### Adding More Channels

Create a new channel by implementing `BaseChannel`:

```python
from ..channels.base import BaseChannel

class SlackChannel(BaseChannel):
    async def connect(self): ...
    async def listen(self): ...
    async def send(self, message): ...
```

All channels automatically use the same agent logic and knowledge base!

## 📂 Project Structure

```
support-agent/
├── bridge/                      # Node.js Baileys bridge (WhatsApp)
│   ├── src/
│   │   ├── index.ts            # Express + WebSocket server
│   │   └── whatsapp.ts         # Baileys integration
│   └── package.json
│
├── config/                      # Configuration files
│   ├── knowledge.md            # LLM knowledge base ⭐
│   ├── settings.yaml           # App settings
│   └── contacts.yaml           # WhatsApp whitelist
│
├── src/support_agent/          # Python application
│   ├── main.py                # Single channel entry point
│   ├── main_all_channels.py   # Multi-channel entry point ⭐
│   ├── config.py              # Configuration loader
│   │
│   ├── core/                  # Core logic
│   │   ├── agent.py           # Main orchestrator
│   │   └── message.py         # Message models
│   │
│   ├── channels/              # Channel implementations
│   │   ├── base.py            # Channel interface
│   │   ├── whatsapp.py        # WhatsApp channel
│   │   └── web.py             # Web chat channel ⭐
│   │
│   ├── web/                   # Web UI
│   │   ├── server.py          # FastAPI server ⭐
│   │   └── templates/
│   │       └── chat.html      # Chat interface ⭐
│   │
│   ├── llm/                   # LLM providers
│   ├── voice/                 # Voice transcription
│   ├── tools/                 # Tool system
│   └── security/              # Authorization
│
├── scripts/                    # Utility scripts
│   ├── show_qr.py             # Display WhatsApp QR code
│   ├── add_contact.py         # Add to whitelist
│   └── start_all_channels.sh  # Start all channels ⭐
│
└── README.md
```

## 🐛 Troubleshooting

### WhatsApp Issues

#### Bridge Won't Start
```bash
cd bridge
rm -rf node_modules package-lock.json
npm install
npm run dev
```

#### WhatsApp Won't Link
1. Make sure bridge is running
2. Check `BRIDGE_URL` in `.env` matches bridge port
3. Try restarting bridge
4. Run setup script again: `python scripts/show_qr.py`

#### Messages Ignored - "Non-whitelisted contact"
WhatsApp uses `@lid` identifiers instead of phone numbers:

1. Send a test message from WhatsApp
2. Check the bridge logs for `Received message from 125438848454740@lid`
3. Check Python agent logs for the exact identifier
4. Whitelist using that **exact identifier**:
   ```bash
   python scripts/add_contact.py '125438848454740@lid'
   ```

### Web Chat Issues

#### Port Already in Use
Change the port in `main_all_channels.py`:
```python
web_server = create_web_server(web_channel, host="0.0.0.0", port=8001)
```

#### Web Chat Not Connecting
1. Check if the agent is running
2. Open browser console (F12) for errors
3. Try http://127.0.0.1:8000 instead of localhost
4. Check firewall settings

### Voice Messages Don't Work

1. Check ffmpeg: `ffmpeg -version`
2. Check Whisper loaded: Look for "Whisper model loaded" in logs
3. Try smaller model: `WHISPER_MODEL=tiny` in `.env`

### LLM Not Responding

1. **Ollama**: Check it's running: `ollama list`
2. **OpenAI**: Verify API key in `.env`
3. Check logs for specific errors
4. Test LLM directly: `ollama run mistral-small3.1`

### No Response from Agent

1. Check contact is whitelisted (for WhatsApp)
2. Check Ollama/LLM is running
3. Check agent logs for errors
4. Verify bridge is connected (for WhatsApp)

## 🔒 Security Notes

- **WhatsApp Whitelist**: Only whitelisted contacts can interact via WhatsApp
- **Web Chat**: Currently open to anyone who can access the URL (add authentication if needed)
- **SSH Keys**: Use key-based SSH authentication (not passwords)
- **Environment Variables**: Keep `.env` secure, never commit
- **Network**: Bridge runs on localhost by default (port 3000)
- **Firewall**: Consider firewall rules if exposing web chat externally

## 📊 Key Concepts

### Multi-Channel Architecture

Each channel operates independently but shares:
- **Same Agent**: Common inference logic
- **Same LLM**: Shared language model
- **Same Tools**: All tools available to all channels
- **Same Knowledge Base**: Shared permanent memory

But maintains separate:
- **Conversation History**: Per-user per-channel contexts
- **Authentication**: Channel-specific authorization
- **Message Format**: Automatically converted to standard format

### Knowledge Base System

The `config/knowledge.md` file is loaded into every LLM query as permanent context. Use it for:
- Server configurations
- Common procedures
- Response guidelines
- Domain-specific knowledge

This ensures the agent always has access to your custom instructions and information.

### Conversation Contexts

Contexts are stored per-user per-channel:
- WhatsApp user A = `whatsapp:+1234567890`
- Web user A = `web:web_abc123`

This means the same person can have different conversations on different channels.

## 📝 Development

### Running Tests

```bash
pip install -e ".[dev]"
pytest
```

### Code Formatting

```bash
black src/ tests/
ruff check src/ tests/
```

## 📄 License

MIT

## 🙏 Credits

Built with:
- [@whiskeysockets/baileys](https://github.com/WhiskeySockets/Baileys) - WhatsApp Web API
- [FastAPI](https://fastapi.tiangolo.com/) - Web framework
- [OpenAI Whisper](https://github.com/openai/whisper) - Voice transcription
- [Ollama](https://ollama.com/) - Local LLM runtime

---

