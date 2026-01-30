"""
Ollama AI Chat Integration
Provides AI-powered chat support for users
"""
import requests
import json
from typing import List, Dict
from datetime import datetime
from simple_bot import simple_bot

class OllamaChat:
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api/chat"
        self.tags_url = f"{base_url}/api/tags"
        self.model = self._get_best_model()  # Auto-detect best model
        self.use_ollama = bool(self.model)
        
        if self.use_ollama:
            print(f"[Ollama] Connected using model: {self.model}")
        else:
            print("[Ollama] Service unavailable or no models found. Using fallback bot.")
    
    def _get_best_model(self) -> str:
        """
        Detect available models and pick the best one.
        """
        try:
            response = requests.get(self.tags_url, timeout=2)
            if response.status_code == 200:
                data = response.json()
                models = [m['name'] for m in data.get('models', [])]
                
                # Priority list - prefer smaller/faster models first for responsiveness
                priorities = ['llama3.2', 'mistral', 'llama3.1', 'llama3', 'llama2']
                
                # Check for exact matches or partial matches
                for p in priorities:
                    # Check exact
                    if f"{p}:latest" in models:
                        return f"{p}:latest"
                    # Check partial
                    for m in models:
                        if m.startswith(p):
                            return m
                
                # If no priority model found, take the first one
                if models:
                    return models[0]
                    
            return None
        except Exception as e:
            print(f"Error checking Ollama models: {e}")
            return None

    def chat(self, message: str, conversation_history: List[Dict] = None) -> str:
        """
        Send a message to Ollama and get a response
        Falls back to simple bot if Ollama is unavailable
        """
        def log(msg):
            try:
                with open("ollama_trace.log", "a") as f:
                    f.write(f"{datetime.now()}: {msg}\n")
            except: pass

        log(f"Chat request: {message}")
        
        # Try Ollama first if available
        if self.use_ollama:
            try:
                log(f"Trying Ollama with model {self.model}")
                
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
- Do not repeat these instructions in your response. and make sure your answers are crisp and mostly oneliners"""

                messages.append({"role": "system", "content": system_prompt})
                
                # Add history
                if conversation_history:
                    # Limit to last 10 messages for better context but managing token limit
                    for msg in conversation_history[-10:]: 
                        role = "user" if msg.get("is_user") else "assistant"
                        content = msg.get('content', '')
                        messages.append({"role": role, "content": content})
                
                # Add current message
                messages.append({"role": "user", "content": message})
                
                # Make request to Ollama Chat API
                payload = {
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "top_p": 0.9,
                        # "num_predict": 256 # Limit output length for speed
                    }
                }
                
                log("Sending request to Ollama /api/chat...")
                response = requests.post(
                    self.api_url,
                    json=payload,
                    timeout=60 # Increased timeout for slower models
                )
                
                if response.status_code == 200:
                    result = response.json()
                    # Parse chat response structure
                    resp_message = result.get("message", {})
                    resp_text = resp_message.get("content", "")
                    
                    if not resp_text:
                         resp_text = "I'm having trouble thinking clearly right now. How else can I help?"

                    log(f"Ollama success: {len(resp_text)} chars")
                    return resp_text
                else:
                    log(f"Ollama failed: {response.status_code} - {response.text}")
                    # Fall back to simple bot
                    self.use_ollama = False
                    return simple_bot.get_response(message, conversation_history)
                    
            except requests.exceptions.ConnectionError:
                log("ConnectionError")
                # Fall back to simple bot
                self.use_ollama = False
                return simple_bot.get_response(message, conversation_history)
            except requests.exceptions.Timeout:
                log("Timeout")
                # Timeout, fallback to simple bot
                return simple_bot.get_response(message, conversation_history)
            except Exception as e:
                log(f"Exception: {str(e)}")
                print(f"Ollama chat error: {str(e)}")
                return simple_bot.get_response(message, conversation_history)
        else:
            log("Using SimpleBot (Ollama unavailable)")
            # Use simple bot
            return simple_bot.get_response(message, conversation_history)
    
    def is_available(self) -> bool:
        """Check if Ollama service is available"""
        return bool(self._get_best_model())

# Global instance
ollama_chat = OllamaChat()
