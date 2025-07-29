#!/usr/bin/env python3
"""
AWS Integration Module for A2A MCP

This module handles integration with Amazon's models via LiteLLM.
"""

import os
from typing import Tuple, Any, Optional

def validate_aws_setup() -> Tuple[bool, Optional[Any]]:
    """
    Validate AWS setup and return integration module.
    
    Returns:
        Tuple[bool, Optional[Any]]: (is_valid, integration_module)
    """
    required_vars = [
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY", 
        "AWS_REGION_NAME"
    ]
    
    # Check all required environment variables
    for var in required_vars:
        if not os.getenv(var):
            return False, None
    
    return True, AWSIntegration()

class AWSIntegration:
    """Handles AWS model integration via LiteLLM."""
    
    def __init__(self):
        self.access_key = os.getenv("AWS_ACCESS_KEY_ID")
        self.secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        self.region = os.getenv("AWS_REGION_NAME")
        self.client_type = os.getenv("AWS_CLIENT_TYPE", "bedrock")
    
    def get_model(self, model_name: str) -> str:
        """
        Get the AWS model configuration for LiteLLM.
        
        Args:
            model_name: The model name from agent card (e.g., "amazon.nova-lite-v1:0")
            
        Returns:
            str: Model identifier for LiteLLM
        """
        # Handle various model name formats
        if model_name.startswith("amazon."):
            # Already in correct format
            bedrock_model = model_name
        elif model_name.startswith("nova"):
            # Convert nova-lite to amazon.nova-lite-v1:0 format
            bedrock_model = f"amazon.{model_name}-v1:0"
        else:
            # Default to nova-lite if unrecognized
            bedrock_model = "amazon.nova-lite-v1:0"
            
        return f"bedrock/{bedrock_model}"
    
    def print_integration_info(self, model_name: str) -> None:
        """Print information about the AWS integration."""
        print("\n🤖 AWS Integration Information:")
        print(f"  • Model: {model_name}")
        print(f"  • Region: {self.region}")
        print("  • Provider: Amazon AWS")
        print("  • Integration: LiteLLM")
        print("  • Status: Active\n") 