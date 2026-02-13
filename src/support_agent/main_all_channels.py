"""Main application entry point with all channels (WhatsApp + Web)."""

import asyncio
from pathlib import Path
from loguru import logger
from dotenv import load_dotenv

from .config import load_settings
from .core.agent import SupportAgent
from .channels.whatsapp import WhatsAppChannel
from .channels.web import WebChannel
from .llm.factory import create_llm
from .voice.transcriber import Transcriber
from .tools.registry import ToolRegistry
from .tools.builtin import register_builtin_tools
from .security.whitelist import ContactWhitelist
from .utils.logging import setup_logging
from .web.server import create_web_server


async def process_channel_messages(channel, agent, channel_name: str):
    """Process messages from a specific channel.

    Args:
        channel: Channel instance
        agent: Support agent instance
        channel_name: Name of the channel for logging
    """
    logger.info(f"Starting message processing for {channel_name}")

    try:
        async for message in channel.listen():
            logger.info(
                f"[{channel_name}] Received {message.message_type} from {message.sender_name or message.sender_id}"
            )

            try:
                # Process message through agent
                response = await agent.process_message(message)

                # Send response back through the same channel
                await channel.send(response)

                logger.info(f"[{channel_name}] Response sent successfully")

            except Exception as e:
                logger.error(f"[{channel_name}] Error processing message: {e}")
                # Send error message to user
                try:
                    error_msg = message.create_reply(
                        "Sorry, I encountered an error processing your request. Please try again."
                    )
                    # Preserve metadata for routing
                    error_msg.metadata = message.metadata
                    await channel.send(error_msg)
                except Exception as send_error:
                    logger.error(f"[{channel_name}] Failed to send error message: {send_error}")

    except Exception as e:
        logger.error(f"[{channel_name}] Fatal error in message processing: {e}")


async def main():
    """Main application entry point with all channels."""

    # Load environment variables
    load_dotenv()

    # Load settings
    settings = load_settings()

    # Setup logging
    setup_logging(settings.log_level)
    logger.info("=" * 80)
    logger.info("Starting Support Agent System (All Channels)")
    logger.info("=" * 80)

    try:
        # 1. Create LLM instance
        logger.info(f"Initializing LLM: {settings.llm_provider}/{settings.llm_model}")
        llm = create_llm(settings)

        # 2. Create tool registry and register tools
        logger.info("Setting up tool registry...")
        tool_registry = ToolRegistry()
        register_builtin_tools(tool_registry, settings)
        logger.info(f"Registered {len(tool_registry)} tools")

        # 3. Create transcriber (optional)
        transcriber = None
        try:
            logger.info(f"Loading Whisper model: {settings.whisper_model}")
            transcriber = Transcriber(
                model_name=settings.whisper_model, device=settings.whisper_device
            )
        except Exception as e:
            logger.warning(f"Could not load Whisper (voice messages disabled): {e}")

        # 4. Load knowledge base
        knowledge_path = settings.config_dir / "knowledge.md"

        # 5. Create agent
        logger.info("Creating support agent...")
        agent = SupportAgent(
            llm=llm,
            tool_registry=tool_registry,
            transcriber=transcriber,
            knowledge_base_path=knowledge_path,
            session_timeout_seconds=settings.session_timeout_seconds,
        )

        # 6. Load contact whitelist (for WhatsApp)
        contacts_file = settings.config_dir / "contacts.yaml"
        whitelist = ContactWhitelist(contacts_file)
        logger.info(f"Loaded {len(whitelist)} whitelisted contacts for WhatsApp")

        if len(whitelist) == 0:
            logger.warning("No whitelisted contacts! Add contacts using scripts/add_contact.py")

        # 7. Create channels
        logger.info("Setting up channels...")

        # WhatsApp channel
        whatsapp = WhatsAppChannel(bridge_url=settings.bridge_url, whitelist=whitelist)

        # Web chat channel
        web_channel = WebChannel()

        # Connect channels
        await whatsapp.connect()
        await web_channel.connect()

        # Check WhatsApp status
        status = await whatsapp.get_status()
        logger.info(f"WhatsApp status: {status}")

        if not status.get("authenticated"):
            logger.warning(
                "WhatsApp not authenticated! Run scripts/setup_whatsapp.py to scan QR code"
            )

        logger.info("=" * 80)
        logger.info("All channels ready!")
        logger.info("  - WhatsApp: Connected to bridge")
        logger.info("  - Web Chat: Starting on http://0.0.0.0:8000")
        logger.info("=" * 80)

        # 8. Create tasks for each channel
        tasks = [
            asyncio.create_task(process_channel_messages(whatsapp, agent, "WhatsApp")),
            asyncio.create_task(process_channel_messages(web_channel, agent, "Web")),
        ]

        # 9. Start web server
        web_server = create_web_server(web_channel, host="0.0.0.0", port=8000)
        tasks.append(asyncio.create_task(web_server.start()))

        # Wait for all tasks
        await asyncio.gather(*tasks)

    except KeyboardInterrupt:
        logger.info("Shutting down gracefully...")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise
    finally:
        # Cleanup
        if "whatsapp" in locals():
            try:
                await whatsapp.disconnect()
            except:
                pass
        if "web_channel" in locals():
            try:
                await web_channel.disconnect()
            except:
                pass
        logger.info("Support Agent System stopped")
        logger.info("=" * 80)


def run():
    """Entry point for running the application."""
    asyncio.run(main())


if __name__ == "__main__":
    run()
