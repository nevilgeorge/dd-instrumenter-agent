import logging
from typing import Dict, Any, Optional

import openai


class BaseLLMClient:
    """Base class for standardized LLM client calls across the application."""
    
    DEFAULT_MODEL = "gpt-4o-mini"
    DEFAULT_TEMPERATURE = 0
    DEFAULT_STREAM = False
    
    def __init__(self, client: openai.OpenAI, model: Optional[str] = None):
        """
        Initialize the base LLM client.
        
        Args:
            client: OpenAI client instance
            model: Optional model override (defaults to DEFAULT_MODEL)
        """
        self.client = client
        self.model = model or self.DEFAULT_MODEL
        self.logger = logging.getLogger(__name__)
    
    def make_completion(
        self, 
        prompt: str, 
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        stream: Optional[bool] = None,
        **kwargs
    ) -> str:
        """
        Make a standardized completion call to the LLM.
        
        Args:
            prompt: The user prompt to send
            model: Optional model override
            temperature: Optional temperature override
            stream: Optional stream override
            **kwargs: Additional parameters to pass to the completion call
            
        Returns:
            The completion response content
            
        Raises:
            Exception: If the completion call fails
        """
        try:
            response = self.client.chat.completions.create(
                model=model or self.model,
                temperature=temperature or self.DEFAULT_TEMPERATURE,
                stream=stream or self.DEFAULT_STREAM,
                messages=[{"role": "user", "content": prompt}],
                **kwargs
            )
            return response.choices[0].message.content
        except Exception as e:
            self.logger.error(f"Error making completion call: {str(e)}")
            raise