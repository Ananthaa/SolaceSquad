#!/usr/bin/env python3
"""
SolaceSquad - Automated Google Play Store Publisher
Deploys Android App Bundles (.aab) directly to Google Play Console via Google Play Developer API v3.

Usage:
  python publish_to_playstore.py --track internal
  python publish_to_playstore.py --track production --notes "New features and bug fixes"
  python publish_to_playstore.py --build --track internal
"""

import os
import sys
import argparse
import subprocess

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2 import service_account

PACKAGE_NAME = "com.ssq2_and.solacesquad"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
KEY_FILE = os.path.join(SCRIPT_DIR, "app", "play-store-key.json")
DEFAULT_AAB = os.path.join(SCRIPT_DIR, "app", "build", "outputs", "bundle", "release", "app-release.aab")

def build_aab():
    print("🔨 [1/4] Building Android App Bundle (Release)...")
    gradle_cmd = os.path.join(SCRIPT_DIR, "gradlew.bat" if sys.platform == "win32" else "gradlew")
    res = subprocess.run([gradle_cmd, "bundleRelease"], cwd=SCRIPT_DIR)
    if res.returncode != 0:
        print("❌ Gradle build failed!")
        sys.exit(1)
    print("✅ Build completed successfully!")

def publish(track="internal", notes="Bug fixes and performance improvements", aab_path=DEFAULT_AAB, skip_build=False):
    if not skip_build and not os.path.exists(aab_path):
        build_aab()

    if not os.path.exists(aab_path):
        print(f"❌ AAB file not found at: {aab_path}")
        sys.exit(1)

    if not os.path.exists(KEY_FILE):
        print(f"❌ Service account key file missing at: {KEY_FILE}")
        print("Please place play-store-key.json in android-wrapper/app/")
        sys.exit(1)

    print(f"🚀 [2/4] Authenticating with Google Play Developer API...")
    scopes = ["https://www.googleapis.com/auth/androidpublisher"]
    credentials = service_account.Credentials.from_service_account_file(KEY_FILE, scopes=scopes)
    service = build("androidpublisher", "v3", credentials=credentials)

    print(f"📦 [3/4] Creating edit session and uploading bundle: {os.path.basename(aab_path)}...")
    edit_request = service.edits().insert(body={}, packageName=PACKAGE_NAME)
    edit_response = edit_request.execute()
    edit_id = edit_response["id"]

    # Upload AAB
    media = MediaFileUpload(aab_path, mimetype="application/octet-stream", resumable=True)
    bundle_response = service.edits().bundles().upload(
        packageName=PACKAGE_NAME,
        editId=edit_id,
        media_body=media
    ).execute()
    version_code = bundle_response["versionCode"]
    print(f"✅ Uploaded versionCode: {version_code} successfully!")

    # Assign track & release notes
    print(f"🎯 [4/4] Assigning to track: '{track}'...")
    track_body = {
        "track": track,
        "releases": [{
            "name": f"Version {version_code}",
            "versionCodes": [str(version_code)],
            "status": "completed",
            "releaseNotes": [{
                "language": "en-IN",
                "text": notes
            }, {
                "language": "en-US",
                "text": notes
            }]
        }]
    }

    service.edits().tracks().update(
        packageName=PACKAGE_NAME,
        editId=edit_id,
        track=track,
        body=track_body
    ).execute()

    # Commit the release
    commit_response = service.edits().commit(
        packageName=PACKAGE_NAME,
        editId=edit_id
    ).execute()

    print("\n" + "="*60)
    print(f"🎉 SUCCESS! Release {version_code} deployed directly to track '{track}'!")
    print(f"📱 Testers will receive update automatically on Google Play.")
    print("="*60 + "\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Automated Google Play Store Publisher")
    parser.add_argument("--track", default="internal", choices=["internal", "alpha", "beta", "production"], help="Google Play Track (default: internal)")
    parser.add_argument("--notes", default="Bug fixes and performance improvements", help="Release notes text")
    parser.add_argument("--aab", default=DEFAULT_AAB, help="Custom path to .aab file")
    parser.add_argument("--build", action="store_true", help="Build bundle before uploading")
    parser.add_argument("--skip-build", action="store_true", help="Use existing AAB without rebuilding")

    args = parser.parse_args()
    if args.build:
        build_aab()
    publish(track=args.track, notes=args.notes, aab_path=args.aab, skip_build=args.skip_build or not args.build)
