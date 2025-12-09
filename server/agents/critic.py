"""Critic agent for harsh but constructive resume critique."""

from typing import List, Optional


class CriticAgent:
    """Agent that provides critical analysis of resumes.
    
    The Critic focuses on identifying the most critical issues
    in a resume that could prevent it from being effective.
    """
    
    def __init__(self) -> None:
        """Initialize the Critic agent."""
        self.name = "Critic"
        self.order = 1
    
    def get_system_prompt(self, memory_context: Optional[List[str]] = None) -> str:
        """
        Get the system prompt for the Critic agent.
        
        Args:
            memory_context: Previous learning patterns from feedback
            
        Returns:
            System prompt string
        """
        base_prompt = """You are the Critic. Identify ONLY the top 3 critical resume issues.

Be direct and specific. Maximum 100 words total.

Format:
1. [Issue] - [Why it matters] - [Quick fix]
2. [Issue] - [Why it matters] - [Quick fix] 
3. [Issue] - [Why it matters] - [Quick fix]

Focus on: Missing keywords, weak language, experience gaps."""
        
        if memory_context:
            memory_section = "\n\nBased on previous feedback patterns:\n" + "\n".join(memory_context)
            return base_prompt + memory_section
        
        return base_prompt
    
    def format_user_message(self, resume_text: str, job_description: str) -> str:
        """
        Format the user message with resume and job description.
        
        Args:
            resume_text: Extracted resume text
            job_description: Target job description
            
        Returns:
            Formatted message for the LLM
            
        Raises:
            ValueError: If inputs are empty
        """
        if not resume_text or not resume_text.strip():
            raise ValueError("Resume text cannot be empty")
        if not job_description or not job_description.strip():
            raise ValueError("Job description cannot be empty")
        return f"""
JOB DESCRIPTION:
{job_description}

RESUME TO CRITIQUE:
{resume_text}

Provide your critical analysis focusing on what would prevent this resume from succeeding for this specific role.
"""