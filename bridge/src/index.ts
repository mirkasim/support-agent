import express from 'express';
import { WebSocketServer, WebSocket } from 'ws';
import { createServer } from 'http';
import cors from 'cors';
import { WhatsAppBridge, type WhatsAppMessage } from './whatsapp.js';

const app = express();
const server = createServer(app);
const wss = new WebSocketServer({ server, path: '/ws/messages' });

const PORT = process.env.PORT || 3000;
const AUTH_DIR = process.env.WHATSAPP_AUTH_DIR || './data/whatsapp-auth';

// Middleware
app.use(cors());
app.use(express.json());

// Initialize WhatsApp bridge
const whatsappBridge = new WhatsAppBridge(AUTH_DIR);
const connectedClients = new Set<WebSocket>();

// Initialize WhatsApp connection
async function initializeWhatsApp() {
  try {
    console.log('Initializing WhatsApp bridge...');
    await whatsappBridge.initialize();

    // Forward messages to all connected WebSocket clients
    whatsappBridge.on('message', (message: WhatsAppMessage) => {
      console.log('Received message from', message.from);

      // Convert Buffer voiceData to base64 for JSON serialization
      const messageData = { ...message };
      if (message.voiceData) {
        messageData.voiceData = message.voiceData.toString('base64');
        console.log('Voice message detected, converted to base64');
      }

      const payload = JSON.stringify({
        type: 'message',
        data: messageData,
      });

      connectedClients.forEach((client) => {
        if (client.readyState === WebSocket.OPEN) {
          client.send(payload);
        }
      });
    });

    // Forward connection events
    whatsappBridge.on('connected', () => {
      console.log('WhatsApp connected');
      broadcastStatus();
    });

    whatsappBridge.on('disconnected', () => {
      console.log('WhatsApp disconnected');
      broadcastStatus();
    });

    whatsappBridge.on('qr', (qr: string) => {
      console.log('QR code generated');
      broadcastStatus();
    });

  } catch (error) {
    console.error('Failed to initialize WhatsApp:', error);
  }
}

function broadcastStatus() {
  const status = whatsappBridge.getStatus();
  const payload = JSON.stringify({
    type: 'status',
    data: status,
  });

  connectedClients.forEach((client) => {
    if (client.readyState === WebSocket.OPEN) {
      client.send(payload);
    }
  });
}

// WebSocket connection handler
wss.on('connection', (ws: WebSocket) => {
  console.log('New WebSocket client connected');
  connectedClients.add(ws);

  // Send current status immediately
  ws.send(JSON.stringify({
    type: 'status',
    data: whatsappBridge.getStatus(),
  }));

  ws.on('close', () => {
    console.log('WebSocket client disconnected');
    connectedClients.delete(ws);
  });

  ws.on('error', (error) => {
    console.error('WebSocket error:', error);
    connectedClients.delete(ws);
  });
});

// REST API Endpoints

// Health check
app.get('/health', (req, res) => {
  res.json({
    status: 'ok',
    whatsapp: {
      connected: whatsappBridge.isConnected(),
      authenticated: whatsappBridge.isAuthenticated(),
    },
  });
});

// Get WhatsApp status
app.get('/api/status', (req, res) => {
  const status = whatsappBridge.getStatus();
  res.json(status);
});

// Get QR code for linking
app.get('/api/qr', (req, res) => {
  const qrCode = whatsappBridge.getQRCode();

  if (qrCode) {
    res.json({
      qr: qrCode,
      message: 'Scan this QR code with WhatsApp',
    });
  } else if (whatsappBridge.isAuthenticated()) {
    res.json({
      message: 'Already authenticated',
    });
  } else {
    res.status(404).json({
      error: 'QR code not available. Try restarting the bridge.',
    });
  }
});

// Send message
app.post('/api/send', async (req, res) => {
  try {
    const { to, text } = req.body;

    if (!to || !text) {
      return res.status(400).json({
        error: 'Missing required fields: to, text',
      });
    }

    if (!whatsappBridge.isConnected()) {
      return res.status(503).json({
        error: 'WhatsApp not connected',
      });
    }

    await whatsappBridge.sendMessage(to, text);

    res.json({
      success: true,
      message: 'Message sent successfully',
    });
  } catch (error: any) {
    console.error('Error sending message:', error);
    res.status(500).json({
      error: 'Failed to send message',
      details: error.message,
    });
  }
});

// Logout and clear session
app.post('/api/logout', async (req, res) => {
  try {
    await whatsappBridge.disconnect();
    await whatsappBridge.clearAuth();

    res.json({
      success: true,
      message: 'Logged out successfully',
    });
  } catch (error: any) {
    console.error('Error logging out:', error);
    res.status(500).json({
      error: 'Failed to logout',
      details: error.message,
    });
  }
});

// Restart connection (re-initialize)
app.post('/api/restart', async (req, res) => {
  try {
    console.log('Restarting WhatsApp bridge...');
    await whatsappBridge.disconnect();

    // Wait a bit before reinitializing
    setTimeout(async () => {
      await initializeWhatsApp();
    }, 2000);

    res.json({
      success: true,
      message: 'Restarting WhatsApp bridge',
    });
  } catch (error: any) {
    console.error('Error restarting:', error);
    res.status(500).json({
      error: 'Failed to restart',
      details: error.message,
    });
  }
});

// Start server
server.listen(PORT, async () => {
  console.log(`WhatsApp Bridge server running on port ${PORT}`);
  console.log(`WebSocket endpoint: ws://localhost:${PORT}/ws/messages`);
  console.log(`HTTP API: http://localhost:${PORT}`);
  console.log('');

  // Initialize WhatsApp
  await initializeWhatsApp();
});

// Graceful shutdown
process.on('SIGINT', async () => {
  console.log('\nShutting down gracefully...');

  // Close WebSocket connections
  connectedClients.forEach((client) => {
    client.close();
  });

  // Disconnect WhatsApp
  await whatsappBridge.disconnect();

  // Close server
  server.close(() => {
    console.log('Server closed');
    process.exit(0);
  });
});
