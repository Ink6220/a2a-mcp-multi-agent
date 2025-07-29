#!/usr/bin/env python3
"""
OpenAI Integration Module for A2A MCP

This module handles integration with OpenAI's models via LiteLLM.
"""

import os
from typing import Tuple, Any, Optional

def validate_openai_setup() -> Tuple[bool, Optional[Any]]:
    """
    Validate OpenAI API setup and return integration module.
    
    Returns:
        Tuple[bool, Optional[Any]]: (is_valid, integration_module)
    """
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        return False, None
    
    return True, OpenAIIntegration()

class OpenAIIntegration:
    """Handles OpenAI model integration via LiteLLM."""
    
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
    
    def get_model(self, model_name: str) -> str:
        """
        Get the OpenAI model configuration for LiteLLM.
        
        Args:
            model_name: The model name from agent card (e.g., "gpt-4.1-mini")
            
        Returns:
            str: Model identifier for LiteLLM
        """
        # Handle various model name formats
        if model_name.startswith("gpt-"):
            # Use model name as-is for OpenAI models
            openai_model = model_name
        else:
            # Default to gpt-4o-mini if unrecognized
            openai_model = "gpt-4o-mini"
            
        return f"openai/{openai_model}"
    
    def print_integration_info(self, model_name: str) -> None:
        """Print information about the OpenAI integration."""
        print("\n🤖 OpenAI Integration Information:")
        print(f"  • Model: {model_name}")
        print("  • Provider: OpenAI")
        print("  • Integration: LiteLLM")
        print("  • Status: Active\n") 