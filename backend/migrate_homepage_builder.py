"""
Migration script to create homepage_sections table
Run this to add the Home Page Builder feature
"""

import sys
import os

# Add parent directory to path to import models
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import engine, SessionLocal
from models import Base, HomePageSection, User
from datetime import datetime

def create_homepage_sections_table():
    """Create the homepage_sections table"""
    try:
        print("Creating homepage_sections table...")
        # Create all tables (this will only create missing ones)
        Base.metadata.create_all(bind=engine)
        print("Table created successfully!")
        
        # Add default welcome section
        db = SessionLocal()
        try:
            # Check if default section already exists
            existing = db.query(HomePageSection).filter(HomePageSection.title == "Welcome Section").first()
            if existing:
                print("Default section already exists!")
                return
                
            default_section = HomePageSection(
                title="Welcome Section",
                html_content="""
                <div class="hero-section">
                    <h1>Welcome to SolaceSquad</h1>
                    <p>Your trusted partner in mental wellness and wellbeing</p>
                    <a href="/signup" class="cta-button">Get Started</a>
                </div>
                """,
                css_content="""
                .hero-section {
                    text-align: center;
                    padding: 80px 20px;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                }
                .hero-section h1 {
                    font-size: 3rem;
                    margin-bottom: 1rem;
                }
                .cta-button {
                    display: inline-block;
                    padding: 12px 32px;
                    background: white;
                    color: #667eea;
                    text-decoration: none;
                    border-radius: 8px;
                    font-weight: 600;
                    margin-top: 2rem;
                }
                """,
                order_index=1,
                is_published=True
            )
            db.add(default_section)
            db.commit()
            print("Default welcome section added!")
        except Exception as e:
            print(f"Note: Could not add default section: {e}")
        finally:
            db.close()
            
    except Exception as e:
        print(f"Error creating table: {e}")
        sys.exit(1)

if __name__ == "__main__":
    create_homepage_sections_table()
