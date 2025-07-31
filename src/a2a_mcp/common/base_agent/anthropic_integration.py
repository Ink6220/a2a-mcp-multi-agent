#!/usr/bin/env python3
"""
Anthropic Integration Module for A2A MCP

This module handles integration with Anthropic's Claude models via LiteLLM.
"""

import os
from typing import Tuple, Any, Optional

def validate_anthropic_setup() -> Tuple[bool, Optional[Any]]:
    """
    Validate Anthropic API setup and return integration module.
    
    Returns:
        Tuple[bool, Optional[Any]]: (is_valid, integration_module)
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    
    if not api_key:
        return False, None
    
    return True, AnthropicIntegration()

class AnthropicIntegration:
    """Handles Anthropic model integration via LiteLLM."""
    
    def __init__(self):
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
    
    def get_model(self, model_name: str) -> str:
        """
        Get the Anthropic model configuration for LiteLLM.
        
        Args:
            model_name: The model name from agent card (e.g., "claude-3-haiku")
            
        Returns:
            str: Model identifier for LiteLLM
        """
        # Handle various model name formats
        if model_name.startswith("claude-"):
            # Use model name as-is for Anthropic models
            claude_model = model_name
        else:
            # Default to claude-3-haiku if unrecognized
            claude_model = "claude-3-haiku-20240307"
            
        return f"litellm/anthropic/{claude_model}"
    
    def print_integration_info(self, model_name: str) -> None:
        """Print information about the Anthropic integration."""
        print("\n🤖 Anthropic Integration Information:")
        print(f"  • Model: {model_name}")
        print("  • Provider: Anthropic")
        print("  • Integration: LiteLLM")
        print("  • Status: Active\n") 