# ─── Stage 1: Build Tailwind CSS ──────────────────────────────────────────
# Uses Node.js to compile all Tailwind utility classes from templates into
# a single minified CSS file. This replaces the render-blocking CDN script.
FROM node:20-slim AS css-builder

WORKDIR /build

# Copy only what's needed for Tailwind compilation
COPY tailwind.config.js ./
COPY static/css/tailwind.input.css ./static/css/
COPY templates/ ./templates/
COPY static/ ./static/

# Install Tailwind CLI + Typography plugin
RUN npm install --save-dev tailwindcss@3 @tailwindcss/typography

# Compile → minified output served as /static/css/tailwind.min.css
RUN npx tailwindcss \
      -c tailwind.config.js \
      -i ./static/css/tailwind.input.css \
      -o ./static/css/tailwind.min.css \
      --minify

# ─── Stage 2: Python runtime ──────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# ✅ Overwrite with the compiled Tailwind CSS from the builder stage
COPY --from=css-builder /build/static/css/tailwind.min.css ./static/css/tailwind.min.css

# Expose port (Cloud Run will set PORT env var)
EXPOSE 8080

# Run application (Socket.IO is mounted at /socket.io)
CMD uvicorn main:app --host 0.0.0.0 --port $PORT
