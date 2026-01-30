"""
OpenAI Chat Integration
Provides AI-powered chat support using OpenAI's API
Cost-effective alternative to local Ollama deployment
"""
import os
from openai import OpenAI
from typing import List, Dict
from datetime import datetime
from simple_bot import simple_bot

class OpenAIChat:
    def __init__(self):
        """
        Initialize OpenAI client
        Requires OPENAI_API_KEY environment variable
        """
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.client = None
        self.use_openai = False
        
        # Use GPT-4o-mini for cost effectiveness
        # Pricing (as of 2024): $0.150/1M input tokens, $0.600/1M output tokens
        # Much cheaper than GPT-4 while still very capable
        self.model = "gpt-4o-mini"
        
        if self.api_key:
            try:
                self.client = OpenAI(api_key=self.api_key)
                self.use_openai = True
                print(f"[OpenAI] Connected using model: {self.model}")
            except Exception as e:
                print(f"[OpenAI] Failed to initialize: {e}")
                print("[OpenAI] Using fallback bot.")
        else:
            print("[OpenAI] API key not found. Set OPENAI_API_KEY environment variable.")
            print("[OpenAI] Using fallback bot.")
    
    def chat(self, message: str, conversation_history: List[Dict] = None) -> str:
        """
        Send a message to OpenAI and get a response
        Falls back to simple bot if OpenAI is unavailable
        """
        def log(msg):
            try:
                with open("openai_trace.log", "a") as f:
                    f.write(f"{datetime.now()}: {msg}\n")
            except: 
                pass

        log(f"Chat request: {message}")
        
        # Try OpenAI first if available
        if self.use_openai and self.client:
            try:
                log(f"Trying OpenAI with model {self.model}")
                
                # Build messages list
                messages = []
                
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

                messages.append({"role": "system", "content": system_prompt})
                
                # Add history (limit to last 10 messages for cost efficiency)
                if conversation_history:
                    for msg in conversation_history[-10:]: 
                        role = "user" if msg.get("is_user") else "assistant"
                        content = msg.get('content', '')
                        messages.append({"role": role, "content": content})
                
                # Add current message
                messages.append({"role": "user", "content": message})
                
                # Make request to OpenAI
                log("Sending request to OpenAI...")
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=256,  # Limit output for cost control
                    top_p=0.9
                )
                
                # Extract response
                resp_text = response.choices[0].message.content
                
                if not resp_text:
                    resp_text = "I'm having trouble thinking clearly right now. How else can I help?"
                
                log(f"OpenAI success: {len(resp_text)} chars")
                return resp_text
                    
            except Exception as e:
                log(f"OpenAI error: {str(e)}")
                print(f"OpenAI chat error: {str(e)}")
                # Fall back to simple bot
                return simple_bot.get_response(message, conversation_history)
        else:
            log("Using SimpleBot (OpenAI unavailable)")
            # Use simple bot
            return simple_bot.get_response(message, conversation_history)
    
    def is_available(self) -> bool:
        """Check if OpenAI service is available"""
        return self.use_openai

# Global instance
openai_chat = OpenAIChat()
