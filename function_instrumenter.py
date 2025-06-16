from typing import Dict, List, Literal
from langchain.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain.chains import LLMChain
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
import logging
from document_retriever import DocSection
from langchain.schema import Document

class InstrumentationResult(BaseModel):
    """Schema for instrumentation output."""
    modified_code: str = Field(description="The complete modified code with Datadog instrumentation")
    changes_made: List[str] = Field(description="List of specific changes made to each Lambda function")
    instrumentation_type: Literal["datadog_lambda_instrumentation"] = Field(
        description="Type of instrumentation added",
        default="datadog_lambda_instrumentation"
    )

class FunctionInstrumenter:
    """Class responsible for instrumenting AWS Lambda functions with Datadog."""
    
    def __init__(self, llm: ChatOpenAI):
        """
        Initialize the FunctionInstrumenter.
        
        Args:
            llm: ChatOpenAI instance for code analysis and modification
        """
        self.llm = llm
        self.logger = logging.getLogger(__name__)
        
        # Create output parser
        self.output_parser = PydanticOutputParser(pydantic_object=InstrumentationResult)
        
        # Initialize prompts for different types of instrumentation
        self.cdk_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert at instrumenting AWS CDK code with Datadog.
            Your task is to analyze and modify CDK code to add Datadog instrumentation to all Lambda functions.
            
            Key requirements:
            - Add Datadog Lambda Extension layer to all Lambda functions
            - Add Datadog Tracing layer to all Lambda functions
            - Set DD_ENV, DD_SERVICE, and DD_VERSION environment variables
            - Add necessary imports for Datadog
            - Ensure proper error handling
            - Maintain existing functionality
            - Follow AWS CDK best practices
            
            For each Lambda function, you must:
            1. Add the Datadog Lambda Extension layer (arn:aws:lambda:{region}:464622532012:layer:Datadog-Extension:latest)
            2. Add the Datadog Tracing layer (arn:aws:lambda:{region}:464622532012:layer:dd-trace-py:latest)
            3. Set environment variables:
               - DD_ENV: based on the stack environment
               - DD_SERVICE: based on the function name
               - DD_VERSION: based on the stack version or '1.0.0' if not specified
            
            You must respond with ONLY a JSON object containing:
            {
                "modified_code": "the complete modified code with Datadog instrumentation",
                "changes_made": ["list of specific changes made to each Lambda function"],
                "instrumentation_type": "datadog_lambda_instrumentation"
            }
            """),
            ("human", "Instrument this CDK code with Datadog:\n{code}")
        ])
        
        self.terraform_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert at instrumenting Terraform code with Datadog.
            Your task is to analyze and modify Terraform code to add Datadog instrumentation to all Lambda functions.
            
            Key requirements:
            - Add Datadog Lambda Extension layer to all Lambda functions
            - Add Datadog Tracing layer to all Lambda functions
            - Set DD_ENV, DD_SERVICE, and DD_VERSION environment variables
            - Add necessary provider configurations
            - Ensure proper error handling
            - Maintain existing functionality
            - Follow Terraform best practices
            
            For each Lambda function, you must:
            1. Add the Datadog Lambda Extension layer (arn:aws:lambda:{region}:464622532012:layer:Datadog-Extension:latest)
            2. Add the Datadog Tracing layer (arn:aws:lambda:{region}:464622532012:layer:dd-trace-py:latest)
            3. Set environment variables:
               - DD_ENV: based on the environment variable or 'dev' if not specified
               - DD_SERVICE: based on the function name
               - DD_VERSION: based on the version variable or '1.0.0' if not specified
            
            You must respond with ONLY a JSON object containing:
            {
                "modified_code": "the complete modified code with Datadog instrumentation",
                "changes_made": ["list of specific changes made to each Lambda function"],
                "instrumentation_type": "datadog_lambda_instrumentation"
            }
            """),
            ("human", "Instrument this Terraform code with Datadog:\n{code}")
        ])
        
        # Create chains for CDK and Terraform instrumentation
        self.cdk_chain = LLMChain(
            llm=self.llm,
            prompt=self.cdk_prompt,
            output_parser=self.output_parser,
            verbose=True
        )
        
        self.terraform_chain = LLMChain(
            llm=self.llm,
            prompt=self.terraform_prompt,
            output_parser=self.output_parser,
            verbose=True
        )
    
    def instrument_cdk_file(self, cdk_script_file: Document, dd_documentation: Dict[str, DocSection]) -> InstrumentationResult:
        """
        Instrument a CDK file with Datadog Lambda instrumentation.
        
        Args:
            file_path: Path to the CDK file
            code: Content of the CDK file
            
        Returns:
            InstrumentationResult containing the modified code and change information
        """
        try:
            result = self.cdk_chain.invoke({"code": cdk_script_file.page_content})
            self.logger.info(f"Successfully instrumented CDK file with Datadog: {cdk_script_file.metadata['source']}")
            return result
        except Exception as e:
            self.logger.error(f"Error instrumenting CDK file {cdk_script_file.metadata['source']}: {str(e)}")
            raise
    
    def instrument_terraform_file(self, file_path: str, code: str) -> InstrumentationResult:
        """
        Instrument a Terraform file with Datadog Lambda instrumentation.
        
        Args:
            file_path: Path to the Terraform file
            code: Content of the Terraform file
            
        Returns:
            InstrumentationResult containing the modified code and change information
        """
        try:
            result = self.terraform_chain.invoke({"code": code})
            self.logger.info(f"Successfully instrumented Terraform file with Datadog: {file_path}")
            return result
        except Exception as e:
            self.logger.error(f"Error instrumenting Terraform file {file_path}: {str(e)}")
            raise 