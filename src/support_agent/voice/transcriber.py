"""Whisper-based voice transcription."""

import tempfile
from pathlib import Path
from typing import Union
import whisper
import torch


class Transcriber:
    """Whisper-based voice transcriber for converting audio to text."""

    def __init__(self, model_name: str = "base", device: str = "cpu"):
        """Initialize transcriber.

        Args:
            model_name: Whisper model size (tiny, base, small, medium, large)
            device: Device to run on ('cpu' or 'cuda')
        """
        self.model_name = model_name
        self.device = device
        self.model = None

        print(f"Loading Whisper model '{model_name}' on {device}...")
        self._load_model()

    def _load_model(self) -> None:
        """Load Whisper model."""
        try:
            self.model = whisper.load_model(self.model_name, device=self.device)
            print(f"Whisper model loaded successfully")
        except Exception as e:
            print(f"Error loading Whisper model: {e}")
            raise

    async def transcribe(
        self, audio_data: Union[bytes, str, Path], language: str = "en"
    ) -> str:
        """Transcribe audio to text.

        Args:
            audio_data: Audio data (bytes, file path, or Path object)
            language: Language code (e.g., 'en', 'es', 'fr')

        Returns:
            Transcribed text
        """
        if not self.model:
            raise RuntimeError("Whisper model not loaded")

        # Handle different input types
        audio_file = None
        temp_file = None

        try:
            if isinstance(audio_data, bytes):
                # Save bytes to temporary file
                temp_file = tempfile.NamedTemporaryFile(suffix=".ogg", delete=False)
                temp_file.write(audio_data)
                temp_file.close()
                audio_file = temp_file.name
            else:
                # File path
                audio_file = str(audio_data)

            # Transcribe
            result = self.model.transcribe(audio_file, language=language)

            return result["text"].strip()

        except Exception as e:
            print(f"Error transcribing audio: {e}")
            raise

        finally:
            # Clean up temporary file
            if temp_file:
                try:
                    Path(temp_file.name).unlink()
                except:
                    pass

    def change_model(self, model_name: str) -> None:
        """Change Whisper model.

        Args:
            model_name: New model name (tiny, base, small, medium, large)
        """
        self.model_name = model_name
        self._load_model()
