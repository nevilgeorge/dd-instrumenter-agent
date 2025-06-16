import requests
from bs4 import BeautifulSoup
from typing import Dict, Optional
import logging
from dataclasses import dataclass
from urllib.parse import urljoin

@dataclass
class DocSection:
    """Represents a section of documentation with its content and metadata."""
    title: str
    content: str
    url: str

    def to_prompt(self) -> str:
        """Convert the documentation section into a prompt string format.

        Returns:
            A formatted string containing the title and content of the section.
        """
        return f"{self.title}\n\n{self.content}"

class DocumentRetriever:
    """Retrieves and parses documentation from Datadog's website."""

    BASE_URL = "https://docs.datadoghq.com"
    LAMBDA_DOCS_URL = "/serverless/aws_lambda/installation/{runtime}/?tab={iac_tool}"

    def __init__(self):
        """Initialize the document retriever with default headers."""
        self.logger = logging.getLogger(__name__)
        self.headers = {
            "User-Agent": "DD-Instrumenter-Agent/1.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def _get_page_content(self, url: str) -> Optional[str]:
        """Fetch the content of a webpage.

        Args:
            url: The URL to fetch content from

        Returns:
            The page content as a string, or None if the request failed
        """
        try:
            response = self.session.get(url)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            self.logger.error(f"Failed to fetch documentation from {url}: {str(e)}")
            return None

    def _extract_main_content(self, soup: BeautifulSoup) -> Optional[DocSection]:
        """Extract content from the mainContent div.

        Args:
            soup: BeautifulSoup object of the page

        Returns:
            DocSection containing the parsed content, or None if mainContent not found
        """
        # Find the main content div
        main_content = soup.find('div', id='mainContent')
        if not main_content:
            self.logger.warning("Could not find mainContent div")
            return None

        # Get the title (first h1 in mainContent)
        title = main_content.find('h1')
        title_text = title.get_text().strip() if title else "Untitled Section"
        content = self.extract_main_content_from_html(main_content)

        return DocSection(
            title=title_text,
            content=content,
            url=urljoin(self.BASE_URL, self.LAMBDA_DOCS_URL)
        )

    def extract_main_content_from_html(self, main_content: BeautifulSoup) -> str:

        # Remove unnecessary tab navs, script, style
        for tag in main_content(["script", "style", "ul", "nav", "header", "footer"]):
            tag.decompose()

        # Accumulate visible content
        content_parts = []

        # Title (h1)
        title = main_content.find("h1")
        if title:
            content_parts.append(f"# {title.get_text(strip=True)}")

        # Alerts (warnings, infos)
        for alert in main_content.select(".alert"):
            content_parts.append(f"> ⚠️ {alert.get_text(strip=True)}")

        # Subheadings (h2, h3)
        for header in main_content.find_all(["h2", "h3"]):
            level = "#" * int(header.name[1])
            content_parts.append(f"{level} {header.get_text(strip=True)}")

        # Paragraphs
        for p in main_content.find_all("p"):
            text = p.get_text(strip=True)
            if text:
                content_parts.append(text)

        # Preformatted/code blocks
        for pre in main_content.find_all("pre"):
            code = pre.get_text()
            content_parts.append(f"```sh\n{code}\n```")

        # Return joined clean text
        return "\n\n".join(content_parts)


    def get_lambda_documentation(self, runtime: str, iac_tool: str) -> Dict[str, DocSection]:
        """Retrieve and parse the AWS Lambda documentation.

        Args:
            runtime: The Lambda runtime (e.g., 'node.js', 'python')
            iac_tool: The IaC tool ('cdk' or 'terraform')

        Returns:
            Dictionary with a single DocSection containing all documentation content
        """
        if iac_tool not in ['cdk', 'terraform']:
            raise ValueError(f"Invalid IaC tool: {iac_tool}")

        runtime_to_url_path = {
            'node.js': 'nodejs',
            'python': 'python',
            'java': 'java',
            'go': 'go',
            'ruby': 'ruby',
            'dotnet': 'dotnet',
        }

        if runtime not in runtime_to_url_path:
            raise ValueError(f"Invalid runtime: {runtime}. Must be one of {list(runtime_to_url_path.keys())}")

        url = urljoin(self.BASE_URL, self.LAMBDA_DOCS_URL.format(
            runtime=runtime_to_url_path[runtime],
            iac_tool=iac_tool
        ))
        content = self._get_page_content(url)

        if not content:
            self.logger.error("Failed to retrieve Lambda documentation")
            return {}

        soup = BeautifulSoup(content, 'html.parser')
        doc_section = self._extract_main_content(soup)

        if not doc_section:
            self.logger.error("Failed to parse documentation content")
            return {}

        return {"documentation": doc_section}
