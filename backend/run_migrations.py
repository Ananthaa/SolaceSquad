import os
import psycopg2
from google.cloud.sql.connector import Connector

def get_conn():
    instance = os.getenv("INSTANCE_CONNECTION_NAME")
    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD")
    db_name = os.getenv("DB_NAME", "solacesquad_prod")
    host = os.getenv("DB_HOST")

    if os.name == "nt" and instance and not host:
        connector = Connector()
        conn = connector.connect(
            instance,
            "pg8000",
            user=user,
            password=password,
            db=db_name
        )
        return conn
    else:
        conn = psycopg2.connect(
            user=user,
            password=password,
            dbname=db_name,
            host=host if host else f"/cloudsql/{instance}"
        )
        return conn

def run_migrations():
    print("Starting migrations...")
    migrations = [
        ("wellness_category on consultant_profiles", 
         "ALTER TABLE consultant_profiles ADD COLUMN IF NOT EXISTS wellness_category VARCHAR(20) DEFAULT NULL"),
        ("reminder_sent on appointments", 
         "ALTER TABLE appointments ADD COLUMN IF NOT EXISTS reminder_sent BOOLEAN DEFAULT FALSE"),
        ("mirror_reminder_sent on appointments", 
         "ALTER TABLE appointments ADD COLUMN IF NOT EXISTS mirror_reminder_sent BOOLEAN DEFAULT FALSE"),
        ("red_flagged on appointments", 
         "ALTER TABLE appointments ADD COLUMN IF NOT EXISTS red_flagged BOOLEAN DEFAULT FALSE"),
        ("red_flag_reason on appointments", 
         "ALTER TABLE appointments ADD COLUMN IF NOT EXISTS red_flag_reason TEXT DEFAULT NULL"),
        ("demo_videos table creation",
         """CREATE TABLE IF NOT EXISTS demo_videos (
             id SERIAL PRIMARY KEY,
             title VARCHAR(255) NOT NULL,
             description TEXT,
             video_url VARCHAR(500) NOT NULL,
             is_youtube BOOLEAN NOT NULL DEFAULT FALSE,
             share_with VARCHAR(20) NOT NULL DEFAULT 'both',
             created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
         )"""),
        ("author_image on event_workshops",
         "ALTER TABLE event_workshops ADD COLUMN IF NOT EXISTS author_image VARCHAR(500) DEFAULT NULL"),
        ("user_device_tokens table creation",
         """CREATE TABLE IF NOT EXISTS user_device_tokens (
             id SERIAL PRIMARY KEY,
             user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
             fcm_token VARCHAR(500) UNIQUE NOT NULL,
             device_type VARCHAR(50) NOT NULL DEFAULT 'android',
             updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
         )"""),
        ("push_30m_sent on appointments",
         "ALTER TABLE appointments ADD COLUMN IF NOT EXISTS push_30m_sent BOOLEAN NOT NULL DEFAULT FALSE"),
        ("mirror_push_30m_sent on appointments",
         "ALTER TABLE appointments ADD COLUMN IF NOT EXISTS mirror_push_30m_sent BOOLEAN NOT NULL DEFAULT FALSE"),
        ("push_notification_schedules table creation",
         """CREATE TABLE IF NOT EXISTS push_notification_schedules (
             id SERIAL PRIMARY KEY,
             notification_type VARCHAR(100) UNIQUE NOT NULL,
             title VARCHAR(200) NOT NULL,
             body VARCHAR(500) NOT NULL,
             is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
             repeat_cycle VARCHAR(50) NOT NULL DEFAULT 'daily',
             delivery_time VARCHAR(50),
             day_of_week INTEGER,
             day_of_month INTEGER,
             threshold_value INTEGER,
             updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
         )"""),
        ("sponsor_config on event_workshops", 
         "ALTER TABLE event_workshops ADD COLUMN IF NOT EXISTS sponsor_config TEXT DEFAULT NULL"),
    ]
    
    conn = get_conn()
    conn.autocommit = True
    cur = conn.cursor()
    
    for label, sql in migrations:
        try:
            print(f"Running: {label}")
            cur.execute(sql)
            print(f"Success: {label}")
        except Exception as e:
            print(f"Error on {label}: {e}")

    # Seed default push schedules
    print("Seeding default push schedules...")
    default_schedules = [
        ("mood_checkin", "Daily Mood Check-in", "How are you feeling now? Track your mood.", "daily", "18:00", None),
        ("vital_scan", "Vital Scan Reminder", "Do your vital scan today to track your wellness score!", "daily", "09:00", None),
        ("workout_log", "Workout Log", "Log your workout today to stay on track!", "daily", "20:00", None),
        ("appointment_reminder", "Upcoming Session Reminder", "Your consultation starts in 30 minutes. Tap to join!", "daily", None, None),
        ("recharge_reminder", "Plan Renewal Reminder", "Your SolaceSquad subscription is expiring soon. Recharge now to continue benefits!", "daily", None, 3),
        ("emora_low_balance", "Emora Balance Low", "You have less than 5 messages left with Emora. Top up your pack now!", "daily", None, 5)
    ]
    for ntype, title, body, cycle, dtime, thresh in default_schedules:
        try:
            cur.execute("""
                INSERT INTO push_notification_schedules (notification_type, title, body, repeat_cycle, delivery_time, threshold_value)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (notification_type) DO NOTHING
            """, (ntype, title, body, cycle, dtime, thresh))
        except Exception as e:
            print(f"Error seeding schedule {ntype}: {e}")
            
    cur.close()
    conn.close()
    print("Migrations complete.")

if __name__ == "__main__":
    run_migrations()
