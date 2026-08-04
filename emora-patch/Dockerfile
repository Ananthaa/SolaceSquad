# Emora-only patch image
# Base = exact production image (solacesquad-00474-dh7, April 8 state)
# Only gemini_chat.py and simple_bot.py are replaced.
# All other production files (main.py, models.py, etc.) are untouched.
FROM us-central1-docker.pkg.dev/abiding-idea-485817-k2/solacesquad/server@sha256:6a4e52d46b47a5c428463b856042e873f7a82d8a926e93d36e6e6918710b7c12

# Replace ONLY the two Emora chat files
COPY gemini_chat.py /app/gemini_chat.py
COPY simple_bot.py  /app/simple_bot.py
