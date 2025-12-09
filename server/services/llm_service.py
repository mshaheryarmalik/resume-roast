"""LLM service for Azure OpenAI API interactions."""

import logging
from typing import AsyncGenerator, List, Optional

import openai
from openai import AsyncAzureOpenAI

from config import get_settings

logger = logging.getLogger(__name__)


class LLMService:
    """Service responsible for Azure OpenAI API interactions.
    
    This service handles all interactions with the Azure OpenAI API,
    including streaming and non-streaming completions with proper
    error handling and token validation.
    """
    
    def __init__(self) -> None:
        """Initialize the LLM service with Azure OpenAI client."""
        self.settings = get_settings()
        self.client = AsyncAzureOpenAI(
            api_key=self.settings.azure_openai_api_key,
            azure_endpoint=self.settings.azure_openai_endpoint,
            api_version=self.settings.azure_openai_api_version,
        )
    
    async def generate_agent_response(
        self,
        system_prompt: str,
        user_message: str,
        agent_name: str,
        memory_context: Optional[List[str]] = None
    ) -> AsyncGenerator[str, None]:
        """
        Generate streaming response from OpenAI for a specific agent.
        
        Args:
            system_prompt: System prompt defining agent behavior
            user_message: User input (resume + job description)
            agent_name: Name of the agent for logging
            memory_context: List of aggregated learnings for context
            
        Yields:
            String chunks from the streaming response
            
        Raises:
            RuntimeError: If API call fails
        """
        try:
            messages = [{"role": "system", "content": system_prompt}]
            
            # Add memory context if available
            if memory_context:
                memory_text = "\n".join(memory_context)
                messages.append({
                    "role": "system", 
                    "content": f"Based on previous feedback, consider these patterns:\n{memory_text}"
                })
            
            messages.append({"role": "user", "content": user_message})
            
            stream = await self.client.chat.completions.create(
                model=self.settings.azure_openai_deployment,
                messages=messages,
                max_completion_tokens=self.settings.openai_max_tokens,
                temperature=0.7,
                stream=True
            )
            
            async for chunk in stream:
                if hasattr(chunk, 'choices') and chunk.choices:
                    choice = chunk.choices[0]
                    if hasattr(choice, 'delta') and choice.delta and hasattr(choice.delta, 'content') and choice.delta.content:
                        yield choice.delta.content
                    
        except openai.APIError as e:
            logger.error("OpenAI API error for %s: %s", agent_name, str(e))
            raise RuntimeError(f"OpenAI API error for {agent_name}: {str(e)}")
        except openai.RateLimitError as e:
            logger.error("Rate limit exceeded for %s: %s", agent_name, str(e))
            raise RuntimeError(f"OpenAI rate limit exceeded for {agent_name}: {str(e)}")
        except openai.AuthenticationError as e:
            logger.error("Authentication error for %s: %s", agent_name, str(e))
            raise RuntimeError(f"OpenAI authentication error for {agent_name}: {str(e)}")
        except Exception as e:
            logger.error("Unexpected error for %s: %s", agent_name, str(e))
            raise RuntimeError(f"Unexpected error with OpenAI for {agent_name}: {str(e)}")
    
    async def generate_complete_response(
        self,
        system_prompt: str,
        user_message: str,
        memory_context: Optional[List[str]] = None
    ) -> str:
        """
        Generate complete (non-streaming) response from OpenAI.
        
        Args:
            system_prompt: System prompt defining behavior
            user_message: User input
            memory_context: List of aggregated learnings for context
            
        Returns:
            Complete response text
            
        Raises:
            RuntimeError: If API call fails
        """
        try:
            messages = [{"role": "system", "content": system_prompt}]
            
            # Add memory context if available
            if memory_context:
                memory_text = "\n".join(memory_context)
                messages.append({
                    "role": "system", 
                    "content": f"Based on previous feedback, consider these patterns:\n{memory_text}"
                })
            
            messages.append({"role": "user", "content": user_message})
            
            response = await self.client.chat.completions.create(
                model=self.settings.azure_openai_deployment,
                messages=messages,
                max_completion_tokens=self.settings.openai_max_tokens,
                temperature=0.7,
                stream=False
            )
            
            return response.choices[0].message.content if response.choices else ""
            
        except openai.APIError as e:
            raise RuntimeError(f"OpenAI API error: {str(e)}")
        except openai.RateLimitError as e:
            raise RuntimeError(f"OpenAI rate limit exceeded: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Unexpected error with OpenAI: {str(e)}")
    
    def validate_token_count(self, text: str, limit: int, context: str) -> None:
        """
        Validate text doesn't exceed token limit.
        
        Args:
            text: Text to validate
            limit: Token limit
            context: Context for error message (e.g., "resume", "job description")
            
        Raises:
            ValueError: If text exceeds token limit
        """
        # Rough estimation: 1 token ≈ 0.75 words
        estimated_tokens = len(text.split()) * 1.33
        
        if estimated_tokens > limit:
            raise ValueError(
                f"{context} is too long: approximately {int(estimated_tokens)} tokens "
                f"(limit: {limit})"
            )
    
    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for given text.
        
        Args:
            text: Text to estimate tokens for
            
        Returns:
            Estimated token count
        """
        # Rough estimation: 1 token ≈ 0.75 words
        return int(len(text.split()) * 1.33)