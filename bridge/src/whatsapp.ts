import makeWASocket, {
  DisconnectReason,
  useMultiFileAuthState,
  fetchLatestBaileysVersion,
  makeCacheableSignalKeyStore,
  downloadMediaMessage,
  type WASocket,
  type ConnectionState,
  type WAMessage,
  type proto,
} from '@whiskeysockets/baileys';
import { Boom } from '@hapi/boom';
import pino from 'pino';
import QRCode from 'qrcode';
import { EventEmitter } from 'events';
import * as fs from 'fs/promises';
import * as path from 'path';

export interface WhatsAppMessage {
  id: string;
  from: string;
  fromName?: string;
  body?: string;
  timestamp: number;
  isGroup: boolean;
  messageType: 'text' | 'voice' | 'image' | 'video' | 'document' | 'unknown';
  voiceData?: Buffer | string;  // Buffer when created, string (base64) when serialized
  mediaUrl?: string;
}

export interface WhatsAppStatus {
  connected: boolean;
  authenticated: boolean;
  qrCode?: string;
  error?: string;
}

export class WhatsAppBridge extends EventEmitter {
  private socket?: WASocket;
  private authDir: string;
  private qrCode?: string;
  private status: WhatsAppStatus = {
    connected: false,
    authenticated: false,
  };
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;

  constructor(authDir: string = './data/whatsapp-auth') {
    super();
    this.authDir = authDir;
  }

  async initialize(): Promise<void> {
    const logger = pino({ level: 'info' });

    // Ensure auth directory exists
    await fs.mkdir(this.authDir, { recursive: true });

    // Load auth state
    const { state, saveCreds } = await useMultiFileAuthState(this.authDir);

    // Get latest Baileys version
    const { version } = await fetchLatestBaileysVersion();

    // Create socket
    this.socket = makeWASocket({
      version,
      logger,
      printQRInTerminal: true,
      auth: {
        creds: state.creds,
        keys: makeCacheableSignalKeyStore(state.keys, logger),
      },
      getMessage: async (key) => {
        return { conversation: '' };
      },
    });

    // Save credentials on update
    this.socket.ev.on('creds.update', saveCreds);

    // Handle connection updates
    this.socket.ev.on('connection.update', async (update) => {
      const { connection, lastDisconnect, qr } = update;

      // Generate QR code
      if (qr) {
        this.qrCode = await QRCode.toDataURL(qr);
        this.status.qrCode = this.qrCode;
        this.emit('qr', this.qrCode);
        console.log('QR Code generated - scan with WhatsApp');
      }

      // Handle connection state
      if (connection === 'close') {
        const shouldReconnect =
          (lastDisconnect?.error as Boom)?.output?.statusCode !== DisconnectReason.loggedOut;

        console.log('Connection closed:', lastDisconnect?.error);
        this.status.connected = false;
        this.status.authenticated = false;
        this.emit('disconnected');

        if (shouldReconnect && this.reconnectAttempts < this.maxReconnectAttempts) {
          this.reconnectAttempts++;
          console.log(`Reconnecting... (attempt ${this.reconnectAttempts})`);
          setTimeout(() => this.initialize(), 5000);
        } else if (!shouldReconnect) {
          console.log('Logged out - please scan QR code again');
          this.status.error = 'Logged out';
          await this.clearAuth();
        } else {
          console.log('Max reconnect attempts reached');
          this.status.error = 'Max reconnect attempts exceeded';
        }
      } else if (connection === 'open') {
        console.log('WhatsApp connected successfully');
        this.reconnectAttempts = 0;
        this.status.connected = true;
        this.status.authenticated = true;
        this.status.qrCode = undefined;
        this.emit('connected');
      }
    });

    // Handle incoming messages
    this.socket.ev.on('messages.upsert', async ({ messages }) => {
      for (const msg of messages) {
        if (!msg.message || msg.key.fromMe) continue;

        const formattedMessage = await this.formatMessage(msg);
        if (formattedMessage) {
          this.emit('message', formattedMessage);
        }
      }
    });
  }

  private async formatMessage(msg: WAMessage): Promise<WhatsAppMessage | null> {
    const messageContent = msg.message;
    if (!messageContent) return null;

    const rawFrom = msg.key.remoteJid || '';
    const fromName = msg.pushName || '';
    const isGroup = rawFrom.endsWith('@g.us');

    // Try to get actual phone number
    let from = rawFrom;
    let phoneNumber: string | undefined;

    // Check if we can get phone number from participant (for @lid users)
    if (rawFrom.includes('@lid')) {
      // For @lid users, try to get phone number from the socket's contact store
      try {
        if (this.socket) {
          // Try to get contact info
          const contactInfo = await this.socket.onWhatsApp(rawFrom.split('@')[0]);
          if (contactInfo && contactInfo.length > 0 && contactInfo[0].jid) {
            const jid = contactInfo[0].jid;
            if (jid.includes('@s.whatsapp.net')) {
              phoneNumber = jid.split('@')[0];
              from = `+${phoneNumber}`;
              console.log(`Resolved lid ${rawFrom} to phone number: ${from}`);
            }
          }
        }
      } catch (e) {
        console.log(`Could not resolve phone number for ${rawFrom}, using lid as identifier`);
      }

      // If we couldn't resolve, use the lid as identifier
      if (!phoneNumber) {
        from = rawFrom;
        console.log(`Using lid as identifier: ${from}`);
      }
    } else if (rawFrom.includes('@s.whatsapp.net')) {
      // Standard WhatsApp format
      phoneNumber = rawFrom.split('@')[0];
      if (phoneNumber && phoneNumber.length >= 10) {
        from = `+${phoneNumber}`;
      }
    }

    let messageType: WhatsAppMessage['messageType'] = 'unknown';
    let body: string | undefined;
    let voiceData: Buffer | undefined;
    let mediaUrl: string | undefined;

    // Extract message content based on type
    if (messageContent.conversation) {
      messageType = 'text';
      body = messageContent.conversation;
    } else if (messageContent.extendedTextMessage) {
      messageType = 'text';
      body = messageContent.extendedTextMessage.text ?? undefined;
    } else if (messageContent.audioMessage) {
      messageType = 'voice';
      try {
        const buffer = await this.downloadMediaMessage(msg);
        voiceData = buffer;
      } catch (error) {
        console.error('Failed to download voice message:', error);
      }
    } else if (messageContent.imageMessage) {
      messageType = 'image';
      body = messageContent.imageMessage.caption ?? undefined;
    } else if (messageContent.videoMessage) {
      messageType = 'video';
      body = messageContent.videoMessage.caption ?? undefined;
    } else if (messageContent.documentMessage) {
      messageType = 'document';
      body = messageContent.documentMessage.caption ?? undefined;
    }

    return {
      id: msg.key.id || '',
      from,
      fromName,
      body,
      timestamp: msg.messageTimestamp as number,
      isGroup,
      messageType,
      voiceData,
      mediaUrl,
    };
  }

  private async downloadMediaMessage(msg: WAMessage): Promise<Buffer> {
    if (!this.socket) throw new Error('Socket not initialized');

    const buffer = await downloadMediaMessage(msg, 'buffer', {});
    return buffer as Buffer;
  }

  async sendMessage(to: string, text: string): Promise<void> {
    if (!this.socket) {
      throw new Error('WhatsApp not connected');
    }

    await this.socket.sendMessage(to, { text });
  }

  async sendImage(to: string, imageBuffer: Buffer, caption?: string): Promise<void> {
    if (!this.socket) {
      throw new Error('WhatsApp not connected');
    }

    await this.socket.sendMessage(to, {
      image: imageBuffer,
      caption,
    });
  }

  getStatus(): WhatsAppStatus {
    return { ...this.status };
  }

  getQRCode(): string | undefined {
    return this.qrCode;
  }

  async clearAuth(): Promise<void> {
    try {
      await fs.rm(this.authDir, { recursive: true, force: true });
      await fs.mkdir(this.authDir, { recursive: true });
      console.log('Auth cleared successfully');
    } catch (error) {
      console.error('Failed to clear auth:', error);
    }
  }

  async disconnect(): Promise<void> {
    if (this.socket) {
      await this.socket.logout();
      this.socket = undefined;
    }
  }

  isConnected(): boolean {
    return this.status.connected;
  }

  isAuthenticated(): boolean {
    return this.status.authenticated;
  }
}
