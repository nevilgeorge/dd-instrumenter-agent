import logging
import os

import colorlog
import openai
from dd_internal_authentication.client import (
    JWTDDToolAuthClientTokenManager, JWTInternalServiceAuthClientTokenManager)


def setup_logging():
    """Configure application logging."""
    handler = colorlog.StreamHandler()
    handler.setFormatter(colorlog.ColoredFormatter(
        "%(log_color)s%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red,bg_white',
        }
    ))

    # Get log level from environment variable, default to INFO
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    # Validate log level
    valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    if log_level not in valid_levels:
        log_level = "INFO"

    # Convert string log level to logging constant
    numeric_level = getattr(logging, log_level, logging.INFO)
    logging.basicConfig(level=numeric_level, handlers=[handler])

    logger = logging.getLogger(__name__)
    logger.info(f"Logging level set to {log_level}")

    return logger


def setup_openai_client():
    """Configure and return OpenAI client."""
    logger = logging.getLogger(__name__)
    local = True # Switch based on environment

    try:
        if local:
            logger.debug("Attempting to use DD internal auth (local/staging)")
            token = JWTDDToolAuthClientTokenManager.instance(
                name="rapid-ai-platform", datacenter="us1.staging.dog"
            ).get_token("rapid-ai-platform")
            host = "https://ai-gateway.us1.staging.dog"
        else:
            logger.debug("Attempting to use DD internal auth (production)")
            token = JWTInternalServiceAuthClientTokenManager.instance(
                name="rapid-ai-platform"
            ).get_token("rapid-ai-platform")
            host = "http://ai-gateway.rapid-ai-platform.sidecar-proxy.fabric.dog.:15001"

        logger.info(f"Successfully configured DD internal auth, using host: {host}")
        return openai.OpenAI(
            api_key=token,
            base_url=f"{host}/v1",
            default_headers={
                "source": "dd-instrumenter-agent",
                "org-id": "2",
            },
        )
    except (ImportError, AttributeError, Exception) as e:
        logger.warning(f"DD internal auth failed: {e}")
        logger.info("Falling back to OpenAI API key from environment")

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.error("No OPENAI_API_KEY found in environment variables")
            raise ValueError("No valid authentication method available - DD internal auth failed and no OPENAI_API_KEY set")

        logger.info("Successfully configured OpenAI client with API key")
        return openai.OpenAI(
            api_key=api_key,
            base_url=f"{host}/v1",
            default_headers={
                "source": "dd-instrumenter-agent",
                "org-id": "2",
            },
        )
