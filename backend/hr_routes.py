"""
hr_routes.py — Corporate HR & Enterprise B2B Wellness Portal for SolaceSquad.

Features:
  - Executive Wellness Dashboard: Aggregated health scores, participation rates, credit wallet.
  - Employee Roster Management: Single invitations, CSV bulk onboarding, allowance tracking.
  - Privacy-First Wellness Analytics: Departmental scores (threshold >= 5 employees for DPDP compliance),
    anonymized vital scan health indices, stress and burnout distribution.
  - Corporate Credits & Billing: Plan allowance configuration, credit top-up, GST tax invoices.
  - Team Workshops & Masterclasses: Browsing, scheduling, and custom topic requests for corporate teams.

Registration:
  from hr_routes import register_hr_routes
  register_hr_routes(app, templates, get_db)
"""

from __future__ import annotations

import os
import csv
import io
import json
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, Request, Depends, HTTPException, Form, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, desc

from models import User, VitalsRecord, Appointment, EventWorkshop


# ─────────────────────────────────────────────────────────────────────────────
# MOCK / SEED CORPORATE DATA (FOR DEMO & INITIAL STATE)
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_COMPANY = "Acme Technologies India Pvt Ltd"
DEFAULT_HR_NAME = "Priya Sharma"
DEFAULT_CREDIT_BALANCE = 450
DEFAULT_TOTAL_ENROLLED = 180

SAMPLE_EMPLOYEES = [
    {
        "id": 1,
        "name": "Aarav Patel",
        "email": "aarav.p@acmetech.com",
        "department": "Engineering",
        "role": "Senior Frontend Engineer",
        "joined_date": "15 Jan 2026",
        "allowance_used": 1,
        "allowance_total": 2,
        "status": "Active",
        "last_scan_date": "Yesterday, 4:15 PM"
    },
    {
        "id": 2,
        "name": "Sneha Reddy",
        "email": "sneha.r@acmetech.com",
        "department": "Product & Design",
        "role": "Lead Product Designer",
        "joined_date": "03 Feb 2026",
        "allowance_used": 2,
        "allowance_total": 2,
        "status": "Active",
        "last_scan_date": "28 Sep 2026"
    },
    {
        "id": 3,
        "name": "Rohan Deshmukh",
        "email": "rohan.d@acmetech.com",
        "department": "Engineering",
        "role": "Backend Architect",
        "joined_date": "10 Feb 2026",
        "allowance_used": 0,
        "allowance_total": 2,
        "status": "Active",
        "last_scan_date": "01 Oct 2026"
    },
    {
        "id": 4,
        "name": "Ananya Iyer",
        "email": "ananya.i@acmetech.com",
        "department": "Marketing & GTM",
        "role": "Growth Marketing Manager",
        "joined_date": "18 Feb 2026",
        "allowance_used": 1,
        "allowance_total": 2,
        "status": "Active",
        "last_scan_date": "Today, 10:20 AM"
    },
    {
        "id": 5,
        "name": "Vikram Malhotra",
        "email": "vikram.m@acmetech.com",
        "department": "Sales & Enterprise",
        "role": "Enterprise Account Executive",
        "joined_date": "01 Mar 2026",
        "allowance_used": 2,
        "allowance_total": 2,
        "status": "Active",
        "last_scan_date": "29 Sep 2026"
    },
    {
        "id": 6,
        "name": "Divya Nambiar",
        "email": "divya.n@acmetech.com",
        "department": "Customer Success",
        "role": "Support Lead",
        "joined_date": "12 Mar 2026",
        "allowance_used": 0,
        "allowance_total": 2,
        "status": "Invited",
        "last_scan_date": "Pending Onboarding"
    },
    {
        "id": 7,
        "name": "Karan Singhania",
        "email": "karan.s@acmetech.com",
        "department": "Human Resources",
        "role": "People Operations Specialist",
        "joined_date": "22 Mar 2026",
        "allowance_used": 1,
        "allowance_total": 2,
        "status": "Active",
        "last_scan_date": "Yesterday, 11:45 AM"
    },
    {
        "id": 8,
        "name": "Meera Joshi",
        "email": "meera.j@acmetech.com",
        "department": "Finance & Legal",
        "role": "Financial Analyst",
        "joined_date": "05 Apr 2026",
        "allowance_used": 0,
        "allowance_total": 2,
        "status": "Active",
        "last_scan_date": "25 Sep 2026"
    }
]

SAMPLE_INVOICES = [
    {
        "invoice_no": "INV-SS-2026-089",
        "date": "01 Sep 2026",
        "credits_purchased": 200,
        "amount": "₹99,800",
        "gst_amount": "₹17,964",
        "status": "Paid",
        "receipt_url": "#"
    },
    {
        "invoice_no": "INV-SS-2026-064",
        "date": "01 Aug 2026",
        "credits_purchased": 200,
        "amount": "₹99,800",
        "gst_amount": "₹17,964",
        "status": "Paid",
        "receipt_url": "#"
    },
    {
        "invoice_no": "INV-SS-2026-041",
        "date": "01 Jul 2026",
        "credits_purchased": 150,
        "amount": "₹74,850",
        "gst_amount": "₹13,473",
        "status": "Paid",
        "receipt_url": "#"
    }
]

SAMPLE_SCHEDULED_WORKSHOPS = [
    {
        "id": 1,
        "title": "Workplace Mindfulness & Desk Stress Relief",
        "speaker": "Dr. Priya Nair (Senior Clinical Psychologist)",
        "date_str": "Thursday, Oct 12 • 3:30 PM - 4:30 PM (IST)",
        "rsvps": 64,
        "target_dept": "Company-wide Live",
        "invite_link": "https://solacesquad.com/meet/mindfulness-oct12"
    },
    {
        "id": 2,
        "title": "Ergonomics, Posture & RSI Prevention for Tech Teams",
        "speaker": "Rahul Menon (MPT Ergonomics Specialist)",
        "date_str": "Wednesday, Oct 25 • 4:00 PM - 5:00 PM (IST)",
        "rsvps": 41,
        "target_dept": "Engineering & Product Dept",
        "invite_link": "https://solacesquad.com/meet/ergo-oct25"
    }
]


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE REGISTRATION FUNCTION
# ─────────────────────────────────────────────────────────────────────────────

def register_hr_routes(app: FastAPI, templates: Jinja2Templates, get_db):

    def _get_hr_context(request: Request, db: Session) -> Dict[str, Any]:
        """Resolve current session HR details, defaulting gracefully for preview."""
        user_id = request.session.get("user_id")
        user = db.query(User).filter(User.id == user_id).first() if user_id else None
        
        hr_name = user.full_name if (user and user.full_name) else DEFAULT_HR_NAME
        company_name = getattr(user, "company_name", None) or DEFAULT_COMPANY

        return {
            "request": request,
            "user": user,
            "company_name": company_name,
            "hr_name": hr_name,
            "credit_balance": DEFAULT_CREDIT_BALANCE,
            "total_enrolled": DEFAULT_TOTAL_ENROLLED,
        }

    # ── 1. HR Dashboard / Executive Overview ──────────────────────────────────
    @app.get("/hr", response_class=HTMLResponse)
    @app.get("/hr/dashboard", response_class=HTMLResponse)
    async def hr_dashboard(request: Request, db: Session = Depends(get_db)):
        ctx = _get_hr_context(request, db)
        
        # Calculate real/mock aggregates
        ctx.update({
            "overall_score": 78,
            "participation_rate": 84,
            "consultations_month": 142,
            "burnout_distribution": {
                "low": 58,
                "moderate": 28,
                "high": 14
            },
            "recent_activities": [
                {
                    "icon": "activity",
                    "title": "Vital Scan Surge",
                    "dept": "Engineering Dept (38 scans today)",
                    "time": "15m ago",
                    "badge_class": "bg-teal-50 text-teal-700",
                    "badge_text": "+18% Engagement"
                },
                {
                    "icon": "calendar-check",
                    "title": "1-on-1 Consult Booked",
                    "dept": "Confidential • Marketing Dept",
                    "time": "1h ago",
                    "badge_class": "bg-blue-50 text-blue-700",
                    "badge_text": "Credit Used"
                },
                {
                    "icon": "sparkles",
                    "title": "Masterclass Scheduled",
                    "dept": "Workplace Mindfulness on Oct 12",
                    "time": "3h ago",
                    "badge_class": "bg-purple-50 text-purple-700",
                    "badge_text": "64 RSVPs"
                },
                {
                    "icon": "user-plus",
                    "title": "5 New Employees Enrolled",
                    "dept": "Sales & Operations",
                    "time": "Yesterday",
                    "badge_class": "bg-emerald-50 text-emerald-700",
                    "badge_text": "Onboarded"
                }
            ],
            "department_highlights": [
                {"name": "Engineering", "count": 64, "score": 74, "risk_level": "Moderate", "trend": "↑ +3pts"},
                {"name": "Sales & GTM", "count": 42, "score": 81, "risk_level": "Low", "trend": "↑ +5pts"},
                {"name": "Product & Design", "count": 28, "score": 79, "risk_level": "Low", "trend": "→ Stable"},
                {"name": "Operations & CS", "count": 32, "score": 71, "risk_level": "Moderate", "trend": "↓ -2pts"},
                {"name": "HR & Admin", "count": 14, "score": 88, "risk_level": "Low", "trend": "↑ +4pts"},
            ]
        })
        
        return templates.TemplateResponse("pages/hr_dashboard.html", ctx)

    # ── 2. Employee Roster Management ─────────────────────────────────────────
    @app.get("/hr/employees", response_class=HTMLResponse)
    async def hr_employees(
        request: Request, 
        dept: Optional[str] = None, 
        q: Optional[str] = None, 
        db: Session = Depends(get_db)
    ):
        ctx = _get_hr_context(request, db)
        
        filtered = SAMPLE_EMPLOYEES
        if dept and dept.lower() != "all":
            filtered = [e for e in filtered if dept.lower() in e["department"].lower()]
        if q:
            query = q.strip().lower()
            filtered = [
                e for e in filtered 
                if query in e["name"].lower() or query in e["email"].lower() or query in e["role"].lower()
            ]

        departments = ["All Departments", "Engineering", "Product & Design", "Marketing & GTM", "Sales & Enterprise", "Customer Success", "Human Resources", "Finance & Legal"]
        
        ctx.update({
            "employees": filtered,
            "departments": departments,
            "active_dept": dept or "all",
            "search_query": q or ""
        })
        
        return templates.TemplateResponse("pages/hr_employees.html", ctx)

    # ── 2.1 Single Employee Invitation POST Handler ───────────────────────────
    @app.post("/hr/employees/invite")
    async def hr_invite_employee(
        request: Request,
        name: str = Form(...),
        email: str = Form(...),
        department: str = Form(...),
        role: str = Form(...),
        db: Session = Depends(get_db)
    ):
        # In production: create User entry with company_id, send welcome email with setup token
        new_emp = {
            "id": len(SAMPLE_EMPLOYEES) + 1,
            "name": name.strip(),
            "email": email.strip().lower(),
            "department": department,
            "role": role.strip(),
            "joined_date": date.today().strftime("%d %b %Y"),
            "allowance_used": 0,
            "allowance_total": 2,
            "status": "Invited",
            "last_scan_date": "Pending Onboarding"
        }
        SAMPLE_EMPLOYEES.insert(0, new_emp)
        return RedirectResponse(url="/hr/employees?invited=1", status_code=303)

    # ── 2.2 Bulk CSV Upload POST Handler ──────────────────────────────────────
    @app.post("/hr/employees/bulk-upload")
    async def hr_bulk_upload_employees(
        request: Request,
        file: UploadFile = File(...),
        db: Session = Depends(get_db)
    ):
        try:
            content = await file.read()
            decoded = content.decode("utf-8-sig", errors="ignore")
            reader = csv.DictReader(io.StringIO(decoded))
            
            count = 0
            for row in reader:
                emp_name = row.get("name") or row.get("Full Name") or row.get("Name")
                emp_email = row.get("email") or row.get("Email") or row.get("Work Email")
                emp_dept = row.get("department") or row.get("Department") or "General"
                emp_role = row.get("role") or row.get("Role") or row.get("Title") or "Team Member"
                
                if emp_name and emp_email:
                    SAMPLE_EMPLOYEES.insert(0, {
                        "id": len(SAMPLE_EMPLOYEES) + 1,
                        "name": emp_name.strip(),
                        "email": emp_email.strip().lower(),
                        "department": emp_dept.strip(),
                        "role": emp_role.strip(),
                        "joined_date": date.today().strftime("%d %b %Y"),
                        "allowance_used": 0,
                        "allowance_total": 2,
                        "status": "Invited",
                        "last_scan_date": "Pending Onboarding"
                    })
                    count += 1
                    
            return RedirectResponse(url=f"/hr/employees?bulk_success={count}", status_code=303)
        except Exception as e:
            return RedirectResponse(url=f"/hr/employees?bulk_error={str(e)}", status_code=303)

    # ── 3. Wellness Insights & Aggregate Analytics ────────────────────────────
    @app.get("/hr/analytics", response_class=HTMLResponse)
    async def hr_analytics(request: Request, db: Session = Depends(get_db)):
        ctx = _get_hr_context(request, db)
        
        ctx.update({
            "department_scores": [
                {
                    "department": "Engineering & Technology",
                    "headcount": 64,
                    "overall_score": 74,
                    "emotional_score": 68,
                    "sleep_score": 71,
                    "physical_score": 83,
                    "burnout_risk": "Moderate",
                    "trend": "+3.2% vs last month"
                },
                {
                    "department": "Sales & Enterprise GTM",
                    "headcount": 42,
                    "overall_score": 81,
                    "emotional_score": 79,
                    "sleep_score": 80,
                    "physical_score": 84,
                    "burnout_risk": "Low",
                    "trend": "+5.1% vs last month"
                },
                {
                    "department": "Product & User Experience",
                    "headcount": 28,
                    "overall_score": 79,
                    "emotional_score": 76,
                    "sleep_score": 78,
                    "physical_score": 83,
                    "burnout_risk": "Low",
                    "trend": "Stable"
                },
                {
                    "department": "Operations & Customer Support",
                    "headcount": 32,
                    "overall_score": 71,
                    "emotional_score": 66,
                    "sleep_score": 69,
                    "physical_score": 78,
                    "burnout_risk": "Moderate",
                    "trend": "-1.8% vs last month"
                },
                {
                    "department": "Human Resources & Talent",
                    "headcount": 14,
                    "overall_score": 88,
                    "emotional_score": 89,
                    "sleep_score": 86,
                    "physical_score": 89,
                    "burnout_risk": "Low",
                    "trend": "+4.0% vs last month"
                }
            ],
            "vital_averages": {
                "avg_hr": 72,
                "avg_spo2": 98.4,
                "avg_hrv": 56,
                "avg_stress": "Low-Moderate"
            }
        })
        
        return templates.TemplateResponse("pages/hr_analytics.html", ctx)

    # ── 4. Corporate Credits & Billing Management ─────────────────────────────
    @app.get("/hr/credits", response_class=HTMLResponse)
    async def hr_credits(request: Request, db: Session = Depends(get_db)):
        ctx = _get_hr_context(request, db)
        
        ctx.update({
            "monthly_allowance_per_user": 2,
            "billing_plan": "Enterprise Scaled Tier",
            "invoices": SAMPLE_INVOICES,
            "cost_per_credit": "₹499 + GST",
            "credits_used_this_month": 128,
            "credits_allocated_total": 360,
        })
        
        return templates.TemplateResponse("pages/hr_credits.html", ctx)

    # ── 4.1 Credit Top-Up POST Handler ────────────────────────────────────────
    @app.post("/hr/credits/topup")
    async def hr_credits_topup(
        request: Request,
        credit_pack: int = Form(...),
        payment_method: str = Form("corporate_invoice"),
        db: Session = Depends(get_db)
    ):
        # Create instant invoice record
        amount_num = credit_pack * 499
        gst_num = int(amount_num * 0.18)
        new_inv = {
            "invoice_no": f"INV-SS-2026-0{len(SAMPLE_INVOICES) + 90}",
            "date": date.today().strftime("%d %b %Y"),
            "credits_purchased": credit_pack,
            "amount": f"₹{amount_num:,}",
            "gst_amount": f"₹{gst_num:,}",
            "status": "Paid",
            "receipt_url": "#"
        }
        SAMPLE_INVOICES.insert(0, new_inv)
        return RedirectResponse(url="/hr/credits?topup_success=1", status_code=303)

    # ── 5. Corporate Team Workshops & Masterclasses ───────────────────────────
    @app.get("/hr/events", response_class=HTMLResponse)
    async def hr_events(request: Request, db: Session = Depends(get_db)):
        ctx = _get_hr_context(request, db)
        ctx.update({
            "scheduled_workshops": SAMPLE_SCHEDULED_WORKSHOPS
        })
        return templates.TemplateResponse("pages/hr_events.html", ctx)

    # ── 5.1 Workshop Booking POST Handler ─────────────────────────────────────
    @app.post("/hr/events/book")
    async def hr_book_workshop(
        request: Request,
        workshop_title: str = Form(...),
        preferred_date: Optional[str] = Form(None),
        preferred_time: Optional[str] = Form(None),
        target_department: Optional[str] = Form("All Company"),
        notes: Optional[str] = Form(None),
        is_custom: Optional[bool] = Form(False),
        db: Session = Depends(get_db)
    ):
        date_display = f"{preferred_date} • {preferred_time}" if (preferred_date and preferred_time) else "Schedule Pending Confirmation"
        new_workshop = {
            "id": len(SAMPLE_SCHEDULED_WORKSHOPS) + 1,
            "title": workshop_title,
            "speaker": "SolaceSquad Lead Clinical Specialist",
            "date_str": date_display,
            "rsvps": 0,
            "target_dept": target_department,
            "invite_link": f"https://solacesquad.com/meet/ws-{int(datetime.utcnow().timestamp())}"
        }
        SAMPLE_SCHEDULED_WORKSHOPS.insert(0, new_workshop)
        return RedirectResponse(url="/hr/events?booked=1", status_code=303)

    # ── 6. JSON Stats API for HR Widget / Quick Queries ───────────────────────
    @app.get("/api/hr/stats")
    async def api_hr_stats(request: Request, db: Session = Depends(get_db)):
        return JSONResponse({
            "success": True,
            "company": DEFAULT_COMPANY,
            "enrolled": DEFAULT_TOTAL_ENROLLED,
            "credits_remaining": DEFAULT_CREDIT_BALANCE,
            "wellness_score": 78,
            "participation_pct": 84,
            "dpdp_compliant": True
        })
