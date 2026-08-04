"""
Database migration script to add journal_entries table
Run this to create the journal_entries table in the database
"""

import sys
import os

# Add parent directory to path to import models
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import get_engine
from backend.models import Base, JournalEntry

def create_journal_table():
    """Create the journal_entries table"""
    try:
        engine = get_engine()
        
        # Create only the journal_entries table
        JournalEntry.__table__.create(engine, checkfirst=True)
        
        print("✓ Successfully created journal_entries table")
        return True
    except Exception as e:
        print(f"✗ Error creating journal_entries table: {str(e)}")
        return False

if __name__ == "__main__":
    print("Creating journal_entries table...")
    success = create_journal_table()
    
    if success:
        print("\n✓ Migration completed successfully!")
        print("You can now use the journal feature.")
    else:
        print("\n✗ Migration failed!")
        sys.exit(1)
