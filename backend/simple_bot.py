"""
Simple Rule-Based Chatbot for Wellbeing Support
Works without external dependencies as a fallback when Ollama is unavailable
"""
import random
import re
from datetime import datetime

class SimpleWellbeingBot:
    def __init__(self):
        # Interactive flows for specific techniques
        self.flows = {
            '54321': {
                'name': 'Grounding Technique',
                'steps': [
                    "Let's try the 5-4-3-2-1 grounding technique together. First, look around and tell me 5 things you can see right now.",
                    "Great observation. Now, focus on your sense of touch. Tell me 4 things you can physically feel (like the chair supporting you, or fabric on your skin).",
                    "Wonderful. Next, let's close our eyes for a moment. Listen carefully. Tell me 3 things you can hear.",
                    "You're doing great. Now, engage your sense of smell. Tell me 2 things you can smell (or your favorite smells).",
                    "Almost there. Finally, tell me 1 thing you can taste, or simply name a taste you enjoy.",
                    "Excellent. Take a deep breath. How are you feeling now after grounding yourself in the present?"
                ]
            },
            'breathing': {
                'name': '4-7-8 Breathing',
                'steps': [
                    "Let's do a 4-7-8 breathing exercise. Sit comfortably. Exhale completely through your mouth. Ready? ... Inhale through your nose for 4 seconds.",
                    "Hold that breath for 7 seconds...",
                    "Now exhale forcefully through your mouth for 8 seconds...",
                    "Great. Let's do it one more time. Inhale deeply... 2... 3... 4...",
                    "Hold... 2... 3... 4... 5... 6... 7...",
                    "Exhale fully... 2... 3... 4... 5... 6... 7... 8...",
                    "Wonderful. Normal breathing now. How did that feel for you?"
                ]
            }
        }
        
        self.responses = {
            'greeting': [
                "Hello! I'm here to support your wellbeing journey. How are you feeling right now?",
                "Hi there! It's great to connect. What's on your mind today?",
                "Welcome. I'm listening. How can I help you feel more balanced today?",
                "Hello! I'm glad you're here. How is your day going?",
            ],
            'stress': [
                "I hear that you're stressed. It's completely valid to feel that way. Would you like to try a 'grounding' exercise to help you feel more centered?",
                "Stress can be heavy. Sometimes pausing helps. Shall we try a quick 'breathing' exercise together?",
                "It sounds like you're carrying a lot. Remember to be gentle with yourself. Would a 'distraction' help, or do you want to talk about what's stressing you?",
                "When we're stressed, our body tenses up. Have you taken a moment to stretch or breathe deeply today?",
            ],
            'anxiety': [
                "Anxiety feels overwhelming, but it will pass. Would you like to try the '5-4-3-2-1' technique to help ground you in the moment?",
                "I understand. You're safe here. Shall we try some deep 'breathing' to calm your nervous system?",
                "Naming your worries can sometimes reduce their power. Or we could do a quick 'grounding' exercise. Which sounds better?",
                "Take a gentle breath. You are right here, right now, and you are safe. Can I help you with a calming exercise?",
            ],
            'sad': [
                "I'm sorry you're feeling down. Thank you for telling me. Do you want to share more about what's happening, or would you prefer a gentle distraction?",
                "It's okay to feel sad. I'm here. Would you like to hear a 'positive' thought, or just have someone listen?",
                "Sadness is a heavy emotion. Be kind to yourself today. I'm listening if you want to vent.",
            ],
            'sleep': [
                "Sleep struggles are tough. Have you tried the '4-7-8' breathing technique? I can guide you through it if you like.",
                "Racing thoughts often keep us awake. Would you like to try a 'grounding' exercise to get out of your head?",
                "Setting a consistent bedtime routine can sometimes help. What is your current routine like?"
            ],
            'exercise': [
                "Movement changes mood! Even a 2-minute stretch counts. Want a quick challenge? Try standing up and stretching your arms up high right now!",
                "Regular interactions with nature or just walking can boost your mood significantly. Have you moved your body today?",
            ],
            'gratitude': [
                "Gratitude shifts perspective. Can you tell me just ONE meaningful thing that happened today?",
                "That's a beautiful practice. Who is one person you're grateful for having in your life, and why?",
                "Focusing on the good can help rewiring our brain. What made you smile today?",
            ],
            'motivation': [
                "Motivation follows action, not the other way around. What is the tiniest, 2-minute version of the task you're avoiding?",
                "Be kind to yourself. You don't have to do it all. What's one small step you can take right now?",
                "Sometimes we just need to start. Can you commit to just 5 minutes of the task?",
            ],
            'positive': [
                "That's wonderful! Hold onto that feeling. What do you think contributed to this good moment?",
                "I love hearing that! Celebrate this win. How can you treat yourself to something nice today?",
                "Positivity is contagious. Thank you for sharing your joy with me!",
            ],
            'help': [
                "I can guide you through 'breathing' exercises, 'grounding' techniques, or offer tips for sleep and stress. What feels right for you?",
                "I'm here to support your mental and emotional wellbeing. I can offer coping strategies, mindfulness tips, and encouragement. What would help you most right now?",
            ],
            'professional': [
                "I can offer general support, but our human consultants are amazing for deep work. Would you like me to help you find the booking page?",
                "It sounds like you might benefit from speaking to a professional. Our consultants are here to help.",
            ],
            'work': [
                "Work can be a major source of stress. Remember to take breaks. Have you stepped away from your screen recently?",
                "Balancing work and life is a continuous challenge. What's one boundary you can set today?",
            ],
            'lonely': [
                "Loneliness is a universal human feeling, but it hurts. I'm here with you. Do you have a friend you could text right now?",
                "Connection is important. Even small interactions count. How about sending a kind message to someone you know?",
            ],
            'default': [
                "I'm listening. Please tell me more about that.",
                "I see. How does that make you feel?",
                "Thank you for sharing that with me. Go on.",
                "I'm here with you. What else is on your mind?",
                "That sounds important. Can you elaborate?",
                "I appreciate you opening up. How long have you felt this way?",
                "I'm checking in—how is your body feeling as you talk about this?",
                "That's interesting. What do you think led to this?",
                "I hear you. It's safe to share more if you'd like.",
            ]
        }
        
        self.patterns = {
            'greeting': r'\b(hi|hello|hey|good morning|good evening|greetings)\b',
            'stress': r'\b(stress|stressed|overwhelm|pressure|too much|tense)\b',
            'anxiety': r'\b(anxious|anxiety|worried|worry|nervous|panic|scared|fear)\b',
            'sad': r'\b(sad|depressed|down|unhappy|lonely|alone|cry|crying|tears)\b',
            'sleep': r'\b(sleep|insomnia|tired|exhausted|rest|awake|night)\b',
            'exercise': r'\b(exercise|workout|fitness|active|movement|walk|run|gym)\b',
            'gratitude': r'\b(grateful|gratitude|thankful|appreciate|blessed)\b',
            'motivation': r'\b(motivat|unmotivat|lazy|procrastinat|stuck)\b',
            'positive': r'\b(good|great|happy|better|wonderful|amazing|excellent|joy|love)\b',
            'help': r'\b(help|what can you|how do you|what do you|support)\b',
            'professional': r'\b(therapist|counselor|consultant|professional help|doctor)\b',
            'work': r'\b(work|job|boss|career|office|deadline)\b',
            'lonely': r'\b(lonely|alone|isolation|friend|friends)\b',
            
            # Flow triggers
            'trigger_grounding': r'\b(grounding|5-4-3-2-1|54321|focus|center)\b',
            'trigger_breathing': r'\b(breath|breathing|4-7-8|calm down|inhale|exhale)\b',
            'trigger_yes': r'\b(yes|sure|okay|yeah|yep|please|ok|do it)\b',
            'trigger_no': r'\b(no|nope|nah|pas|later|stop|don\'t|quit)\b'
        }
    
    def get_response(self, message: str, conversation_history: list = None) -> str:
        """Generate a response based on the user's message and history"""
        message_lower = message.lower()
        
        # 1. Check if we are in an active flow
        active_flow_response = self._check_active_flow(conversation_history)
        if active_flow_response:
            # If the user says "no" or "stop" to continuing a flow, break out
            if re.search(self.patterns['trigger_no'], message_lower):
                return "That's completely okay. We can stop. How else can I support you right now?"
            return active_flow_response

        # 2. Check for flow triggers in current message
        if re.search(self.patterns['trigger_grounding'], message_lower):
            return self.flows['54321']['steps'][0]
        
        if re.search(self.patterns['trigger_breathing'], message_lower):
            return self.flows['breathing']['steps'][0]

        # 3. Check for reflection patterns (I feel...)
        reflection_match = re.search(r'\bi (feel|am) ([a-z]+)', message_lower)
        if reflection_match and len(message_lower.split()) < 10:  # Only for short simpler sentences
            feeling = reflection_match.group(2)
            # Avoid repeating valid keywords if they act as triggers (handled below), but catch others
            if feeling not in ['grounding', 'breathing', 'ready']:
                # random chance to reflect or fall through to specific category
                if random.random() < 0.3:
                    return f"I understand that you feel {feeling}. Can you tell me more about what's making you feel {feeling}?"

        # 4. Check for general patterns
        for category, pattern in self.patterns.items():
            if category.startswith('trigger_'): continue # Skip flow triggers checked above
            if re.search(pattern, message_lower, re.IGNORECASE):
                return self._get_varied_response(category, conversation_history)
        
        # 5. Contextual "Yes" handling (if user says "yes" without a clear trigger)
        if conversation_history and len(conversation_history) > 0 and re.search(self.patterns['trigger_yes'], message_lower):
            last_bot_msg = self._get_last_bot_message(conversation_history)
            if last_bot_msg:
                if 'grounding' in last_bot_msg.lower() or '5-4-3-2-1' in last_bot_msg:
                    return self.flows['54321']['steps'][0]
                if 'breath' in last_bot_msg.lower():
                    return self.flows['breathing']['steps'][0]
        
        # 6. Default response
        return self._get_varied_response('default', conversation_history)

    def _check_active_flow(self, history):
        """Check if the conversation is currently inside a flow"""
        last_bot_msg = self._get_last_bot_message(history)
        
        if not last_bot_msg:
            return None

        # Check which flow and step we are in using fuzzy matching
        for flow_name, flow_data in self.flows.items():
            for i, step in enumerate(flow_data['steps']):
                # Simple fuzzy match: check if the first 15 chars match or last 15 chars match
                # This handles minor differences or truncations
                clean_step = step.strip()
                clean_last = last_bot_msg.strip()
                
                # Check for exact match or partial match
                match = (clean_step == clean_last) or \
                        (len(clean_step) > 20 and clean_step[:20] == clean_last[:20]) or \
                        (len(clean_step) > 20 and clean_step[-20:] == clean_last[-20:])
                
                if match:
                    # valid match, return the NEXT step
                    if i + 1 < len(flow_data['steps']):
                        return flow_data['steps'][i + 1]
                    else:
                        # Flow finished
                        return None
        return None

    def _get_last_bot_message(self, history):
        """Get the content of the last message from the bot"""
        if not history:
            return None
        
        for msg in reversed(history):
            if not msg.get('is_user'): # It's a bot message
                return msg.get('content')
        return None

    def _get_varied_response(self, category, history):
        """Get a response that isn't the same as the last one"""
        options = self.responses.get(category, self.responses['default'])
        
        # Try to avoid the exact same response as last time
        last_bot_msg = self._get_last_bot_message(history)
        
        # Filter out the last message from options if possible
        valid_options = [opt for opt in options if opt != last_bot_msg]
        
        if not valid_options: # If we exhausted options (shouldn't happen with default), reset
            valid_options = options
            
        return random.choice(valid_options)
    
    def get_greeting(self) -> str:
        """Get a greeting message"""
        hour = datetime.now().hour
        if hour < 12:
            greeting = "Good morning"
        elif hour < 18:
            greeting = "Good afternoon"
        else:
            greeting = "Good evening"
        
        return f"{greeting}! I'm your AI wellbeing assistant. I can guide you through grounding exercises, breathing techniques, or just listen to how you're feeling."

# Global instance
simple_bot = SimpleWellbeingBot()
