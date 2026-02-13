"""Main application entry point."""

import asyncio
from pathlib import Path
from loguru import logger
from dotenv import load_dotenv

from .config import load_settings
from .core.agent import SupportAgent
from .channels.whatsapp import WhatsAppChannel
from .llm.factory import create_llm
from .voice.transcriber import Transcriber
from .tools.registry import ToolRegistry
from .tools.builtin import register_builtin_tools
from .security.whitelist import ContactWhitelist
from .utils.logging import setup_logging


async def main():
    """Main application entry point."""

    # Load environment variables
    load_dotenv()

    # Load settings
    settings = load_settings()

    # Setup logging
    setup_logging(settings.log_level)
    logger.info("=" * 60)
    logger.info("Starting Support Agent System")
    logger.info("=" * 60)

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

        # 4. Load additional YAML config
        yaml_config = settings.load_yaml_config()
        llm_config = yaml_config.get("llm", {})
        system_prompt = llm_config.get("system_prompt")

        # 5. Create agent
        logger.info("Creating support agent...")
        agent = SupportAgent(
            llm=llm,
            tool_registry=tool_registry,
            transcriber=transcriber,
            system_prompt=system_prompt,
            session_timeout_seconds=settings.session_timeout_seconds,
        )

        # 6. Load contact whitelist
        contacts_file = settings.config_dir / "contacts.yaml"
        whitelist = ContactWhitelist(contacts_file)
        logger.info(f"Loaded {len(whitelist)} whitelisted contacts")

        if len(whitelist) == 0:
            logger.warning("No whitelisted contacts! Add contacts using scripts/add_contact.py")

        # 7. Create WhatsApp channel
        logger.info(f"Connecting to WhatsApp bridge at {settings.bridge_url}")
        whatsapp = WhatsAppChannel(bridge_url=settings.bridge_url, whitelist=whitelist)

        # 8. Connect to WhatsApp
        await whatsapp.connect()
        logger.info("Connected to WhatsApp bridge")

        # Check status
        status = await whatsapp.get_status()
        logger.info(f"WhatsApp status: {status}")

        if not status.get("authenticated"):
            logger.warning(
                "WhatsApp not authenticated! Run scripts/setup_whatsapp.py to scan QR code"
            )
            qr_code = await whatsapp.get_qr_code()
            if qr_code:
                logger.info("QR code available - check bridge logs or run setup script")

        # 9. Main message processing loop
        logger.info("Starting message processing loop...")
        logger.info("Ready to receive messages!")
        logger.info("=" * 60)

        async for message in whatsapp.listen():
            logger.info(
                f"Received {message.message_type} message from {message.sender_name or message.sender_id}"
            )

            try:
                # Process message through agent
                response = await agent.process_message(message)

                # Send response back
                await whatsapp.send(response)

                logger.info("Response sent successfully")

            except Exception as e:
                logger.error(f"Error processing message: {e}")
                # Send error message to user
                try:
                    error_msg = message.create_reply(
                        "Sorry, I encountered an error processing your request. Please try again."
                    )
                    error_msg.metadata["recipient"] = message.sender_id
                    await whatsapp.send(error_msg)
                except Exception as send_error:
                    logger.error(f"Failed to send error message: {send_error}")

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
        logger.info("Support Agent System stopped")
        logger.info("=" * 60)


def run():
    """Entry point for running the application."""
    asyncio.run(main())


if __name__ == "__main__":
    run()
