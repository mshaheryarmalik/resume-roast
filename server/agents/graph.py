"""Multi-agent workflow orchestration using LangGraph."""

import logging
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Dict, List, Tuple

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
    
    Architecture:
    - Uses LangGraph StateGraph (self.workflow) to define agent structure
    - Implements workflow-guided streaming in execute_debate() for real-time UX
    - Maintains state management following LangGraph patterns
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
    
    def _get_agent_prompt_and_message(
        self,
        agent_name: str,
        state: AgentState
    ) -> Tuple[str, str]:
        """Get prompt and message for an agent.
        
        Single source of truth for agent prompt generation logic.
        Used by both workflow nodes and streaming execution.
        
        Args:
            agent_name: Name of agent ("critic", "advocate", "realist")
            state: Current workflow state
            
        Returns:
            Tuple of (system_prompt, user_message)
        """
        if agent_name == "critic":
            prompt = self.critic.get_system_prompt(state["memory_context"])
            message = self.critic.format_user_message(
                state["resume_text"],
                state["job_description"]
            )
            return prompt, message
            
        elif agent_name == "advocate":
            prompt = self.advocate.get_system_prompt(state["memory_context"])
            message = self.advocate.format_user_message(
                state["resume_text"],
                state["job_description"]
            )
            return prompt, message
            
        elif agent_name == "realist":
            prompt = self.realist.get_system_prompt(state["memory_context"])
            message = self.realist.format_user_message(
                state["resume_text"],
                state["job_description"],
                state["critic_response"],
                state["advocate_response"]
            )
            return prompt, message
        
        raise ValueError(f"Unknown agent: {agent_name}")
    
    def _create_workflow(self) -> StateGraph:
        """Create the LangGraph workflow for agent orchestration.
        
        This workflow defines the structure and execution order of agents:
        - Entry point: Critic
        - Flow: Critic -> Advocate -> Realist -> END
        
        Note: While this compiled workflow serves as the architectural blueprint,
        actual execution happens in execute_debate() with token-level streaming
        to maintain real-time UX. The nodes defined here mirror the logic in
        _execute_node_with_streaming() to ensure consistency.
        """
        
        async def critic_node(state: AgentState) -> AgentState:
            """Execute critic agent and update state."""
            prompt, message = self._get_agent_prompt_and_message("critic", state)
            response = await self.llm_service.generate_complete_response(
                prompt, message, state["memory_context"]
            )
            state["critic_response"] = response
            state["current_agent"] = "Critic"
            return state
        
        async def advocate_node(state: AgentState) -> AgentState:
            """Execute advocate agent and update state."""
            prompt, message = self._get_agent_prompt_and_message("advocate", state)
            response = await self.llm_service.generate_complete_response(
                prompt, message, state["memory_context"]
            )
            state["advocate_response"] = response
            state["current_agent"] = "Advocate"
            return state
        
        async def realist_node(state: AgentState) -> AgentState:
            """Execute realist agent and update state."""
            prompt, message = self._get_agent_prompt_and_message("realist", state)
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
    
    async def _execute_node_with_streaming(
        self,
        node_name: str,
        state: AgentState
    ) -> AsyncGenerator[str, None]:
        """
        Execute a workflow node with real-time token streaming.
        
        This method bridges the workflow structure with streaming requirements,
        executing nodes as defined in self.workflow while streaming LLM tokens.
        
        Args:
            node_name: Name of the node to execute ("critic", "advocate", "realist")
            state: Current workflow state
            
        Yields:
            Token chunks from the LLM response
            
        Updates:
            state: Modifies state in place with agent response
        """
        # Get prompt and message using shared logic
        prompt, message = self._get_agent_prompt_and_message(node_name, state)
        agent_name = node_name.capitalize()
        
        # Stream response from LLM
        response = ""
        async for chunk in self.llm_service.generate_agent_response(
            prompt, message, agent_name, state["memory_context"]
        ):
            response += chunk
            yield chunk
        
        # Update state as workflow node would
        state[f"{node_name}_response"] = response
        state["current_agent"] = agent_name
    
    async def execute_debate(
        self, 
        resume_text: str, 
        job_description: str,
        memory_context: List[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Execute the multi-agent debate workflow with streaming responses.
        
        This method follows the workflow structure defined in self.workflow
        (critic -> advocate -> realist) while maintaining real-time token streaming
        for optimal frontend UX.
        
        Args:
            resume_text: Extracted resume text
            job_description: Job description to match against
            memory_context: Aggregated learnings from previous sessions
            
        Yields:
            Dictionary containing agent name, response chunk, and metadata
        """
        if memory_context is None:
            memory_context = []
        
        # Initialize state following workflow's AgentState structure
        state: AgentState = {
            "resume_text": resume_text,
            "job_description": job_description,
            "critic_response": "",
            "advocate_response": "",
            "realist_response": "",
            "memory_context": memory_context,
            "current_agent": "",
        }
        
        # Execute workflow nodes in order defined by self.workflow
        # Node 1: Critic (entry point as per workflow.set_entry_point("critic"))
        yield {"agent_name": "Critic", "chunk": "", "is_complete": False, "order": 1}
        
        async for chunk in self._execute_node_with_streaming("critic", state):
            yield {
                "agent_name": "Critic", 
                "chunk": chunk, 
                "is_complete": False, 
                "order": 1
            }
        
        yield {"agent_name": "Critic", "chunk": "", "is_complete": True, "order": 1}
        
        # Node 2: Advocate (as per workflow.add_edge("critic", "advocate"))
        yield {"agent_name": "Advocate", "chunk": "", "is_complete": False, "order": 2}
        
        async for chunk in self._execute_node_with_streaming("advocate", state):
            yield {
                "agent_name": "Advocate", 
                "chunk": chunk, 
                "is_complete": False, 
                "order": 2
            }
        
        yield {"agent_name": "Advocate", "chunk": "", "is_complete": True, "order": 2}
        
        # Node 3: Realist (as per workflow.add_edge("advocate", "realist"))
        yield {"agent_name": "Realist", "chunk": "", "is_complete": False, "order": 3}
        
        async for chunk in self._execute_node_with_streaming("realist", state):
            yield {
                "agent_name": "Realist", 
                "chunk": chunk, 
                "is_complete": False, 
                "order": 3
            }
        
        yield {"agent_name": "Realist", "chunk": "", "is_complete": True, "order": 3}
        
        # Workflow complete (as per workflow.add_edge("realist", END))
        yield {
            "agent_name": "Workflow", 
            "chunk": "", 
            "is_complete": True, 
            "order": 4,
            "results": AgentWorkflowResult(
                critic_response=state["critic_response"],
                advocate_response=state["advocate_response"],
                realist_response=state["realist_response"]
            )
        }