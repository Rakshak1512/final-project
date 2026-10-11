"""
Global Search Route for EventSphere
Provides fast, role-aware, case-insensitive query responses across:
- Direct Navigation Links
- Campus Events
- Student Certificates
- Event Registrations & Tickets
- Event Results & Award Standings
- Assigned Work & Faculty Tasks
- Faculty Directory & Institutional Approvals
- System Notifications
"""
import logging
from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, Query

from app.dependencies import get_current_approved_user
from app.models.user import User
from app.db import firestore_service as db_service

logger = logging.getLogger("app.search")

router = APIRouter(prefix="/api/search", tags=["Search"])


class SearchResultItem(BaseModel):
    id: str
    title: str
    category: str
    subtitle: Optional[str] = None
    link: str
    badge: Optional[str] = None


class GlobalSearchResponse(BaseModel):
    query: str
    total: int
    results: List[SearchResultItem]


@router.get("/global", response_model=GlobalSearchResponse)
def global_search(
    q: Optional[str] = Query(default="", max_length=100, description="Search query string"),
    current_user: User = Depends(get_current_approved_user),
):
    raw_query = (q or "").strip()
    query_str = raw_query.lower()
    if not query_str:
        return GlobalSearchResponse(query="", total=0, results=[])

    query_terms = [t for t in query_str.split() if t]

    def matches(*fields) -> bool:
        combined = " ".join(str(f or "") for f in fields).lower()
        if query_str in combined:
            return True
        return all(term in combined for term in query_terms)

    role = (current_user.role or "student").lower()
    base_path = f"/{role}" if role in ("student", "faculty", "admin", "volunteer") else "/student"
    results: List[SearchResultItem] = []

    try:
        # 1. Navigation & Quick Links Matching (Filtered by Role)
        nav_items = []
        if role == "student":
            nav_items = [
                ("events", "Browse Events", "Explore upcoming campus fests, workshops, and hackathons", f"{base_path}/events"),
                ("registrations", "My Registrations", "Track ticket QR passes and registration approvals", f"{base_path}/my-registrations"),
                ("certificates", "My Certificates", "View and download verified digital certificates", f"{base_path}/certificates"),
                ("notifications", "Notifications", "Live system announcements and alerts", f"{base_path}/notifications"),
                ("profile", "Profile Settings", "Manage account information and security", f"{base_path}/profile"),
                ("settings", "Account Settings", "Customize your preferences and account", f"{base_path}/settings"),
            ]
        elif role == "faculty":
            nav_items = [
                ("dashboard", "Faculty Dashboard", "Overview of department events and registrations", f"{base_path}/dashboard"),
                ("events", "Manage Events", "Create, edit, and organize campus events", f"{base_path}/events"),
                ("student-approvals", "Student Approvals", "Review and verify student registrations", f"{base_path}/student-approvals"),
                ("volunteer-approvals", "Volunteer Approvals", "Review and verify student volunteers", f"{base_path}/volunteer-approvals"),
                ("registrations", "Event Registrations", "Track attendee lists and ticket passes", f"{base_path}/registrations"),
                ("reports", "Registration Reports", "Review student rosters and download PDF reports", f"{base_path}/registration-reports"),
                ("results", "Results & Winners", "Declare winners and manage standings", f"{base_path}/results"),
                ("certificates", "Manage Certificates", "Generate and upload event certificates", f"{base_path}/certificates"),
                ("tasks", "Assigned Work", "Review administrative directives and responsibilities", f"{base_path}/tasks"),
                ("notifications", "Notifications", "Live alerts and notifications", f"{base_path}/notifications"),
                ("profile", "Profile Settings", "Manage account profile", f"{base_path}/profile"),
            ]
        elif role == "admin":
            nav_items = [
                ("dashboard", "Admin Dashboard", "System overview, active events, and counts", f"{base_path}/dashboard"),
                ("faculty-approvals", "Faculty Approvals", "Verify new faculty coordinator registrations", f"{base_path}/faculty-approvals"),
                ("faculty", "Faculty Directory", "All department faculty coordinators and tasks", f"{base_path}/faculty"),
                ("assignments", "Work Assignments", "Assign and monitor administrative directives", f"{base_path}/assignments"),
                ("events", "Manage Events", "Campus-wide event catalog and approvals", f"{base_path}/events"),
                ("reports", "Master Reports", "Generate institutional PDF analytics and reports", f"{base_path}/reports"),
                ("notifications", "Notifications", "Administrative system alerts", f"{base_path}/notifications"),
                ("profile", "Profile Settings", "Manage administrator profile", f"{base_path}/profile"),
            ]
        elif role == "volunteer":
            nav_items = [
                ("dashboard", "Volunteer Scanner", "Scan attendee QR tickets and mark check-in", f"{base_path}/dashboard"),
                ("events", "Assigned Events", "View active events and schedules", f"{base_path}/events"),
                ("notifications", "Notifications", "System announcements and updates", f"{base_path}/notifications"),
                ("profile", "Profile Settings", "Manage volunteer profile", f"{base_path}/profile"),
            ]

        for key, title, desc, link in nav_items:
            if matches(key, title, desc):
                results.append(SearchResultItem(
                    id=f"nav-{key}",
                    title=title,
                    category="Navigation",
                    subtitle=desc,
                    link=link,
                    badge="Page",
                ))

        # 2. Campus Events Search (Visible across all roles)
        all_events = []
        try:
            all_events = db_service.get_all_events()
            for ev in all_events:
                if matches(ev.title, ev.category, ev.venue, ev.description, str(ev.id)):
                    results.append(SearchResultItem(
                        id=f"event-{ev.id}",
                        title=ev.title,
                        category="Events",
                        subtitle=f"{ev.category} · {ev.venue or 'Campus'} · {ev.event_date} ({ev.available_seats}/{ev.total_seats} spots left)",
                        link=f"{base_path}/events/{ev.id}",
                        badge=ev.category,
                    ))
        except Exception as ev_err:
            logger.debug(f"Search events query error: {ev_err}")

        # 3. Certificates Search (Role-based access enforced)
        try:
            if role == "student":
                student_certs = db_service.get_certificates_by_registration_number(current_user.registration_number or "")
                for c in student_certs:
                    c_id_str = f"ESP-{c.id:06d}" if isinstance(c.id, int) else f"ESP-{c.id}"
                    issued_date = c.uploaded_at.strftime("%Y-%m-%d") if getattr(c, "uploaded_at", None) and hasattr(c.uploaded_at, "strftime") else "Recent"
                    if matches(c.title, c_id_str, str(c.id), "certificate"):
                        results.append(SearchResultItem(
                            id=f"cert-{c.id}",
                            title=c.title,
                            category="Certificates",
                            subtitle=f"Certificate ID: {c_id_str} · Issued: {issued_date}",
                            link=f"{base_path}/certificates",
                            badge="Certificate",
                        ))
            elif role in ("faculty", "admin"):
                all_uploaded = db_service.get_certificates_by_faculty(current_user.id) if role == "faculty" else []
                for c in all_uploaded:
                    c_id_str = f"ESP-{c.id:06d}" if isinstance(c.id, int) else f"ESP-{c.id}"
                    if matches(c.title, c.registration_number, c.student_name, c_id_str, "certificate"):
                        results.append(SearchResultItem(
                            id=f"cert-{c.id}",
                            title=c.title,
                            category="Certificates",
                            subtitle=f"Student: {c.student_name} ({c.registration_number}) · {c_id_str}",
                            link=f"{base_path}/certificates",
                            badge="Certificate",
                        ))
        except Exception as cert_err:
            logger.debug(f"Search certificates query error: {cert_err}")

        # 4. Registrations & Tickets Search (Role-based access enforced)
        try:
            if role == "student":
                my_regs = db_service.get_my_registrations(current_user.id)
                for r in my_regs:
                    r_title = r.event.title if r.event else f"Event #{r.event_id}"
                    r_code = r.ticket_code or ""
                    r_status = str(r.status.value if hasattr(r.status, "value") else r.status)
                    if matches(r_title, r_code, r_status, "registration", "ticket"):
                        results.append(SearchResultItem(
                            id=f"reg-{r.id}",
                            title=r_title,
                            category="My Registrations",
                            subtitle=f"Ticket: #{r_code} · Status: {r_status.upper()}",
                            link=f"{base_path}/my-registrations",
                            badge=r_status.capitalize(),
                        ))
            elif role in ("faculty", "admin"):
                target_events = db_service.get_events_by_organizer(current_user.id) if role == "faculty" else all_events[:10]
                for ev in target_events[:8]:
                    ev_regs = db_service.get_event_registrations(ev.id)
                    for r in ev_regs:
                        s_name = r.student.name if r.student else (r.student_name or "")
                        s_reg = r.student.registration_number if r.student else (r.registration_number or "")
                        s_dept = r.student.department if r.student and r.student.department else "General"
                        t_code = r.ticket_code or ""
                        r_st = str(r.status.value if hasattr(r.status, "value") else r.status)
                        if matches(s_name, s_reg, s_dept, t_code, r_st, ev.title):
                            results.append(SearchResultItem(
                                id=f"reg-{r.id}",
                                title=f"{s_name} ({s_reg})",
                                category="Student Registrations",
                                subtitle=f"Event: {ev.title} · Ticket: #{t_code} · {r_st.upper()}",
                                link=f"{base_path}/registrations",
                                badge=r_st.capitalize(),
                            ))
        except Exception as reg_err:
            logger.debug(f"Search registrations query error: {reg_err}")

        # 5. Results & Award Standings Search
        try:
            if role in ("faculty", "admin"):
                for ev in all_events[:8]:
                    results_list = db_service.get_event_results(ev.id)
                    for res in results_list:
                        if matches(res.student_name, res.registration_number, res.position, res.event_title or ev.title, "winner", "result"):
                            results.append(SearchResultItem(
                                id=f"result-{res.id}",
                                title=f"{res.student_name} — {res.position}",
                                category="Results & Winners",
                                subtitle=f"Event: {res.event_title or ev.title} · Reg No: {res.registration_number}",
                                link=f"{base_path}/results",
                                badge=res.position,
                            ))
        except Exception as res_err:
            logger.debug(f"Search results query error: {res_err}")

        # 6. Assigned Work & Faculty Tasks (Faculty & Admin only)
        try:
            if role == "faculty":
                my_tasks = db_service.get_faculty_assignments(current_user.id)
                for t in my_tasks:
                    if matches(t.title, t.description, t.priority, t.status, "task", "work"):
                        results.append(SearchResultItem(
                            id=f"task-{t.id}",
                            title=t.title,
                            category="Assigned Work",
                            subtitle=f"Priority: {t.priority.upper()} · Status: {t.status} · Due: {t.deadline or 'N/A'}",
                            link=f"{base_path}/tasks",
                            badge=t.priority.capitalize(),
                        ))

                # Pending Student Approvals for Faculty
                pending_stu = db_service.get_pending_students()
                for ps in pending_stu:
                    if matches(ps.name, ps.registration_number, ps.department, "pending", "approval"):
                        results.append(SearchResultItem(
                            id=f"pending-stu-{ps.id}",
                            title=f"Pending Student: {ps.name}",
                            category="Student Approvals",
                            subtitle=f"Reg: {ps.registration_number or 'N/A'} · {ps.department or 'General'} · Awaiting Faculty Approval",
                            link=f"{base_path}/student-approvals",
                            badge="Pending",
                        ))
            elif role == "admin":
                all_tasks = db_service.get_all_assignments()
                for t in all_tasks:
                    if matches(t.title, t.faculty_name, t.priority, t.status, "task", "assignment"):
                        results.append(SearchResultItem(
                            id=f"task-{t.id}",
                            title=t.title,
                            category="Assigned Work",
                            subtitle=f"Assigned to: Prof. {t.faculty_name} · Priority: {t.priority.upper()}",
                            link=f"{base_path}/assignments",
                            badge=t.status.capitalize(),
                        ))

                # Faculty Directory Search
                fac_list = db_service.get_all_faculty_with_stats()
                for f in fac_list:
                    if matches(f.get("name"), f.get("department"), f.get("email"), "faculty"):
                        results.append(SearchResultItem(
                            id=f"fac-{f.get('id')}",
                            title=f.get("name"),
                            category="Faculty Directory",
                            subtitle=f"{f.get('department')} · {f.get('email')} · {f.get('assigned_tasks_count', 0)} tasks",
                            link=f"{base_path}/faculty",
                            badge=f.get("department") or "Faculty",
                        ))

                # Pending Faculty Approvals
                pending_fac = db_service.get_pending_faculty()
                for pf in pending_fac:
                    if matches(pf.name, pf.email, pf.department, "pending", "approval"):
                        results.append(SearchResultItem(
                            id=f"pending-fac-{pf.id}",
                            title=f"Pending Faculty: {pf.name}",
                            category="Faculty Approvals",
                            subtitle=f"{pf.department or 'Faculty'} · {pf.email} · Awaiting Admin Verification",
                            link=f"{base_path}/faculty-approvals",
                            badge="Pending Approval",
                        ))
        except Exception as task_err:
            logger.debug(f"Search tasks query error: {task_err}")

        # 7. Notifications Search (User's own notifications only)
        try:
            my_notifs = db_service.list_notifications(user_id=current_user.id, limit=20)
            for n in my_notifs:
                if matches(n.title, n.message, "notification", "alert"):
                    results.append(SearchResultItem(
                        id=f"notif-{n.id}",
                        title=n.title,
                        category="Notifications",
                        subtitle=n.message[:90] + ("..." if len(n.message) > 90 else ""),
                        link=f"{base_path}/notifications",
                        badge="Alert",
                    ))
        except Exception as notif_err:
            logger.debug(f"Search notifs query error: {notif_err}")

        # Deduplicate and limit to top 15 most relevant results
        seen_keys = set()
        deduped = []
        for r in results:
            key = (r.category, r.title, r.link)
            if key not in seen_keys:
                seen_keys.add(key)
                deduped.append(r)

        return GlobalSearchResponse(query=raw_query, total=len(deduped), results=deduped[:15])

    except Exception as e:
        logger.exception(f"Global search error for query '{raw_query}': {e}")
        return GlobalSearchResponse(query=raw_query, total=0, results=[])
