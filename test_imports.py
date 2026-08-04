#!/usr/bin/env python3
"""
Test script to verify main.py can be imported without errors
"""
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

print("Testing main.py import...")
try:
    # Set required environment variables for testing
    os.environ['K_SERVICE'] = ''  # Not in production
    
    import main
    print("✓ main.py imported successfully!")
    print(f"✓ FastAPI app created: {main.app}")
    print(f"✓ App title: {main.app.title}")
    
except Exception as e:
    print(f"✗ Failed to import main.py: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\nAll imports successful!")
