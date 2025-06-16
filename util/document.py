from pydantic import BaseModel, Field
from typing import Dict, Any

class Document(BaseModel):
    """A document containing content and metadata."""
    page_content: str = Field(description="The main content of the document")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata associated with the document")