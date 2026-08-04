"""
Extract registered consultants from SolaceSquad production database.
Outputs: consultants_export.csv in the same directory.
"""
import psycopg2
import csv
import os
from datetime import datetime

# ── DB credentials from .env ─────────────────────────────────────────────────
DB_HOST     = "34.10.148.248"
DB_USER     = "postgres"
DB_PASSWORD = "SoulSquad2024x"
DB_NAME     = "solacesquad_prod"

print(f"Connecting to {DB_HOST}/{DB_NAME}...")

conn = psycopg2.connect(
    host=DB_HOST,
    user=DB_USER,
    password=DB_PASSWORD,
    dbname=DB_NAME,
    connect_timeout=10
)
cursor = conn.cursor()

query = """
SELECT
    u.id                        AS user_id,
    u.name                      AS name,
    u.email                     AS email,
    u.phone_number              AS phone,
    u.is_active                 AS is_active,
    u.email_verified            AS email_verified,
    u.created_at                AS registered_at,
    u.last_login                AS last_login,

    cp.specialization           AS specialization,
    cp.bio                      AS bio,
    cp.experience_years         AS experience_years,
    cp.is_approved              AS is_approved,
    cp.is_profile_completed     AS profile_completed,
    cp.is_available             AS is_available,
    cp.consultation_fee         AS consultation_fee,
    cp.city                     AS city,
    cp.highest_qualification    AS qualification,
    cp.languages                AS languages,
    cp.engagement_type          AS engagement_type,
    cp.expertise_areas          AS expertise_areas,
    cp.linkedin_url             AS linkedin,
    cp.cv_url                   AS cv_url,
    cp.photo_url                AS photo_url,
    cp.calls_scheduled          AS calls_scheduled,
    cp.calls_completed          AS calls_completed
FROM users u
LEFT JOIN consultant_profiles cp ON cp.user_id = u.id
WHERE u.user_type = 'consultant'
ORDER BY u.created_at DESC;
"""

cursor.execute(query)
rows = cursor.fetchall()
columns = [desc[0] for desc in cursor.description]

output_file = "consultants_export.csv"
with open(output_file, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=columns)
    writer.writeheader()
    for row in rows:
        writer.writerow(dict(zip(columns, row)))

cursor.close()
conn.close()

print(f"\n✅ Done! Exported {len(rows)} consultant(s) to: {output_file}")
print(f"   File location: {os.path.abspath(output_file)}")
print("\n── Summary ──────────────────────────────────────────────────")
print(f"{'#':<4} {'Name':<25} {'Email':<35} {'Approved':<10} {'Profile Done'}")
print("-" * 85)
for i, row in enumerate(rows, 1):
    data = dict(zip(columns, row))
    print(f"{i:<4} {str(data['name']):<25} {str(data['email']):<35} {str(data['is_approved']):<10} {data['profile_completed']}")
