"""
Apple Health Export Import
Routes (all via this file):
  POST /api/import/apple-health  → parse ZIP/XML, create WorkoutLog entries

The GET /app/import/apple-health page is registered in main.py to avoid circular imports.
"""

import io
import os
import zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import date, datetime

from fastapi import APIRouter, Request, UploadFile, File, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from database import get_db
from models import User, WorkoutLog

router = APIRouter()

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Apple Health workout type → our workout type
_APPLE_TYPE_MAP = {
    "HKWorkoutActivityTypeRunning":          "Running",
    "HKWorkoutActivityTypeWalking":          "Walking",
    "HKWorkoutActivityTypeCycling":          "Cycling",
    "HKWorkoutActivityTypeSwimming":         "Swimming",
    "HKWorkoutActivityTypeYoga":             "Yoga",
    "HKWorkoutActivityTypeTraditionalStrengthTraining": "Strength",
    "HKWorkoutActivityTypeFunctionalStrengthTraining":  "Strength",
    "HKWorkoutActivityTypeHighIntensityIntervalTraining": "HIIT",
    "HKWorkoutActivityTypePilates":          "Pilates",
    "HKWorkoutActivityTypeDance":            "Dancing",
    "HKWorkoutActivityTypeMindAndBody":      "Meditation",
    "HKWorkoutActivityTypeSoccer":           "Sports",
    "HKWorkoutActivityTypeBasketball":       "Sports",
    "HKWorkoutActivityTypeRowingMachine":    "Rowing",
    "HKWorkoutActivityTypeBoxing":           "Boxing",
    "HKWorkoutActivityTypeClimbing":         "Climbing",
    "HKWorkoutActivityTypeStretching":       "Stretching",
}


def _parse_export_xml(xml_bytes: bytes) -> list[dict]:
    """Parse Apple Health Export.xml and return list of workout dicts."""
    root = ET.fromstring(xml_bytes)
    results = []

    # ── Process <Workout> records ──────────────────────────────────────────────
    for wk in root.findall(".//Workout"):
        raw_type = wk.get("workoutActivityType", "")
        workout_type = _APPLE_TYPE_MAP.get(raw_type, "Other")

        start_str = wk.get("startDate", "")
        if not start_str:
            continue
        try:
            start_dt = datetime.fromisoformat(start_str[:19])
            log_date = start_dt.date()
        except ValueError:
            continue

        duration_min = 0
        duration_val = wk.get("duration")
        dur_unit     = wk.get("durationUnit", "min")
        if duration_val:
            try:
                d = float(duration_val)
                duration_min = int(d if dur_unit == "min" else d / 60)
            except ValueError:
                pass

        calories = 0
        for stat in wk.findall("WorkoutStatistics"):
            if stat.get("type") == "HKQuantityTypeIdentifierActiveEnergyBurned":
                try:
                    calories = int(float(stat.get("sum", 0)))
                except ValueError:
                    pass

        steps = 0
        for stat in wk.findall("WorkoutStatistics"):
            if stat.get("type") == "HKQuantityTypeIdentifierStepCount":
                try:
                    steps = int(float(stat.get("sum", 0)))
                except ValueError:
                    pass

        results.append({
            "log_date":     log_date,
            "workout_type": workout_type,
            "duration_min": duration_min,
            "calories":     calories,
            "step_count":   steps,
            "source":       "Apple Health",
        })

    # ── Aggregate daily step counts from <Record> if no Workout steps ─────────
    daily_steps: dict[date, int] = defaultdict(int)
    for rec in root.findall(".//Record[@type='HKQuantityTypeIdentifierStepCount']"):
        start_str = rec.get("startDate", "")
        if not start_str:
            continue
        try:
            d = datetime.fromisoformat(start_str[:19]).date()
            daily_steps[d] += int(float(rec.get("value", 0)))
        except (ValueError, TypeError):
            pass

    # Surface days that only have step records (no explicit workout)
    workout_dates = {r["log_date"] for r in results}
    for d, steps in daily_steps.items():
        if d not in workout_dates and steps > 1000:
            results.append({
                "log_date":     d,
                "workout_type": "Walking",
                "duration_min": 0,
                "calories":     0,
                "step_count":   steps,
                "source":       "Apple Health",
            })

    return results


# ── Import Endpoint ────────────────────────────────────────────────────────────

@router.post("/api/import/apple-health")
async def import_apple_health(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    user_id = request.session.get("user_id")
    if not user_id:
        return JSONResponse({"error": "Not logged in"}, status_code=401)

    from subscription_routes import get_active_subscription
    sub = get_active_subscription(user_id, db)
    if not sub or not sub.plan or sub.plan.is_free:
        return JSONResponse({"error": "Apple Health integration is only available on the White plan and above. Upgrade your plan to unlock."}, status_code=403)

    content_type = file.content_type or ""
    filename     = file.filename or ""

    raw_bytes = await file.read()
    xml_bytes = None

    # Accept: .zip (Apple's export format) or raw .xml
    if filename.endswith(".zip") or "zip" in content_type:
        try:
            with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
                # Look for Export.xml inside the zip
                for name in zf.namelist():
                    if name.endswith("Export.xml"):
                        xml_bytes = zf.read(name)
                        break
        except zipfile.BadZipFile:
            return JSONResponse({"error": "Invalid ZIP file"}, status_code=400)
    elif filename.endswith(".xml") or "xml" in content_type:
        xml_bytes = raw_bytes

    if not xml_bytes:
        return JSONResponse(
            {"error": "Could not find Export.xml in the uploaded file. Upload the apple_health_export.zip directly from the Health app."},
            status_code=400,
        )

    # Parse
    try:
        entries = _parse_export_xml(xml_bytes)
    except ET.ParseError as e:
        return JSONResponse({"error": f"XML parse error: {str(e)}"}, status_code=400)

    if not entries:
        return JSONResponse({"success": True, "imported": 0, "message": "No workout records found in the export."})

    # Insert into DB — skip duplicates
    imported = 0
    for e in entries:
        existing = db.query(WorkoutLog).filter(
            WorkoutLog.user_id      == user_id,
            WorkoutLog.log_date     == e["log_date"],
            WorkoutLog.workout_type == e["workout_type"],
            WorkoutLog.notes.like("%Apple Health%"),
        ).first()

        if not existing:
            wl = WorkoutLog(
                user_id=user_id,
                log_date=e["log_date"],
                workout_type=e["workout_type"],
                duration_min=e["duration_min"],
                calories=e["calories"],
                step_count=e["step_count"],
                notes="Apple Health import",
            )
            db.add(wl)
            imported += 1

    db.commit()
    print(f"[AppleHealth] Imported {imported}/{len(entries)} entries for user {user_id}")

    # Recalculate daily wellness/lifestyle score after sync
    try:
        from main import compute_and_save_wellness
        imported_dates = {e["log_date"] for e in entries}
        for d in imported_dates:
            compute_and_save_wellness(user_id, db, for_date=d)
    except Exception as e:
        print(f"[AppleHealth] Wellness score recalculation failed: {e}")

    return JSONResponse({
        "success":  True,
        "imported": imported,
        "total":    len(entries),
        "message":  f"Successfully imported {imported} workout entries from Apple Health.",
    })
