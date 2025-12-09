"""Simple chatbot interface built with NiceGUI for Resume Roast demo."""

import asyncio
import json
import logging
import os
from typing import Dict, Optional, Set

import httpx
from nicegui import run, ui

logger = logging.getLogger(__name__)


class ResumeRoastUI:
    """Main UI class for Resume Roast chatbot interface.
    
    This class provides a web-based interface for users to upload
    resumes and receive AI-powered feedback through a chat interface.
    """
    
    def __init__(self) -> None:
        """Initialize the Resume Roast UI."""
        self.api_base_url = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")
        self.current_session_id: Optional[str] = None
        self.agents_completed: Set[str] = set()
        
        # UI components
        self.chat_container = None
        self.feedback_buttons: Dict[str, Dict] = {}
        self.upload_area = None
        self.job_description_input = None
        
    def setup_theme(self) -> None:
        """Configure corporate blue theme."""
        ui.colors(
            primary='#1976D2',  # Corporate blue
            secondary='#424242',  # Dark gray
            accent='#82B1FF',   # Light blue
            positive='#4CAF50',  # Green for success
            negative='#F44336',  # Red for errors
            info='#2196F3',     # Blue for info
            warning='#FF9800'   # Orange for warnings
        )
        
        ui.dark_mode(False)  # Light mode
    
    def create_header(self) -> None:
        """Create application header."""
        with ui.row().classes('w-full justify-between items-center p-6 bg-gradient-to-r from-blue-600 to-blue-800 text-white shadow-lg'):
            with ui.column().classes('gap-1'):
                ui.label('💼 Resume Roast').classes('text-3xl font-bold')
                ui.label('AI-Powered Professional Resume Analysis').classes('text-sm opacity-90')
    
    async def handle_file_upload(self, e):
        """Handle PDF file upload."""
        try:
            # In NiceGUI, the upload event provides the file via e.file, filename via e.file.name
            filename = e.file.name
            
            if not filename.lower().endswith('.pdf'):
                ui.notify('Please upload a PDF file only.', type='negative')
                return
            
            # Get job description
            job_description = self.job_description_input.value.strip()
            if not job_description:
                ui.notify('Please enter a job description first.', type='warning')
                return
            
            # Show processing message
            with self.chat_container:
                ui.chat_message(
                    f'Uploaded: {filename}',
                    name='You',
                    sent=True
                ).classes('mb-2')
                
                loading_msg = ui.chat_message(
                    'Processing your resume... Please wait.',
                    name='System',
                    sent=False
                ).classes('mb-2')
            
            # Upload to API
            async with httpx.AsyncClient(timeout=30.0) as client:
                file_content = await e.file.read()
                files = {'file': (filename, file_content, 'application/pdf')}
                data = {'job_description': job_description}
                
                response = await client.post(
                    f"{self.api_base_url}/upload-resume",
                    files=files,
                    data=data
                )
                
                if response.status_code == 200:
                    result = response.json()
                    self.current_session_id = result['session_id']
                    
                    # Remove loading message
                    loading_msg.delete()
                    
                    with self.chat_container:
                        ui.chat_message(
                            '✅ Resume uploaded successfully! Starting AI analysis...',
                            name='System',
                            sent=False
                        ).classes('mb-2')
                    
                    # Start streaming analysis
                    await self.stream_agent_responses()
                    
                else:
                    error_data = response.json()
                    loading_msg.content = f'❌ Upload failed: {error_data.get("detail", "Unknown error")}'
                    ui.notify('Upload failed. Please try again.', type='negative')
        
        except Exception as ex:
            ui.notify(f'Error uploading file: {str(ex)}', type='negative')
    
    async def stream_agent_responses(self):
        """Stream agent responses from the API."""
        if not self.current_session_id:
            return
        
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream(
                    'GET', 
                    f"{self.api_base_url}/stream-analysis/{self.current_session_id}"
                ) as response:
                    
                    if response.status_code != 200:
                        ui.notify('Failed to start analysis stream.', type='negative')
                        return
                    
                    current_agents = {}
                    agent_contents = {}  # Store accumulated content
                    
                    async for line in response.aiter_lines():
                        if line.startswith('data: '):
                            try:
                                data = json.loads(line[6:])  # Remove 'data: ' prefix
                                
                                if data.get('error'):
                                    with self.chat_container:
                                        ui.chat_message(
                                            f'Error: {data["message"]}',
                                            name='System',
                                            sent=False
                                        )
                                    break
                                
                                agent_name = data.get('agent_name')
                                chunk = data.get('chunk', '')
                                is_complete = data.get('is_complete', False)
                                
                                if agent_name and agent_name != 'Workflow':
                                    # Initialize agent message if not exists
                                    if agent_name not in current_agents:
                                        # Initialize content accumulator
                                        agent_contents[agent_name] = ""
                                        
                                        with self.chat_container:
                                            # Agent emoji mapping
                                            emoji = {'Critic': '🔍', 'Advocate': '💪', 'Realist': '⚖️'}.get(agent_name, '🤖')
                                            
                                            # Create container for agent response with professional styling
                                            with ui.card().classes('w-full mb-4 p-6 shadow-lg border-l-4 border-blue-500 bg-white'):
                                                ui.label(f'{emoji} {agent_name}').classes('font-semibold text-xl mb-3 text-gray-800')
                                                current_agents[agent_name] = ui.markdown('').classes('w-full text-gray-700 prose max-w-none')
                                    
                                    # Accumulate and update message content
                                    if chunk:
                                        agent_contents[agent_name] += chunk
                                        # Update markdown content
                                        current_agents[agent_name].content = agent_contents[agent_name]
                                    
                                    # Add feedback buttons when agent completes
                                    if is_complete and agent_name not in self.agents_completed:
                                        self.agents_completed.add(agent_name)
                                        # Add feedback buttons below the agent response
                                        with self.chat_container:
                                            with ui.row().classes('justify-end mt-2 mb-4 gap-2'):
                                                ui.label('Was this helpful?').classes('text-sm text-gray-600 self-center')
                                                
                                                thumbs_up_btn = ui.button(
                                                    '👍', 
                                                    on_click=lambda an=agent_name: asyncio.create_task(self.submit_feedback(an, True))
                                                ).classes('px-3 py-1 bg-gray-200 hover:bg-green-500 hover:text-white rounded-full text-sm transition-colors')
                                                
                                                thumbs_down_btn = ui.button(
                                                    '👎', 
                                                    on_click=lambda an=agent_name: asyncio.create_task(self.submit_feedback(an, False))
                                                ).classes('px-3 py-1 bg-gray-200 hover:bg-red-500 hover:text-white rounded-full text-sm transition-colors')
                                                
                                                # Store button references for state updates
                                                self.feedback_buttons[agent_name] = {
                                                    'up': thumbs_up_btn,
                                                    'down': thumbs_down_btn
                                                }
                                
                                # Check if workflow is complete
                                if agent_name == 'Workflow' and is_complete:
                                    with self.chat_container:
                                        with ui.card().classes('w-full mb-4 p-4 bg-blue-50 border border-blue-200'):
                                            ui.label('✅ Analysis Complete').classes('font-semibold text-lg text-blue-800 mb-2')
                                            ui.label('Please provide feedback on the agent responses above to help improve future analyses.').classes('text-blue-700')
                                    break
                                    
                            except json.JSONDecodeError:
                                continue  # Skip malformed JSON
        
        except Exception as ex:
            ui.notify(f'Streaming error: {str(ex)}', type='negative')
    
    async def add_feedback_buttons(self, agent_name: str, message_element):
        """Add thumbs up/down feedback buttons to agent response."""
        try:
            with message_element:
                ui.separator().classes('my-2')
                
                with ui.row().classes('justify-center gap-2'):
                    ui.label('Was this helpful?').classes('text-sm text-gray-600')
                    
                    thumbs_up_btn = ui.button(
                        '👍', 
                        on_click=lambda: asyncio.create_task(
                            self.submit_feedback(agent_name, True)
                        )
                    ).classes('text-sm')
                    
                    thumbs_down_btn = ui.button(
                        '👎',
                        on_click=lambda: asyncio.create_task(
                            self.submit_feedback(agent_name, False)
                        )
                    ).classes('text-sm')
                    
                    # Store buttons for potential updates
                    self.feedback_buttons[agent_name] = {
                        'up': thumbs_up_btn,
                        'down': thumbs_down_btn
                    }
        
        except Exception:
            # Silently ignore feedback button errors
            pass
    
    async def submit_feedback(self, agent_name: str, thumbs_up: bool):
        """Submit feedback for an agent response."""
        try:
            # Update button states immediately for better UX
            if agent_name in self.feedback_buttons:
                buttons = self.feedback_buttons[agent_name]
                if thumbs_up:
                    buttons['up'].classes(remove='bg-gray-200 hover:bg-green-500').classes('bg-green-500 text-white')
                    buttons['down'].props('disabled')
                else:
                    buttons['down'].classes(remove='bg-gray-200 hover:bg-red-500').classes('bg-red-500 text-white')
                    buttons['up'].props('disabled')
            
            feedback_text = None
            
            # Show feedback dialog for additional comments
            if not thumbs_up:
                with ui.dialog() as dialog, ui.card().classes('w-96 p-4'):
                    ui.label(f'Help us improve {agent_name}\'s responses').classes('text-lg font-bold mb-4')
                    feedback_input = ui.textarea(
                        'What could be better?', 
                        placeholder='Optional feedback...'
                    ).classes('w-full')
                    
                    feedback_result = {'text': None}
                    
                    with ui.row().classes('justify-end gap-2 mt-4'):
                        ui.button('Skip', on_click=dialog.close).classes('text-sm')
                        ui.button(
                            'Submit',
                            on_click=lambda: (
                                setattr(feedback_result, 'text', feedback_input.value),
                                dialog.close()
                            )[-1]
                        ).classes('text-sm bg-primary')
                
                dialog.open()
                await dialog
                
                feedback_text = getattr(feedback_result, 'text', None)
            
            # Send feedback to backend API
            if self.current_session_id:
                try:
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        feedback_data = {
                            'session_id': self.current_session_id,
                            'agent_name': agent_name.lower(),
                            'thumbs_up': thumbs_up,
                            'feedback_text': feedback_text or ''
                        }
                        
                        response = await client.post(
                            f'{self.api_base_url}/submit-feedback',
                            json=feedback_data
                        )
                        
                        if response.status_code == 200:
                            # Feedback submitted successfully - button state already updated above
                            pass
                        else:
                            # Feedback recorded locally - button state already updated above
                            pass
                except httpx.RequestError:
                    # Network error - button state already updated above
                    pass
            else:
                # No session ID - button state already updated above
                pass
            
        except Exception as ex:
            # Reset button state on error
            if agent_name in self.feedback_buttons:
                buttons = self.feedback_buttons[agent_name]
                buttons['up'].classes(remove='bg-green-500 bg-red-500 text-white').classes('bg-gray-200 hover:bg-green-500')
                buttons['down'].classes(remove='bg-green-500 bg-red-500 text-white').classes('bg-gray-200 hover:bg-red-500')
                buttons['up'].props(remove='disabled')
                buttons['down'].props(remove='disabled')
    
    def create_main_interface(self):
        """Create the main chat interface."""
        with ui.column().classes('w-full max-w-4xl mx-auto p-4 gap-4'):
            
            # Instructions
            with ui.card().classes('w-full p-4'):
                ui.label('Welcome to Resume Roast! 🔥').classes('text-xl font-bold mb-2')
                ui.label(
                    'Upload your resume and paste a job description below. '
                    'Our AI agents will provide detailed feedback in real-time.'
                ).classes('text-gray-600')
            
            # Upload area
            with ui.card().classes('w-full p-4'):
                ui.label('Step 1: Enter Job Description').classes('font-bold mb-2')
                self.job_description_input = ui.textarea(
                    'Paste the job description here...',
                    placeholder='Looking for a Senior Python Developer with 5+ years of experience...'
                ).classes('w-full').props('rows=4')
                
                ui.separator().classes('my-4')
                
                ui.label('Step 2: Upload Resume (PDF only)').classes('font-bold mb-2')
                self.upload_area = ui.upload(
                    on_upload=self.handle_file_upload,
                    auto_upload=True
                ).classes('w-full').props('accept=.pdf max-file-size=5242880')  # 5MB limit
            
            # Chat container
            with ui.card().classes('w-full p-4 min-h-96'):
                ui.label('AI Analysis').classes('font-bold mb-4')
                self.chat_container = ui.column().classes('w-full gap-2')
                
                # Initial welcome message
                with self.chat_container:
                    ui.chat_message(
                        'Ready to analyze your resume. Please upload a PDF and provide a job description above.',
                        name='Resume Roast AI',
                        sent=False
                    ).classes('mb-2')
    
    def run_app(self):
        """Run the NiceGUI application."""
        self.setup_theme()
        
        # Create UI
        self.create_header()
        self.create_main_interface()
        
        # Add footer
        with ui.row().classes('w-full justify-center p-4 text-gray-500'):
            ui.label('Resume Roast v0.1.0 - Powered by AI').classes('text-sm')


# Create and run the application
def main():
    """Main function to start the application."""
    ui_app = ResumeRoastUI()
    ui_app.run_app()
    
    ui.run(
        title='Resume Roast - AI Resume Critique',
        host='0.0.0.0',
        port=8080,
        reload=False,
        show=False
    )


if __name__ in {"__main__", "__mp_main__"}:
    main()