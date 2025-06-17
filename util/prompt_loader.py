"""Utility for loading and formatting prompt templates."""

import json
import re
from pathlib import Path
from typing import Any


def load_prompt_template(template_name: str, **kwargs: Any) -> str:
    """
    Load a prompt template from the prompts directory and format it with provided variables.

    Args:
        template_name: Name of the template file (without .md extension)
        **kwargs: Variables to substitute in the template

    Returns:
        Formatted prompt string

    Raises:
        FileNotFoundError: If template file doesn't exist
        KeyError: If required template variables are missing
    """
    # Get the project root directory (parent of util directory)
    current_dir = Path(__file__).parent
    project_root = current_dir.parent
    template_path = project_root / "prompts" / f"{template_name}.md"

    if not template_path.exists():
        raise FileNotFoundError(f"Prompt template not found: {template_path}")

    with open(template_path, 'r', encoding='utf-8') as f:
        template_content = f.read()

    try:
        return template_content.format(**kwargs)
    except KeyError as e:
        raise KeyError(f"Missing required template variable: {e}")


def parse_json_response(response_text: str) -> dict:
    """
    Parse JSON from LLM response, handling markdown code blocks.

    Args:
        response_text: Raw response from LLM

    Returns:
        Parsed JSON dictionary

    Raises:
        json.JSONDecodeError: If JSON cannot be parsed
    """
    # Remove markdown code block markers if present
    text = response_text.strip()
    if text.startswith("```json"):
        text = text[7:]  # Remove ```json
    elif text.startswith("```"):
        text = text[3:]   # Remove ```

    if text.endswith("```"):
        text = text[:-3]  # Remove closing ```

    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Fallback: try to extract JSON from anywhere in the response
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        raise
