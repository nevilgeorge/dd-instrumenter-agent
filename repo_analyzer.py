from typing import Dict, List, Literal
from langchain.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain.schema import Document
from langchain.chains import LLMChain
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
import os


class RepoType(BaseModel):
    """Schema for repository type analysis output."""
    repo_type: Literal["cdk", "terraform", "neither"] = Field(description="The type of infrastructure as code project")
    confidence: float = Field(description="Confidence score between 0 and 1")
    evidence: List[str] = Field(description="List of evidence found in the repository that led to this conclusion")
    cdk_script_file: str = Field(description="The name of the file that contains the CDK script")
    terraform_script_file: str = Field(description="The name of the file that contains the Terraform script")

class RepoAnalyzer:
    """
    Analyzes repository contents to determine if it's a CDK, Terraform, or neither.
    Uses LangChain and OpenAI to perform the analysis.
    """

    def __init__(self, llm: ChatOpenAI):
        """
        Initialize the RepoAnalyzer.
        
        Args:
            llm: ChatOpenAI instance for repository analysis
        """
        self.llm = llm
        
        # Create a prompt template for repository analysis
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert at analyzing code repositories to determine their infrastructure type.
            Analyze the following repository contents and determine if it's a CDK project, Terraform project, or neither.
            If a CDK project is detected, look for the cdk.json file and the CDK app files.
            If a Terraform project is detected, look for the .tf files, terraform.tfstate, and .tfvars files.
            
            Look for key indicators:
            - CDK: presence of cdk.json, CDK app files, aws-cdk-lib dependencies
            - Terraform: .tf files, terraform.tfstate, .tfvars files
            
            You must respond with ONLY a JSON object with the following keys only (no other text):
                - "repo_type": ["cdk", "terraform", "neither"],
                - "confidence": 0.95,
                - "evidence": ["Found cdk.json", "Found aws-cdk-lib dependency"]
                - "cdk_script_file": the name of the file that contains the CDK script (if detected), empty string if not detected
                - "terraform_script_file": the name of the file that contains the Terraform script (if detected), empty string if not detected
            
            
            The repo_type must be exactly one of: "cdk", "terraform", or "neither"
            The confidence must be a number between 0 and 1
            The evidence must be a list of strings
            
            Repository contents:
            {repo_contents}
            """),
            ("human", "Analyze this repository. Return ONLY the JSON object, no other text.")
        ])

        # Create a chain that uses the prompt and parses output into our schema
        self.chain = LLMChain(
            llm=self.llm,
            prompt=self.prompt,
            output_parser=PydanticOutputParser(pydantic_object=RepoType),
            verbose=True
        )

    def analyze_repo(self, documents: List[Document]) -> RepoType:
        """
        Analyze repository contents to determine its type.
        :param documents: List of LangChain Document objects containing repository contents
        :return: RepoType object containing the analysis results
        """
        # Format repository contents for the prompt
        repo_contents = "\n".join([
            f"File: {os.path.basename(doc.metadata.get('source', 'unknown'))}\n---"
            for doc in documents
        ])
        
        try:
            # Get the raw dictionary result
            result_dict = self.chain.invoke({"repo_contents": repo_contents})
            print("Raw dictionary result:", result_dict)
            return result_dict['text']
        except Exception as e:
            print(f"Error analyzing repository: {str(e)}")
            raise 