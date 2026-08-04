"""
Vertex AI Chat Integration
Provides AI-powered chat support using Google's Vertex AI (Gemini)
Uses GCP credits - perfect for Cloud Run deployment
"""
import os
from typing import List, Dict
from datetime import datetime
from simple_bot import simple_bot

try:
    import vertexai
    from vertexai.generative_models import GenerativeModel, ChatSession
    VERTEX_AVAILABLE = True
except ImportError:
    VERTEX_AVAILABLE = False
    print("[Vertex AI] vertexai package not installed. Using fallback bot.")

class VertexAIChat:
    def __init__(self):
        """
        Initialize Vertex AI client
        Uses GCP project credentials (automatic on Cloud Run)
        """
        self.project_id = os.getenv("GCP_PROJECT_ID", "abiding-idea-485817-k2")
        self.location = os.getenv("GCP_REGION", "us-central1")
        self.model_name = "gemini-1.5-flash-001"  # specific version
        self.client = None
        self.use_vertex = False
        
        if not VERTEX_AVAILABLE:
            print("[Vertex AI] Package not available. Using fallback bot.")
            return
        
        try:
            # Initialize Vertex AI
            vertexai.init(project=self.project_id, location=self.location)
            
            # Create generative model
            self.model = GenerativeModel(
                self.model_name,
                system_instruction=[
                    """You are a caring friend who happens to know a lot about wellbeing. You're here to listen and support.

MOST IMPORTANT RULE:
- ALWAYS respond DIRECTLY to what the user JUST said
- Show you heard them by acknowledging their specific words and feelings
- Be conversational, like texting a supportive friend

HOW TO RESPOND:
1. First, acknowledge what they said (use their words!)
2. Then, respond naturally based on what THEY brought up
3. Only ask a follow-up question if it flows naturally from the conversation

CONVERSATION STYLE:
- Keep it SHORT (1-3 sentences)
- Sound human, not like a bot
- Don't give advice unless they ask for it
- Don't ask multiple questions
- Don't give lists of tips unless requested
- Match their energy (if they're casual, be casual)

EXAMPLES OF GOOD RESPONSES:

User: "I'm feeling really stressed lately"
Good: "That sounds tough. What's been going on?"
Bad: "I understand you're stressed. Here are 5 stress management techniques..."

User: "Work has been crazy, so many deadlines"
Good: "Ugh, deadline pressure is the worst. Are you able to take any breaks?"
Bad: "How long has this been happening? What industry do you work in? Do you exercise regularly?"

User: "Yeah I try to take breaks but it's hard"
Good: "I get that. Even a 5-minute walk can help reset your brain, but I know it's easier said than done."
Bad: "You should definitely take breaks. Studies show that breaks improve productivity by 30%..."

User: "Thanks, that helps"
Good: "Anytime! I'm here if you need to talk more."
Bad: "You're welcome! Would you like to discuss sleep hygiene? Nutrition? Exercise routines?"

REMEMBER:
- You're a friend, not a therapist or life coach
- Listen MORE than you talk
- Respond to what THEY say, don't push your own agenda
- Keep it natural and conversational
- If they need professional help, gently suggest booking a consultant on the platform"""
                ]
            )
            
            self.use_vertex = True
            print(f"[Vertex AI] Connected using model: {self.model_name}")
            print(f"[Vertex AI] Project: {self.project_id}, Region: {self.location}")
            
        except Exception as e:
            print(f"[Vertex AI] Failed to initialize: {e}")
            print("[Vertex AI] Using fallback bot.")
    
    def chat(self, message: str, conversation_history: List[Dict] = None) -> str:
        """
        Send a message to Vertex AI and get a response
        Falls back to simple bot if Vertex AI is unavailable
        """
        def log(msg):
            try:
                with open("vertex_trace.log", "a") as f:
                    f.write(f"{datetime.now()}: {msg}\n")
            except: 
                pass

        log(f"Chat request: {message}")
        
        # Try Vertex AI first if available
        if self.use_vertex and self.model:
            try:
                log(f"Trying Vertex AI with model {self.model_name}")
                
                # Start a new chat session
                chat = self.model.start_chat()
                
                # Add conversation history if available
                if conversation_history:
                    # Only use last 4 messages (2 exchanges) for context
                    recent_history = conversation_history[-4:]
                    for msg in recent_history:
                        content = msg.get('content', '')
                        is_user = msg.get('is_user', False)
                        
                        # Send previous user messages to build context
                        if is_user and content:
                            try:
                                chat.send_message(content)
                            except:
                                pass  # Skip if error in history
                
                # Send current message
                log("Sending request to Vertex AI...")
                response = chat.send_message(
                    message,
                    generation_config={
                        "max_output_tokens": 256,  # Match Ollama's limit
                        "temperature": 0.7,  # Match Ollama
                        "top_p": 0.9,  # Match Ollama
                    }
                )
                
                # Extract response
                resp_text = response.text.strip()
                
                if not resp_text:
                    resp_text = "I'm here for you. Tell me more about what's on your mind."
                
                log(f"Vertex AI success: {len(resp_text)} chars")
                return resp_text
                    
            except Exception as e:
                log(f"Vertex AI error: {str(e)}")
                print(f"Vertex AI chat error: {str(e)}")
                # Fall back to simple bot
                return simple_bot.get_response(message, conversation_history)
        else:
            log("Using SimpleBot (Vertex AI unavailable)")
            # Use simple bot
            return simple_bot.get_response(message, conversation_history)
    
    def is_available(self) -> bool:
        """Check if Vertex AI service is available"""
        return self.use_vertex

# Global instance
vertex_chat = VertexAIChat()
