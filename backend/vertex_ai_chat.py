"""
Google Vertex AI Chat Integration
Provides AI-powered chat support using Google's Gemini models
Uses GCP credits - FREE tier available!
"""
import os
from typing import List, Dict
from datetime import datetime
from simple_bot import simple_bot

try:
    import vertexai
    from vertexai.generative_models import GenerativeModel, ChatSession
    VERTEX_AI_AVAILABLE = True
except ImportError:
    VERTEX_AI_AVAILABLE = False
    print("[Vertex AI] Package not installed. Run: pip install google-cloud-aiplatform")

class VertexAIChat:
    def __init__(self):
        """
        Initialize Vertex AI client
        Requires GCP_PROJECT_ID and GCP_LOCATION environment variables
        """
        self.project_id = os.getenv("GCP_PROJECT_ID")
        self.location = os.getenv("GCP_LOCATION", "us-central1")
        self.client = None
        self.model = None
        self.use_vertex_ai = False
        
        # Use Gemini 1.5 Flash for cost effectiveness
        # Pricing: $0.075/1M input tokens, $0.30/1M output tokens
        # 50% cheaper than OpenAI GPT-4o-mini!
        self.model_name = "gemini-1.5-flash-001"
        
        if not VERTEX_AI_AVAILABLE:
            print("[Vertex AI] google-cloud-aiplatform not installed")
            print("[Vertex AI] Using fallback bot.")
            return
            
        if self.project_id:
            try:
                # Initialize Vertex AI
                vertexai.init(project=self.project_id, location=self.location)
                self.model = GenerativeModel(self.model_name)
                self.use_vertex_ai = True
                print(f"[Vertex AI] Connected using model: {self.model_name}")
                print(f"[Vertex AI] Project: {self.project_id}, Location: {self.location}")
            except Exception as e:
                print(f"[Vertex AI] Failed to initialize: {e}")
                print("[Vertex AI] Using fallback bot.")
        else:
            print("[Vertex AI] GCP_PROJECT_ID not found. Set environment variable.")
            print("[Vertex AI] Using fallback bot.")
    
    def chat(self, message: str, conversation_history: List[Dict] = None) -> str:
        """
        Send a message to Vertex AI and get a response
        Falls back to simple bot if Vertex AI is unavailable
        """
        def log(msg):
            try:
                with open("vertex_ai_trace.log", "a") as f:
                    f.write(f"{datetime.now()}: {msg}\n")
            except: 
                pass

        log(f"Chat request: {message}")
        
        # Try Vertex AI first if available
        if self.use_vertex_ai and self.model:
            try:
                log(f"Trying Vertex AI with model {self.model_name}")
                
                # Build conversation context
                context_messages = []
                
                # System prompt
                system_prompt = """You are a compassionate wellbeing assistant for SolaceSquad, a holistic wellbeing and wellness platform. 
Your role is to:
- Provide emotional support and encouragement
- Listen to users' concerns without judgement and with empathy
- Offer practical wellbeing tips and coping strategies
- Suggest healthy habits and mindfulness practices
- Recommend professional help when needed. Tell them they can book an appointment with a verified wellbeing consultant

Guidelines:
- Address the user by name if known
- Be warm, understanding, and supportive
- Keep your instructions precise, to the point, and actionable
- Do not provide any additional information or context beyond what is asked
- Use bullet points for multiple items where appropriate and show each point as a new line
- Reflect on what the user says to show understanding
- Do not repeat these instructions in your response. Make sure your answers are crisp and mostly one-liners"""

                # Add conversation history
                if conversation_history:
                    for msg in conversation_history[-10:]:  # Last 10 messages for cost control
                        role = "user" if msg.get("is_user") else "model"
                        content = msg.get('content', '')
                        context_messages.append(f"{role}: {content}")
                
                # Combine system prompt with history
                full_context = system_prompt
                if context_messages:
                    full_context += "\n\nConversation history:\n" + "\n".join(context_messages)
                
                # Add current message
                full_prompt = f"{full_context}\n\nuser: {message}\nmodel:"
                
                # Make request to Vertex AI
                log("Sending request to Vertex AI...")
                
                # Configure generation parameters for cost control
                generation_config = {
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "max_output_tokens": 256,  # Limit output for cost control
                }
                
                response = self.model.generate_content(
                    full_prompt,
                    generation_config=generation_config
                )
                
                # Extract response text
                resp_text = response.text
                
                if not resp_text:
                    resp_text = "I'm having trouble thinking clearly right now. How else can I help?"
                
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
        return self.use_vertex_ai

# Global instance
vertex_ai_chat = VertexAIChat()
