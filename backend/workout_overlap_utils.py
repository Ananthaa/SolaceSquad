"""
Multi-Device Workout Overlap & Deduplication Utilities
SolaceSquad Health Engine

Handles concurrent workout synchronization across Apple HealthKit,
Google Fit / Health Connect, Fitbit, and Strava.
"""

from datetime import date, datetime, timedelta
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func

from models import WorkoutLog


def derive_effective_duration(duration_min: int, step_count: int, workout_type: str = "Walking") -> int:
    """
    Ensure steps contribute to active workout minutes when background
    sync provides 0 duration. Standard brisk walking cadence: ~100 steps/min.
    """
    d = duration_min or 0
    s = step_count or 0
    if d <= 0 and s > 0 and any(w in (workout_type or "").lower() for w in ["walk", "step"]):
        return max(1, round(s / 100.0))
    return d


def detect_and_merge_workout(
    db: Session,
    user_id: int,
    log_date: date,
    workout_type: str,
    duration_min: int,
    step_count: int = 0,
    calories: int = 0,
    distance_km: Optional[float] = None,
    source: str = "manual",
    external_id: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    notes: Optional[str] = None,
) -> Tuple[WorkoutLog, bool]:
    """
    Ingest a workout with multi-device interval overlap detection and telemetry merging.
    Returns: (WorkoutLog record, is_new: bool)
    """
    # 1. Exact provider ID dedup check
    if external_id:
        existing_exact = db.query(WorkoutLog).filter(
            WorkoutLog.user_id == user_id,
            WorkoutLog.external_id == str(external_id),
            WorkoutLog.source == source,
        ).first()
        if existing_exact:
            # Update telemetry if incoming has higher values
            if step_count and step_count > (existing_exact.step_count or 0):
                existing_exact.step_count = step_count
            if calories and calories > (existing_exact.calories or 0):
                existing_exact.calories = calories
            if distance_km and (existing_exact.distance_km is None or distance_km > existing_exact.distance_km):
                existing_exact.distance_km = distance_km
            if start_time and not existing_exact.start_time:
                existing_exact.start_time = start_time
            if end_time and not existing_exact.end_time:
                existing_exact.end_time = end_time
            effective_d = derive_effective_duration(duration_min, existing_exact.step_count, workout_type)
            if effective_d > (existing_exact.duration_min or 0):
                existing_exact.duration_min = effective_d
            return existing_exact, False

    # 2. Derive effective duration if missing
    eff_duration = derive_effective_duration(duration_min, step_count, workout_type)

    # 3. Time-Interval Overlap Check against other devices on the same date
    if start_time and end_time and end_time > start_time:
        dur_sec = max(60, int((end_time - start_time).total_seconds()))
        # Buffer of 3 minutes for phone clock drift
        buffer_td = timedelta(minutes=3)
        
        candidates = db.query(WorkoutLog).filter(
            WorkoutLog.user_id == user_id,
            WorkoutLog.log_date == log_date,
            WorkoutLog.is_duplicate == False,
            WorkoutLog.start_time.isnot(None),
            WorkoutLog.end_time.isnot(None),
        ).all()

        for cand in candidates:
            c_start = cand.start_time
            c_end   = cand.end_time
            if not c_start or not c_end or c_end <= c_start:
                continue

            # Compute overlap window with drift tolerance
            o_start = max(start_time - buffer_td, c_start)
            o_end   = min(end_time + buffer_td, c_end)

            if o_end > o_start:
                overlap_sec = (o_end - o_start).total_seconds()
                cand_dur_sec = max(60, int((c_end - c_start).total_seconds()))
                min_dur = min(dur_sec, cand_dur_sec)

                # If overlap exceeds 50% of either workout, or >= 5 mins overlap
                if overlap_sec >= 0.50 * min_dur or overlap_sec >= 300:
                    print(f"[DEDUP] Detected multi-device workout overlap for user {user_id}: "
                          f"{source} ({start_time.strftime('%H:%M')}-{end_time.strftime('%H:%M')}) overlaps with "
                          f"{cand.source} ({c_start.strftime('%H:%M')}-{c_end.strftime('%H:%M')}) by {int(overlap_sec//60)} min")
                    
                    # Merge telemetry into primary (cand)
                    cand.step_count = max(cand.step_count or 0, step_count or 0)
                    cand.calories   = max(cand.calories or 0, calories or 0)
                    if distance_km and (cand.distance_km is None or distance_km > cand.distance_km):
                        cand.distance_km = distance_km
                    
                    # Expand time window to cover outer bounds
                    cand.start_time = min(cand.start_time, start_time)
                    cand.end_time   = max(cand.end_time, end_time)
                    cand.duration_min = max(cand.duration_min or 0, eff_duration, int((cand.end_time - cand.start_time).total_seconds() // 60))
                    
                    if source not in (cand.notes or ""):
                        cand.notes = (cand.notes or "").strip() + f" [Merged with {source}]"

                    # Save incoming record flagged as duplicate linked to primary
                    dup_record = WorkoutLog(
                        user_id      = user_id,
                        log_date     = log_date,
                        workout_type = workout_type,
                        duration_min = eff_duration,
                        step_count   = step_count or 0,
                        calories     = calories or 0,
                        distance_km  = distance_km,
                        source       = source,
                        external_id  = external_id,
                        start_time   = start_time,
                        end_time     = end_time,
                        notes        = f"Duplicate: merged into workout #{cand.id} ({cand.source})",
                        is_duplicate = True,
                        duplicate_of_id = cand.id,
                    )
                    db.add(dup_record)
                    return cand, False

    # 4. Daily Background Steps Check (e.g. Google Fit daily steps vs Apple Health daily steps)
    is_daily_steps_entry = "daily steps" in (workout_type or "").lower() or "daily steps" in (notes or "").lower()
    if is_daily_steps_entry and step_count > 0:
        existing_step_summary = db.query(WorkoutLog).filter(
            WorkoutLog.user_id == user_id,
            WorkoutLog.log_date == log_date,
            WorkoutLog.is_duplicate == False,
            WorkoutLog.notes.like("%daily steps%"),
        ).first()

        if existing_step_summary:
            # Reconcile daily background steps: take maximum, do not sum
            if step_count > (existing_step_summary.step_count or 0):
                existing_step_summary.step_count = step_count
                existing_step_summary.duration_min = derive_effective_duration(0, step_count, "Walking")
                if calories and calories > (existing_step_summary.calories or 0):
                    existing_step_summary.calories = calories
                existing_step_summary.notes = f"Daily steps synced: {step_count:,} steps (reconciled across devices)"
            return existing_step_summary, False

    # 5. No overlap detected: Create new master workout entry
    new_entry = WorkoutLog(
        user_id      = user_id,
        log_date     = log_date,
        workout_type = workout_type,
        duration_min = eff_duration,
        step_count   = step_count or 0,
        calories     = calories or 0,
        distance_km  = distance_km,
        source       = source,
        external_id  = external_id,
        start_time   = start_time,
        end_time     = end_time,
        notes        = notes or f"Synced from {source}",
        is_duplicate = False,
    )
    db.add(new_entry)
    return new_entry, True


def calculate_daily_active_minutes(db: Session, user_id: int, log_date: date) -> int:
    """
    Calculates the true total physical active minutes for a day by computing
    the mathematical union of all non-overlapping workout time intervals,
    plus untimed session durations and background step activity.
    """
    workouts = db.query(WorkoutLog).filter(
        WorkoutLog.user_id == user_id,
        WorkoutLog.log_date == log_date,
        WorkoutLog.is_duplicate == False,
    ).all()

    if not workouts:
        return 0

    timed_intervals: List[Tuple[datetime, datetime]] = []
    untimed_mins = 0
    max_steps = 0

    for w in workouts:
        if w.step_count and w.step_count > max_steps:
            max_steps = w.step_count

        if w.start_time and w.end_time and w.end_time > w.start_time:
            timed_intervals.append((w.start_time, w.end_time))
        elif w.duration_min and w.duration_min > 0:
            untimed_mins += w.duration_min

    # Disjoint interval union
    merged_timed_seconds = 0
    if timed_intervals:
        timed_intervals.sort(key=lambda x: x[0])
        curr_start, curr_end = timed_intervals[0]
        for nxt_start, nxt_end in timed_intervals[1:]:
            if nxt_start <= curr_end:
                curr_end = max(curr_end, nxt_end)
            else:
                merged_timed_seconds += (curr_end - curr_start).total_seconds()
                curr_start, curr_end = nxt_start, nxt_end
        merged_timed_seconds += (curr_end - curr_start).total_seconds()

    merged_timed_mins = int(merged_timed_seconds // 60)
    workout_mins = merged_timed_mins + untimed_mins

    # Derived duration from daily steps (100 steps/min)
    step_derived_mins = int(round(max_steps / 100.0)) if max_steps > 0 else 0

    return max(workout_mins, step_derived_mins)
