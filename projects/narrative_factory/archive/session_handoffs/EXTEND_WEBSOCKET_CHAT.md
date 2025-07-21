# Extend WebSocket for Conversational Interface

## EXTEND Phase 2.1: Add Chat Route (Extend existing websocket_routes.py)

### Add to `src/web/websocket_routes.py`:

```python
@websocket_router.websocket("/ws/chat")
async def websocket_chat_endpoint(websocket: WebSocket):
    """
    Conversational AI endpoint for natural language story control.
    
    Extends existing WebSocket infrastructure for chat-based interaction.
    """
    user_id = None
    
    try:
        await websocket.accept()
        
        # Use existing authentication pattern
        auth_message = await websocket.receive_text()
        auth_data = json.loads(auth_message)
        
        # Reuse existing auth system
        user_id = await verify_websocket_token(auth_data.get("token"))
        
        # Register with existing connection manager
        await connection_manager.connect(websocket, user_id, "chat")
        
        # Chat message loop
        while True:
            message = await websocket.receive_text()
            chat_data = json.loads(message)
            
            # Process chat message using existing agent system
            response = await _process_chat_message(chat_data, user_id)
            
            # Send response using existing message format
            await connection_manager.send_to_user(user_id, {
                "type": "chat_response",
                "timestamp": datetime.now().isoformat(),
                "data": response
            })
            
    except WebSocketDisconnect:
        logger.info(f"Chat client {user_id} disconnected")
    except Exception as e:
        logger.error(f"Chat error for user {user_id}: {e}")
    finally:
        if user_id:
            await connection_manager.disconnect(websocket, user_id)

async def _process_chat_message(chat_data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """
    Process chat message using existing agent infrastructure.
    
    Extends existing agents with conversational capabilities.
    """
    message = chat_data.get("message", "")
    context = chat_data.get("context", {})
    
    # Use existing ChatDirector (extend existing DirectorAgent)
    from src.agents.chat_agents import ChatDirector
    
    chat_director = ChatDirector()
    response = await chat_director.process_chat(message, context, user_id)
    
    return {
        "response": response.text,
        "suggestions": response.suggestions,
        "actions": response.proposed_actions
    }
```

## EXTEND Phase 2.2: Create Chat Agent Extensions

### Add `src/agents/chat_agents.py` (Extends existing agent system):

```python
"""
Chat-enabled agent extensions for conversational story control.

Extends existing DirectorAgent, TacticianAgent, etc. with chat capabilities.
"""

from typing import Dict, Any, List
from pydantic import BaseModel

from src.agents.personas import DirectorAgent, TacticianAgent, WeaverAgent, CanonistAgent
from src.memory.qdrant import QdrantService
from src.workflows.jobs import JobStore

class ChatResponse(BaseModel):
    """Response format for chat interactions."""
    text: str
    suggestions: List[str] = []
    proposed_actions: List[Dict[str, Any]] = []
    requires_approval: bool = False

class ChatDirector(DirectorAgent):
    """
    Extends existing DirectorAgent with conversational capabilities.
    
    Reuses all existing Director functionality while adding chat interface.
    """
    
    def __init__(self):
        super().__init__()  # Initialize existing DirectorAgent
        self.qdrant = QdrantService()  # Use existing memory service
        self.job_store = JobStore()   # Use existing job system
    
    async def process_chat(self, message: str, context: Dict[str, Any], user_id: str) -> ChatResponse:
        """
        Process natural language message and respond with story guidance.
        
        Extends existing Director capabilities with conversational interface.
        """
        
        # Parse intent using existing Director analysis
        intent = await self._parse_chat_intent(message, context)
        
        if intent.type == "add_character":
            return await self._handle_character_addition(intent, user_id)
        elif intent.type == "review_chapter":
            return await self._handle_chapter_review(intent, user_id)
        elif intent.type == "story_direction":
            return await self._handle_story_direction(intent, user_id)
        else:
            return await self._handle_general_guidance(intent, user_id)
    
    async def _handle_character_addition(self, intent, user_id: str) -> ChatResponse:
        """Handle character addition requests using existing systems."""
        
        # Use existing memory system to check conflicts
        existing_chars = await self.qdrant.search_by_content(
            query_text=intent.character_name,
            collection_name="world_bible",
            limit=5
        )
        
        # Use existing Director agent to analyze integration
        integration_analysis = await self.execute(
            f"Analyze adding {intent.character_name} to existing story",
            {"existing_characters": existing_chars}
        )
        
        # Create job using existing job system
        job_id = self.job_store.create_job(
            agent="Director",
            input_payload={
                "action": "character_addition",
                "character": intent.character_name,
                "analysis": integration_analysis.model_dump()
            }
        )
        
        return ChatResponse(
            text=f"I'll help you add {intent.character_name}. Based on your existing story, here's my analysis:",
            suggestions=[
                f"Introduce {intent.character_name} at chapter {intent.optimal_chapter}",
                f"Role: {intent.suggested_role}",
                f"Relationship dynamics: {intent.relationship_impact}"
            ],
            proposed_actions=[
                {
                    "type": "create_character_sheet",
                    "job_id": job_id,
                    "requires_approval": True
                }
            ],
            requires_approval=True
        )
    
    async def _parse_chat_intent(self, message: str, context: Dict[str, Any]):
        """Parse user intent from natural language using existing Director."""
        
        # Use existing Director agent to understand intent
        intent_prompt = f"""
        Parse this user message for story management intent:
        Message: "{message}"
        Context: {context}
        
        Determine if this is:
        - add_character (wanting to add new character)
        - review_chapter (wanting to review agent output)
        - story_direction (wanting to change plot direction)
        - general_guidance (asking for advice)
        """
        
        # Use existing execute method
        result = await self.execute(intent_prompt, context)
        
        # Parse result into structured intent
        return self._structure_intent(result, message)

class ChatInterface:
    """
    Main chat interface that coordinates between chat agents and existing systems.
    
    Orchestrates existing agents, job system, and memory system for chat interaction.
    """
    
    def __init__(self):
        self.chat_director = ChatDirector()
        # Can extend with ChatTactician, ChatWeaver, etc. as needed
    
    async def process_message(self, message: str, user_id: str, context: Dict[str, Any] = None) -> ChatResponse:
        """
        Main entry point for chat message processing.
        
        Uses existing agent infrastructure with conversational wrapper.
        """
        if context is None:
            context = {}
        
        # Use ChatDirector (which extends existing DirectorAgent)
        return await self.chat_director.process_chat(message, context, user_id)
```

## EXTEND Phase 2.3: Simple Chat UI (Optional)

### Add `web/chat.html` (Simple interface for testing):

```html
<!DOCTYPE html>
<html>
<head>
    <title>Narrative Factory Chat</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        #chat-container { max-width: 800px; margin: 0 auto; }
        #messages { height: 400px; overflow-y: scroll; border: 1px solid #ccc; padding: 10px; margin-bottom: 10px; }
        #input-container { display: flex; }
        #message-input { flex: 1; padding: 10px; margin-right: 10px; }
        button { padding: 10px 20px; }
        .message { margin-bottom: 10px; padding: 10px; border-radius: 5px; }
        .user-message { background-color: #e3f2fd; text-align: right; }
        .ai-message { background-color: #f3e5f5; }
        .suggestions { margin-top: 10px; font-style: italic; color: #666; }
    </style>
</head>
<body>
    <div id="chat-container">
        <h1>Narrative Factory Chat</h1>
        <div id="messages"></div>
        <div id="input-container">
            <input type="text" id="message-input" placeholder="Ask about your story..." />
            <button onclick="sendMessage()">Send</button>
        </div>
    </div>

    <script>
        // Use existing WebSocket infrastructure
        const ws = new WebSocket('ws://localhost:8000/ws/chat');
        
        ws.onopen = function(event) {
            // Use existing authentication pattern
            ws.send(JSON.stringify({
                token: 'your-auth-token'  // In real app, get from login
            }));
        };
        
        ws.onmessage = function(event) {
            const response = JSON.parse(event.data);
            if (response.type === 'chat_response') {
                displayAIMessage(response.data);
            }
        };
        
        function sendMessage() {
            const input = document.getElementById('message-input');
            const message = input.value.trim();
            
            if (message) {
                displayUserMessage(message);
                
                // Send using existing WebSocket message format
                ws.send(JSON.stringify({
                    type: 'chat_message',
                    message: message,
                    timestamp: new Date().toISOString(),
                    context: {
                        story_id: 'my_serial'  // Could be dynamic
                    }
                }));
                
                input.value = '';
            }
        }
        
        function displayUserMessage(message) {
            const messagesDiv = document.getElementById('messages');
            messagesDiv.innerHTML += `
                <div class="message user-message">
                    <strong>You:</strong> ${message}
                </div>
            `;
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }
        
        function displayAIMessage(data) {
            const messagesDiv = document.getElementById('messages');
            let suggestionsHtml = '';
            
            if (data.suggestions && data.suggestions.length > 0) {
                suggestionsHtml = `
                    <div class="suggestions">
                        Suggestions: ${data.suggestions.join(', ')}
                    </div>
                `;
            }
            
            messagesDiv.innerHTML += `
                <div class="message ai-message">
                    <strong>Narrative Factory:</strong> ${data.response}
                    ${suggestionsHtml}
                </div>
            `;
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }
        
        // Allow Enter key to send message
        document.getElementById('message-input').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                sendMessage();
            }
        });
    </script>
</body>
</html>
```

## Implementation Strategy: Extend, Don't Rebuild

### What You're Extending:

1. **WebSocket System**: Add `/ws/chat` route to existing infrastructure
2. **Agent System**: Create ChatDirector that extends existing DirectorAgent
3. **Job System**: Use existing JobStore for chat-triggered actions
4. **Memory System**: Use existing QdrantService for context retrieval

### What Stays the Same:

- All existing CLI commands work unchanged
- All existing agent workflows work unchanged  
- All existing memory/vector operations work unchanged
- All existing authentication and connection management

### Development Steps:

1. **Week 3**: Add chat WebSocket route (extends existing websocket_routes.py)
2. **Week 4**: Create ChatDirector (extends existing DirectorAgent)
3. **Week 4**: Add simple HTML interface (optional - for testing)
4. **Test**: Chat interface triggers existing job approval workflow

This approach gives you conversational control while preserving all existing functionality.