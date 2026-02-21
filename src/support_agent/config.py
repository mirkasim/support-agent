"""Configuration management for the support agent."""

from pathlib import Path
from typing import Optional
import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings from environment variables and config files.

    Environment variables take precedence over config files.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # General
    app_name: str = Field(default="Support Agent", description="Application name")
    debug: bool = Field(default=False, description="Debug mode")
    log_level: str = Field(default="INFO", description="Logging level")

    # Baileys Bridge
    bridge_url: str = Field(
        default="http://localhost:3000", description="URL of Baileys bridge server"
    )

    # LLM Configuration
    llm_provider: str = Field(default="ollama", description="LLM provider: ollama or openai")
    llm_model: str = Field(default="llama2", description="Model name to use")
    llm_base_url: str = Field(
        default="http://localhost:11434", description="LLM API base URL"
    )
    llm_api_key: Optional[str] = Field(default=None, description="API key for OpenAI-compatible APIs")
    llm_hide_reasoning: bool = Field(
        default=True, description="Hide reasoning/thinking output from LLM responses (for o1 models, etc.)"
    )

    # Whisper Configuration
    whisper_model: str = Field(
        default="base", description="Whisper model: tiny, base, small, medium, large"
    )
    whisper_device: str = Field(default="cpu", description="Device for Whisper: cpu or cuda")

    # Session Management
    session_timeout_seconds: int = Field(
        default=3600, description="Session timeout in seconds (default 1 hour). History is cleared after this gap."
    )

    # Paths
    config_dir: Path = Field(default=Path("./config"), description="Configuration directory")
    data_dir: Path = Field(default=Path("./data"), description="Data directory")
    whatsapp_auth_dir: Path = Field(
        default=Path("./data/whatsapp-auth"), description="WhatsApp auth storage"
    )

    def load_yaml_config(self, config_file: Optional[Path] = None) -> dict:
        """Load additional configuration from YAML file.

        Args:
            config_file: Path to settings.yaml (defaults to config_dir/settings.yaml)

        Returns:
            Dictionary of YAML configuration
        """
        if config_file is None:
            config_file = self.config_dir / "settings.yaml"

        if not config_file.exists():
            return {}

        with open(config_file) as f:
            return yaml.safe_load(f) or {}


def load_settings() -> Settings:
    """Load application settings.

    YAML config is loaded first as defaults; environment variables take precedence.

    Returns:
        Settings instance with environment variables loaded
    """
    # Load YAML defaults first
    base = Settings()
    yaml_config = base.load_yaml_config()

    # Map nested YAML keys to flat Settings fields
    llm = yaml_config.get("llm", {})
    yaml_defaults = {}
    if "provider" in llm:
        yaml_defaults["llm_provider"] = llm["provider"]
    if "model" in llm:
        yaml_defaults["llm_model"] = llm["model"]
    if "temperature" in llm:
        yaml_defaults["llm_temperature"] = llm["temperature"]
    if "max_tokens" in llm:
        yaml_defaults["llm_max_tokens"] = llm["max_tokens"]

    # Re-create Settings with YAML values as defaults; env vars still win
    return Settings(**yaml_defaults)
