"""
Simple Fallback Bot for SolaceSquad (Emora)
Safe, empathetic offline fallback when AI models are temporarily unreachable.
No grounding loops, no 5-4-3-2-1 traps, strictly supportive and consultant-friendly.
"""
import random
import re
from datetime import datetime

class SimpleWellbeingBot:
    def __init__(self):
        self.responses = {
            'greeting': [
                "Hello! 👋 I'm Emora, your wellness guide. How are you feeling today?",
                "Hi there! 💜 I'm right here with you. What's on your mind today?",
                "Hello! I'm glad you're here. How can I support your wellbeing today?",
            ],
            'stress': [
                "I hear you, and it is completely understandable to feel overwhelmed. Remember you don't have to carry this alone. You can also connect with one of our SolaceSquad consultants for personalized support.",
                "Stress can feel heavy, but I'm here to listen. Take things one moment at a time. How can I support you right now?",
                "It sounds like you're carrying a lot right now. Please be gentle with yourself. Would you like to talk about what's causing this stress, or connect with a specialist?",
            ],
            'anxiety': [
                "I understand how uncomfortable and overwhelming anxiety can feel. Take a gentle breath—you are safe here. Would you like to talk about what's making you anxious, or would you like to explore talking with a verified consultant?",
                "Feeling anxious is tough, but you are not alone. I'm right here listening. What thoughts or situations are on your mind right now?",
                "I hear you. Anxiety can be exhausting. Take your time—I'm here with you. How can I help you feel a bit more at ease today?",
            ],
            'sad': [
                "I'm so sorry you're feeling down. Thank you for opening up to me. I'm here to listen whenever you're ready to share.",
                "It's completely okay to not feel okay today. You are safe here with me. What has been weighing on your heart?",
                "Sadness is a heavy emotion. Please be kind to yourself. If you'd like deeper support, our SolaceSquad consultants are also here to help you through this.",
            ],
            'sleep': [
                "Sleep struggles can be so draining. Creating a calm, low-light environment and winding down early can help. What seems to be keeping you awake?",
                "I hear you—restless nights make everything harder. Would you like to share what's on your mind, or connect with a sleep and wellness specialist?",
            ],
            'nutrition': [
                "Nutrition and physical wellness play a huge role in how we feel every day. Would you like to share what specific health or diet goals you're focusing on?",
                "Taking care of your body is a wonderful step. You can also connect directly with certified nutritionists right here on SolaceSquad.",
            ],
            'consultant': [
                "We have verified wellness consultants, therapists, and nutritionists on SolaceSquad who can support you 1-on-1. You can view their profiles and book a session right below.",
                "Connecting with a professional can make a world of difference. You can check out our matched specialists and pick a time slot that works best for you.",
            ],
            'default': [
                "I hear you. I'm right here with you—please tell me more about what you're experiencing.",
                "Thank you for sharing that with me. What would be most helpful for you right now?",
                "I'm listening closely. How has this been affecting your day?",
                "I appreciate you opening up. Take your time—I'm here to support you.",
            ]
        }
        
        self.patterns = {
            'greeting': r'\b(hi|hello|hey|good morning|good evening|namaste|greetings)\b',
            'stress': r'\b(stress|stressed|overwhelm|pressure|too much|burnout|tense)\b',
            'anxiety': r'\b(anxious|anxiety|worried|worry|nervous|panic|scared|fear)\b',
            'sad': r'\b(sad|depressed|depression|down|unhappy|lonely|alone|cry|crying|grief)\b',
            'sleep': r'\b(sleep|insomnia|tired|exhausted|rest|awake|night)\b',
            'nutrition': r'\b(nutrition|diet|weight|gut|digestion|fitness|workout|exercise)\b',
            'consultant': r'\b(therapist|counselor|consultant|doctor|psychologist|nutritionist|specialist|session|book)\b',
        }
    
    def get_response(self, message: str, conversation_history: list = None) -> str:
        """Generate an empathetic, non-looping response"""
        if not message:
            return "I'm right here with you. What would you like to talk about today?"

        message_clean = message.strip()
        message_lower = message_clean.lower()

        # Check if matcher context is present in message
        if "[CONSULTANT_MATCHER_RECOMMENDATION]" in message_clean:
            # Extract consultant names from context if any
            consultant_matches = re.findall(r'•\s+([^(\n]+)\s*\(([^)]+)\)', message_clean)
            if consultant_matches:
                names = [c[0].strip() for c in consultant_matches[:2]]
                names_str = " and ".join(names)
                return f"We have verified specialists ready to support you, including {names_str}. You can view their profiles and book a session directly from the cards below."
            return "We have verified specialists available to help you with this concern. You can browse their details and book a session right below."

        if "[CONSULTANT_MATCHER_PROBLEM_UNDERSTOOD]" in message_clean:
            return "Thank you for sharing that with me. I understand what you're going through, and a 1-on-1 consultation would be ideal for this. Do you have any language preferences for your consultant?"

        if "[CONSULTANT_MATCHER_GREETING]" in message_clean:
            return "Hi! I'm Emora, your wellness guide. What health, wellness, nutrition, or life challenge can we support you with today?"

        if "[CONSULTANT_MATCHER_CLARIFICATION]" in message_clean:
            return "I'm right here with you. Could you share a little more about what specific challenge or concern you'd like support with today?"

        # Match category patterns
        for category, pattern in self.patterns.items():
            if re.search(pattern, message_lower):
                options = self.responses.get(category, self.responses['default'])
                return random.choice(options)

        return random.choice(self.responses['default'])

    def get_greeting(self) -> str:
        return "Hi! 👋 I'm Emora, your wellness guide. How can I support you today?"

# Global instance
simple_bot = SimpleWellbeingBot()
