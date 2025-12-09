"""Multi-agent workflow orchestration using LangGraph."""

import logging
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Dict, List

from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

from services import LLMService

from .advocate import AdvocateAgent
from .critic import CriticAgent
from .realist import RealistAgent

logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    """State shared between agents in the workflow."""
    resume_text: str
    job_description: str
    critic_response: str
    advocate_response: str
    realist_response: str
    memory_context: List[str]
    current_agent: str


@dataclass
class AgentWorkflowResult:
    """Result from agent workflow execution."""
    critic_response: str
    advocate_response: str
    realist_response: str


class AgentOrchestrator:
    """Orchestrates the multi-agent debate workflow.
    
    This class coordinates the execution of multiple AI agents
    (Critic, Advocate, Realist) in a structured debate format
    to provide comprehensive resume feedback.
    """
    
    def __init__(self, llm_service: LLMService) -> None:
        """Initialize the orchestrator with required services."""
        if not llm_service:
            raise ValueError("LLM service is required")
            
        self.llm_service = llm_service
        self.critic = CriticAgent()
        self.advocate = AdvocateAgent()
        self.realist = RealistAgent()
        self.workflow = self._create_workflow()
    
    def _create_workflow(self) -> StateGraph:
        """Create the LangGraph workflow for agent orchestration."""
        
        async def critic_node(state: AgentState) -> AgentState:
            """Execute critic agent and update state."""
            prompt = self.critic.get_system_prompt(state["memory_context"])
            message = self.critic.format_user_message(
                state["resume_text"], 
                state["job_description"]
            )
            
            response = await self.llm_service.generate_complete_response(
                prompt, message, state["memory_context"]
            )
            
            state["critic_response"] = response
            state["current_agent"] = "Critic"
            return state
        
        async def advocate_node(state: AgentState) -> AgentState:
            """Execute advocate agent and update state."""
            prompt = self.advocate.get_system_prompt(state["memory_context"])
            message = self.advocate.format_user_message(
                state["resume_text"], 
                state["job_description"]
            )
            
            response = await self.llm_service.generate_complete_response(
                prompt, message, state["memory_context"]
            )
            
            state["advocate_response"] = response
            state["current_agent"] = "Advocate"
            return state
        
        async def realist_node(state: AgentState) -> AgentState:
            """Execute realist agent and update state."""
            prompt = self.realist.get_system_prompt(state["memory_context"])
            message = self.realist.format_user_message(
                state["resume_text"], 
                state["job_description"],
                state["critic_response"],
                state["advocate_response"]
            )
            
            response = await self.llm_service.generate_complete_response(
                prompt, message, state["memory_context"]
            )
            
            state["realist_response"] = response
            state["current_agent"] = "Realist"
            return state
        
        # Create workflow
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("critic", critic_node)
        workflow.add_node("advocate", advocate_node)
        workflow.add_node("realist", realist_node)
        
        # Define edges
        workflow.set_entry_point("critic")
        workflow.add_edge("critic", "advocate")
        workflow.add_edge("advocate", "realist")
        workflow.add_edge("realist", END)
        
        return workflow.compile()
    
    async def execute_debate(
        self, 
        resume_text: str, 
        job_description: str,
        memory_context: List[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Execute the multi-agent debate workflow with streaming responses.
        
        Args:
            resume_text: Extracted resume text
            job_description: Job description to match against
            memory_context: Aggregated learnings from previous sessions
            
        Yields:
            Dictionary containing agent name, response chunk, and metadata
        """
        if memory_context is None:
            memory_context = []
        
        # Initialize state
        initial_state: AgentState = {
            "resume_text": resume_text,
            "job_description": job_description,
            "critic_response": "",
            "advocate_response": "",
            "realist_response": "",
            "memory_context": memory_context,
            "current_agent": "",
        }
        
        # Execute Critic
        yield {"agent_name": "Critic", "chunk": "", "is_complete": False, "order": 1}
        
        critic_prompt = self.critic.get_system_prompt(memory_context)
        critic_message = self.critic.format_user_message(resume_text, job_description)
        critic_response = ""
        
        async for chunk in self.llm_service.generate_agent_response(
            critic_prompt, critic_message, "Critic", memory_context
        ):
            critic_response += chunk
            yield {
                "agent_name": "Critic", 
                "chunk": chunk, 
                "is_complete": False, 
                "order": 1
            }
        
        yield {"agent_name": "Critic", "chunk": "", "is_complete": True, "order": 1}
        
        # Execute Advocate
        yield {"agent_name": "Advocate", "chunk": "", "is_complete": False, "order": 2}
        
        advocate_prompt = self.advocate.get_system_prompt(memory_context)
        advocate_message = self.advocate.format_user_message(resume_text, job_description)
        advocate_response = ""
        
        async for chunk in self.llm_service.generate_agent_response(
            advocate_prompt, advocate_message, "Advocate", memory_context
        ):
            advocate_response += chunk
            yield {
                "agent_name": "Advocate", 
                "chunk": chunk, 
                "is_complete": False, 
                "order": 2
            }
        
        yield {"agent_name": "Advocate", "chunk": "", "is_complete": True, "order": 2}
        
        # Execute Realist
        yield {"agent_name": "Realist", "chunk": "", "is_complete": False, "order": 3}
        
        realist_prompt = self.realist.get_system_prompt(memory_context)
        realist_message = self.realist.format_user_message(
            resume_text, job_description, critic_response, advocate_response
        )
        realist_response = ""
        
        async for chunk in self.llm_service.generate_agent_response(
            realist_prompt, realist_message, "Realist", memory_context
        ):
            realist_response += chunk
            yield {
                "agent_name": "Realist", 
                "chunk": chunk, 
                "is_complete": False, 
                "order": 3
            }
        
        yield {"agent_name": "Realist", "chunk": "", "is_complete": True, "order": 3}
        
        # Final workflow complete signal
        yield {
            "agent_name": "Workflow", 
            "chunk": "", 
            "is_complete": True, 
            "order": 4,
            "results": AgentWorkflowResult(
                critic_response=critic_response,
                advocate_response=advocate_response,
                realist_response=realist_response
            )
        }