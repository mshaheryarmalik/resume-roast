"""Advocate agent for highlighting resume strengths."""

from typing import List, Optional


class AdvocateAgent:
    """Agent that advocates for the candidate and highlights strengths.
    
    The Advocate focuses on identifying and emphasizing the candidate's
    strengths, achievements, and potential value to employers.
    """
    
    def __init__(self) -> None:
        """Initialize the Advocate agent."""
        self.name = "Advocate"
        self.order = 2
    
    def get_system_prompt(self, memory_context: Optional[List[str]] = None) -> str:
        """
        Get the system prompt for the Advocate agent.
        
        Args:
            memory_context: Previous learning patterns from feedback
            
        Returns:
            System prompt string
        """
        base_prompt = """You are the Advocate - an enthusiastic career coach. Highlight this candidate's top 3 strengths.

Focus on:
- Unique achievements and skills
- Transferable experience  
- Growth potential

Be encouraging and specific. Keep response under 150 words.
End with why they'd be a great fit for the role."""
        
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

RESUME TO ADVOCATE FOR:
{resume_text}

Identify and highlight all the strengths, achievements, and positive aspects that make this candidate attractive for this role.
"""