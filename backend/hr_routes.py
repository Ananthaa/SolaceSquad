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

from models import User, VitalsRecord, Appointment, EventWorkshop


# ─────────────────────────────────────────────────────────────────────────────
# MOCK / SEED CORPORATE DATA (24 DETAILED EMPLOYEES ACROSS 3 PAGES)
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_COMPANY = "Acme Technologies India Pvt Ltd"
DEFAULT_HR_NAME = "Priya Sharma"
DEFAULT_CREDIT_BALANCE = 450
DEFAULT_TOTAL_ENROLLED = 180

SAMPLE_EMPLOYEES = [
    # Page 1 (1 - 8)
    {
        "id": 1,
        "name": "Aarav Patel",
        "email": "aarav.p@acmetech.com",
        "department": "Engineering",
        "designation": "Senior Frontend Engineer",
        "joined_date": "15 Jan 2026",
        "credits_used": 1,
        "credits_quota": 2,
        "status": "Active",
        "daily_workout_mins": 45,
        "calories_burnt": 480,
        "last_consultation_date": "28 Sep 2026",
        "last_consultation_type": "Ergonomics & Desk Posture",
        "last_active": "Today, 10:30 AM"
    },
    {
        "id": 2,
        "name": "Sneha Reddy",
        "email": "sneha.r@acmetech.com",
        "department": "Product & Design",
        "designation": "Lead Product Designer",
        "joined_date": "03 Feb 2026",
        "credits_used": 2,
        "credits_quota": 2,
        "status": "Active",
        "daily_workout_mins": 35,
        "calories_burnt": 390,
        "last_consultation_date": "24 Sep 2026",
        "last_consultation_type": "Mental Wellbeing & Anxiety",
        "last_active": "Yesterday, 4:15 PM"
    },
    {
        "id": 3,
        "name": "Rohan Deshmukh",
        "email": "rohan.d@acmetech.com",
        "department": "Engineering",
        "designation": "Backend Architect",
        "joined_date": "10 Feb 2026",
        "credits_used": 0,
        "credits_quota": 2,
        "status": "Active",
        "daily_workout_mins": 25,
        "calories_burnt": 310,
        "last_consultation_date": "12 Sep 2026",
        "last_consultation_type": "Sleep Optimization",
        "last_active": "Today, 09:10 AM"
    },
    {
        "id": 4,
        "name": "Ananya Iyer",
        "email": "ananya.i@acmetech.com",
        "department": "Sales & Marketing",
        "designation": "Growth Marketing Manager",
        "joined_date": "18 Feb 2026",
        "credits_used": 1,
        "credits_quota": 2,
        "status": "Active",
        "daily_workout_mins": 40,
        "calories_burnt": 440,
        "last_consultation_date": "30 Sep 2026",
        "last_consultation_type": "Stress & Burnout Reset",
        "last_active": "Today, 11:20 AM"
    },
    {
        "id": 5,
        "name": "Vikram Malhotra",
        "email": "vikram.m@acmetech.com",
        "department": "Sales & Marketing",
        "designation": "Enterprise Account Executive",
        "joined_date": "01 Mar 2026",
        "credits_used": 2,
        "credits_quota": 2,
        "status": "Active",
        "daily_workout_mins": 50,
        "calories_burnt": 560,
        "last_consultation_date": "29 Sep 2026",
        "last_consultation_type": "Executive Performance Coaching",
        "last_active": "Yesterday, 6:40 PM"
    },
    {
        "id": 6,
        "name": "Divya Nambiar",
        "email": "divya.n@acmetech.com",
        "department": "Operations",
        "designation": "Support Team Lead",
        "joined_date": "12 Mar 2026",
        "credits_used": 0,
        "credits_quota": 2,
        "status": "Invited",
        "daily_workout_mins": 20,
        "calories_burnt": 260,
        "last_consultation_date": "None yet",
        "last_consultation_type": "Pending Onboarding",
        "last_active": "Pending Invite"
    },
    {
        "id": 7,
        "name": "Karan Singhania",
        "email": "karan.s@acmetech.com",
        "department": "Human Resources",
        "designation": "People Operations Specialist",
        "joined_date": "22 Mar 2026",
        "credits_used": 1,
        "credits_quota": 2,
        "status": "Active",
        "daily_workout_mins": 30,
        "calories_burnt": 350,
        "last_consultation_date": "19 Sep 2026",
        "last_consultation_type": "Mindfulness & Resilience",
        "last_active": "Today, 08:45 AM"
    },
    {
        "id": 8,
        "name": "Meera Joshi",
        "email": "meera.j@acmetech.com",
        "department": "Engineering",
        "designation": "DevOps Engineer",
        "joined_date": "05 Apr 2026",
        "credits_used": 0,
        "credits_quota": 2,
        "status": "Active",
        "daily_workout_mins": 35,
        "calories_burnt": 380,
        "last_consultation_date": "22 Sep 2026",
        "last_consultation_type": "Physical Ergonomics",
        "last_active": "25 Sep 2026"
    },

    # Page 2 (9 - 16)
    {
        "id": 9,
        "name": "Aditya Verma",
        "email": "aditya.v@acmetech.com",
        "department": "Engineering",
        "designation": "Staff Cloud Engineer",
        "joined_date": "12 Apr 2026",
        "credits_used": 2,
        "credits_quota": 2,
        "status": "Active",
        "daily_workout_mins": 40,
        "calories_burnt": 420,
        "last_consultation_date": "01 Oct 2026",
        "last_consultation_type": "Neck & Spine Alignment",
        "last_active": "Today, 10:05 AM"
    },
    {
        "id": 10,
        "name": "Pooja Hegde",
        "email": "pooja.h@acmetech.com",
        "department": "Product & Design",
        "designation": "UX Researcher",
        "joined_date": "19 Apr 2026",
        "credits_used": 1,
        "credits_quota": 2,
        "status": "Active",
        "daily_workout_mins": 30,
        "calories_burnt": 340,
        "last_consultation_date": "15 Sep 2026",
        "last_consultation_type": "Work-Life Balance",
        "last_active": "Yesterday, 3:30 PM"
    },
    {
        "id": 11,
        "name": "Siddharth Rao",
        "email": "siddharth.r@acmetech.com",
        "department": "Sales & Marketing",
        "designation": "Content Strategist",
        "joined_date": "02 May 2026",
        "credits_used": 0,
        "credits_quota": 2,
        "status": "Active",
        "daily_workout_mins": 55,
        "calories_burnt": 590,
        "last_consultation_date": "05 Sep 2026",
        "last_consultation_type": "Sleep Hygiene",
        "last_active": "Yesterday, 5:15 PM"
    },
    {
        "id": 12,
        "name": "Kavita Menon",
        "email": "kavita.m@acmetech.com",
        "department": "Operations",
        "designation": "Logistics & Supply Manager",
        "joined_date": "14 May 2026",
        "credits_used": 1,
        "credits_quota": 2,
        "status": "Active",
        "daily_workout_mins": 25,
        "calories_burnt": 290,
        "last_consultation_date": "27 Sep 2026",
        "last_consultation_type": "Stress Management",
        "last_active": "Today, 09:40 AM"
    },
    {
        "id": 13,
        "name": "Nikhil Agarwal",
        "email": "nikhil.a@acmetech.com",
        "department": "Engineering",
        "designation": "Security Specialist",
        "joined_date": "28 May 2026",
        "credits_used": 2,
        "credits_quota": 2,
        "status": "Active",
        "daily_workout_mins": 35,
        "calories_burnt": 400,
        "last_consultation_date": "20 Sep 2026",
        "last_consultation_type": "Burnout Prevention",
        "last_active": "28 Sep 2026"
    },
    {
        "id": 14,
        "name": "Tanvi Kapoor",
        "email": "tanvi.k@acmetech.com",
        "department": "Human Resources",
        "designation": "Talent Acquisition Partner",
        "joined_date": "05 Jun 2026",
        "credits_used": 0,
        "credits_quota": 2,
        "status": "Invited",
        "daily_workout_mins": 20,
        "calories_burnt": 240,
        "last_consultation_date": "None yet",
        "last_consultation_type": "Pending Onboarding",
        "last_active": "Pending Invite"
    },
    {
        "id": 15,
        "name": "Gaurav Bhatt",
        "email": "gaurav.b@acmetech.com",
        "department": "Sales & Marketing",
        "designation": "Regional Sales Director",
        "joined_date": "16 Jun 2026",
        "credits_used": 2,
        "credits_quota": 2,
        "status": "Active",
        "daily_workout_mins": 60,
        "calories_burnt": 620,
        "last_consultation_date": "02 Oct 2026",
        "last_consultation_type": "Executive Coaching",
        "last_active": "Today, 11:55 AM"
    },
    {
        "id": 16,
        "name": "Ishita Sen",
        "email": "ishita.s@acmetech.com",
        "department": "Product & Design",
        "designation": "Product Manager (Core App)",
        "joined_date": "25 Jun 2026",
        "credits_used": 1,
        "credits_quota": 2,
        "status": "Active",
        "daily_workout_mins": 40,
        "calories_burnt": 430,
        "last_consultation_date": "18 Sep 2026",
        "last_consultation_type": "Anxiety & Cognitive Stamina",
        "last_active": "Yesterday, 2:10 PM"
    },

    # Page 3 (17 - 24)
    {
        "id": 17,
        "name": "Deepak Chawla",
        "email": "deepak.c@acmetech.com",
        "department": "Engineering",
        "designation": "QA Automation Lead",
        "joined_date": "02 Jul 2026",
        "credits_used": 1,
        "credits_quota": 2,
        "status": "Active",
        "daily_workout_mins": 30,
        "calories_burnt": 350,
        "last_consultation_date": "25 Sep 2026",
        "last_consultation_type": "Eye Strain & Ergonomics",
        "last_active": "Today, 10:15 AM"
    },
    {
        "id": 18,
        "name": "Rhea Chakraborty",
        "email": "rhea.c@acmetech.com",
        "department": "Operations",
        "designation": "Compliance Associate",
        "joined_date": "11 Jul 2026",
        "credits_used": 0,
        "credits_quota": 2,
        "status": "Active",
        "daily_workout_mins": 35,
        "calories_burnt": 370,
        "last_consultation_date": "14 Sep 2026",
        "last_consultation_type": "Nutrition & Energy Focus",
        "last_active": "29 Sep 2026"
    },
    {
        "id": 19,
        "name": "Harsh Vardhan",
        "email": "harsh.v@acmetech.com",
        "department": "Engineering",
        "designation": "Data Platform Engineer",
        "joined_date": "20 Jul 2026",
        "credits_used": 2,
        "credits_quota": 2,
        "status": "Active",
        "daily_workout_mins": 45,
        "calories_burnt": 490,
        "last_consultation_date": "29 Sep 2026",
        "last_consultation_type": "Lower Back & Spine Health",
        "last_active": "Yesterday, 4:50 PM"
    },
    {
        "id": 20,
        "name": "Shweta Bansal",
        "email": "shweta.b@acmetech.com",
        "department": "Sales & Marketing",
        "designation": "Brand Partnerships Lead",
        "joined_date": "01 Aug 2026",
        "credits_used": 1,
        "credits_quota": 2,
        "status": "Active",
        "daily_workout_mins": 35,
        "calories_burnt": 380,
        "last_consultation_date": "21 Sep 2026",
        "last_consultation_type": "Mindful Leadership",
        "last_active": "Today, 08:20 AM"
    },
    {
        "id": 21,
        "name": "Manish Pandey",
        "email": "manish.p@acmetech.com",
        "department": "Operations",
        "designation": "IT Systems Admin",
        "joined_date": "15 Aug 2026",
        "credits_used": 0,
        "credits_quota": 2,
        "status": "Active",
        "daily_workout_mins": 25,
        "calories_burnt": 290,
        "last_consultation_date": "08 Sep 2026",
        "last_consultation_type": "Sleep Reset",
        "last_active": "Yesterday, 1:45 PM"
    },
    {
        "id": 22,
        "name": "Archana Saxena",
        "email": "archana.s@acmetech.com",
        "department": "Human Resources",
        "designation": "Employee Engagement Lead",
        "joined_date": "28 Aug 2026",
        "credits_used": 2,
        "credits_quota": 2,
        "status": "Active",
        "daily_workout_mins": 50,
        "calories_burnt": 510,
        "last_consultation_date": "30 Sep 2026",
        "last_consultation_type": "Psychological Safety Lab",
        "last_active": "Today, 11:10 AM"
    },
    {
        "id": 23,
        "name": "Rajesh Nair",
        "email": "rajesh.n@acmetech.com",
        "department": "Engineering",
        "designation": "Principal Mobile Engineer",
        "joined_date": "05 Sep 2026",
        "credits_used": 1,
        "credits_quota": 2,
        "status": "Active",
        "daily_workout_mins": 40,
        "calories_burnt": 440,
        "last_consultation_date": "26 Sep 2026",
        "last_consultation_type": "Ergonomics & Desk Mobility",
        "last_active": "Yesterday, 5:30 PM"
    },
    {
        "id": 24,
        "name": "Simran Kaur",
        "email": "simran.k@acmetech.com",
        "department": "Product & Design",
        "designation": "Design Systems Architect",
        "joined_date": "15 Sep 2026",
        "credits_used": 0,
        "credits_quota": 2,
        "status": "Invited",
        "daily_workout_mins": 30,
        "calories_burnt": 320,
        "last_consultation_date": "None yet",
        "last_consultation_type": "Pending Onboarding",
        "last_active": "Pending Invite"
    }
]

SAMPLE_INVOICES = [
    {
        "id": 1,
        "invoice_number": "INV-SS-2026-089",
        "date": "01 Sep 2026",
        "credits_amount": 200,
        "amount_inr": "₹99,800",
        "gst_amount": "₹17,964",
        "status": "Paid",
        "receipt_url": "#"
    },
    {
        "id": 2,
        "invoice_number": "INV-SS-2026-064",
        "date": "01 Aug 2026",
        "credits_amount": 200,
        "amount_inr": "₹99,800",
        "gst_amount": "₹17,964",
        "status": "Paid",
        "receipt_url": "#"
    },
    {
        "id": 3,
        "invoice_number": "INV-SS-2026-041",
        "date": "01 Jul 2026",
        "credits_amount": 150,
        "amount_inr": "₹74,850",
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
        "time": "3:30 PM - 4:30 PM (IST)",
        "month": "OCT",
        "day": "12",
        "date_str": "Thursday, Oct 12 • 3:30 PM - 4:30 PM (IST)",
        "attendees_count": 64,
        "target_dept": "Company-wide Live",
        "invite_link": "https://solacesquad.com/meet/mindfulness-oct12"
    },
    {
        "id": 2,
        "title": "Ergonomics, Posture & RSI Prevention for Tech Teams",
        "speaker": "Rahul Menon (MPT Ergonomics Specialist)",
        "time": "4:00 PM - 5:00 PM (IST)",
        "month": "OCT",
        "day": "25",
        "date_str": "Wednesday, Oct 25 • 4:00 PM - 5:00 PM (IST)",
        "attendees_count": 41,
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
        
        ctx.update({
            "metrics": {
                "org_health_score": 82,
                "active_enrolled": 142,
                "total_headcount": DEFAULT_TOTAL_ENROLLED,
                "consultations_count": 164,
                "credit_balance": DEFAULT_CREDIT_BALANCE,
            },
            "recent_employees": SAMPLE_EMPLOYEES[:5],
            "upcoming_events": SAMPLE_SCHEDULED_WORKSHOPS,
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
        
        filtered = list(SAMPLE_EMPLOYEES)
        if dept and dept.lower() != "all":
            filtered = [e for e in filtered if dept.lower() in e["department"].lower()]
        if q:
            query = q.strip().lower()
            filtered = [
                e for e in filtered 
                if query in e["name"].lower() or query in e["email"].lower() or query in e.get("designation", "").lower()
            ]

        departments = ["All Departments", "Engineering", "Product & Design", "Sales & Marketing", "Human Resources", "Operations"]
        
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
        designation: Optional[str] = Form(None),
        role: Optional[str] = Form(None),
        credits_quota: Optional[int] = Form(2),
        db: Session = Depends(get_db)
    ):
        emp_role = designation or role or "Team Member"
        new_emp = {
            "id": len(SAMPLE_EMPLOYEES) + 1,
            "name": name.strip(),
            "email": email.strip().lower(),
            "department": department,
            "designation": emp_role.strip(),
            "joined_date": date.today().strftime("%d %b %Y"),
            "credits_used": 0,
            "credits_quota": credits_quota or 2,
            "status": "Invited",
            "daily_workout_mins": 30,
            "calories_burnt": 350,
            "last_consultation_date": "None yet",
            "last_consultation_type": "Pending Onboarding",
            "last_active": "Pending Onboarding"
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
                emp_role = row.get("designation") or row.get("role") or row.get("Role") or row.get("Title") or "Team Member"
                
                if emp_name and emp_email:
                    SAMPLE_EMPLOYEES.insert(0, {
                        "id": len(SAMPLE_EMPLOYEES) + 1,
                        "name": emp_name.strip(),
                        "email": emp_email.strip().lower(),
                        "department": emp_dept.strip(),
                        "designation": emp_role.strip(),
                        "joined_date": date.today().strftime("%d %b %Y"),
                        "credits_used": 0,
                        "credits_quota": 2,
                        "status": "Invited",
                        "daily_workout_mins": 30,
                        "calories_burnt": 350,
                        "last_consultation_date": "None yet",
                        "last_consultation_type": "Pending Onboarding",
                        "last_active": "Pending Onboarding"
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
            "departments": [
                {
                    "name": "Engineering & Tech",
                    "badge_color": "bg-indigo-500",
                    "headcount": 64,
                    "participation": 82,
                    "avg_score": 78,
                    "stress_status": "Moderate Load",
                    "stress_badge": "bg-amber-50 text-amber-700 border-amber-200",
                    "top_pillar": "Mental & Ergonomics"
                },
                {
                    "name": "Sales & Enterprise GTM",
                    "badge_color": "bg-emerald-500",
                    "headcount": 42,
                    "participation": 89,
                    "avg_score": 85,
                    "stress_status": "Optimal Zone",
                    "stress_badge": "bg-emerald-50 text-emerald-700 border-emerald-200",
                    "top_pillar": "Work-Life Balance"
                },
                {
                    "name": "Product & User Experience",
                    "badge_color": "bg-purple-500",
                    "headcount": 28,
                    "participation": 86,
                    "avg_score": 81,
                    "stress_status": "Optimal Zone",
                    "stress_badge": "bg-emerald-50 text-emerald-700 border-emerald-200",
                    "top_pillar": "Stress Resilience"
                },
                {
                    "name": "Operations & Customer Support",
                    "badge_color": "bg-rose-500",
                    "headcount": 32,
                    "participation": 74,
                    "avg_score": 73,
                    "stress_status": "Attention Needed",
                    "stress_badge": "bg-amber-50 text-amber-700 border-amber-200",
                    "top_pillar": "Sleep & Ergonomics"
                },
                {
                    "name": "Human Resources & Talent",
                    "badge_color": "bg-teal-500",
                    "headcount": 14,
                    "participation": 94,
                    "avg_score": 91,
                    "stress_status": "Thriving Zone",
                    "stress_badge": "bg-emerald-50 text-emerald-700 border-emerald-200",
                    "top_pillar": "Mindfulness & Resilience"
                }
            ],
            "quarterly_trend": [
                {"quarter": "Q1 2026", "score": 72, "participation": 65},
                {"quarter": "Q2 2026", "score": 76, "participation": 74},
                {"quarter": "Q3 2026", "score": 79, "participation": 81},
                {"quarter": "Q4 2026", "score": 82, "participation": 84}
            ],
            "vitals_summary": {
                "resting_hr": "71 bpm",
                "spo2": "98.4%",
                "stress_index": "22 (Low)",
                "active_minutes": "38m / day"
            }
        })
        
        return templates.TemplateResponse("pages/hr_analytics.html", ctx)

    # ── 4. Corporate Credits & Billing Management ─────────────────────────────
    @app.get("/hr/credits", response_class=HTMLResponse)
    async def hr_credits(request: Request, db: Session = Depends(get_db)):
        ctx = _get_hr_context(request, db)
        
        ctx.update({
            "wallet": {
                "available_credits": DEFAULT_CREDIT_BALANCE,
                "total_purchased": 1000,
                "consumed": 550,
                "default_monthly_quota": "₹2,000 / mo",
                "renewal_date": "01 Nov 2026",
                "plan_tier": "Enterprise Scaled Tier"
            },
            "invoices": SAMPLE_INVOICES,
        })
        
        return templates.TemplateResponse("pages/hr_credits.html", ctx)

    # ── 4.1 Credit Top-Up POST Handler ────────────────────────────────────────
    @app.post("/hr/credits/topup")
    async def hr_credits_topup(
        request: Request,
        credit_pack: int = Form(...),
        payment_method: Optional[str] = Form("corporate_invoice"),
        db: Session = Depends(get_db)
    ):
        amount_num = credit_pack * 499
        gst_num = int(amount_num * 0.18)
        new_inv = {
            "id": len(SAMPLE_INVOICES) + 1,
            "invoice_number": f"INV-SS-2026-0{len(SAMPLE_INVOICES) + 90}",
            "date": date.today().strftime("%d %b %Y"),
            "credits_amount": credit_pack,
            "amount_inr": f"₹{amount_num:,}",
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
            "time": preferred_time or "TBD",
            "month": "NOV",
            "day": "15",
            "attendees_count": 0,
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
            "thryveq_score": 82,
            "participation_pct": 84,
            "happiness_index": 84,
            "dpdp_compliant": True
        })
