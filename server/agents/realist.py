"""Realist agent for balanced resume assessment."""

from typing import List, Optional


class RealistAgent:
    """Agent that provides balanced, realistic assessment and actionable recommendations.
    
    The Realist synthesizes feedback from both Critic and Advocate agents
    to provide practical, balanced recommendations for improvement.
    """
    
    def __init__(self) -> None:
        """Initialize the Realist agent."""
        self.name = "Realist"
        self.order = 3
    
    def get_system_prompt(self, memory_context: Optional[List[str]] = None) -> str:
        """
        Get the system prompt for the Realist agent.
        
        Args:
            memory_context: Previous learning patterns from feedback
            
        Returns:
            System prompt string
        """
        base_prompt = """You are the Realist - a pragmatic hiring manager. Provide 3 specific, actionable recommendations.

Balance the Critic's concerns with the Advocate's strengths:
- Prioritize high-impact changes
- Give practical next steps
- Consider market realities

Keep response under 150 words.
End with one key positioning strategy for this role."""
        
        if memory_context:
            memory_section = "\n\nBased on previous feedback patterns:\n" + "\n".join(memory_context)
            return base_prompt + memory_section
        
        return base_prompt
    
    def format_user_message(self, resume_text: str, job_description: str, critic_response: str, advocate_response: str) -> str:
        """
        Format the user message including previous agent responses.
        
        Args:
            resume_text: Extracted resume text
            job_description: Target job description
            critic_response: Critic agent's response
            advocate_response: Advocate agent's response
            
        Returns:
            Formatted message for the LLM
            
        Raises:
            ValueError: If any input is empty
        """
        if not resume_text or not resume_text.strip():
            raise ValueError("Resume text cannot be empty")
        if not job_description or not job_description.strip():
            raise ValueError("Job description cannot be empty")
        if not critic_response or not critic_response.strip():
            raise ValueError("Critic response cannot be empty")
        if not advocate_response or not advocate_response.strip():
            raise ValueError("Advocate response cannot be empty")
            
        return f"""
JOB DESCRIPTION:
{job_description}

RESUME:
{resume_text}

CRITIC'S ANALYSIS:
{critic_response}

ADVOCATE'S PERSPECTIVE:
{advocate_response}

Now provide your balanced, realistic assessment with specific actionable recommendations.
"""