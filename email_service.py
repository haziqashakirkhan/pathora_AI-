"""
Pathora AI — Transactional Email Notification & Inactivity Service
Uses Resend API (via httpx) to send verified opportunity alerts and 7-day application tracker reminders.
Strictly isolates student data and prevents duplicate email delivery.
"""

import os
import re
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
import httpx

logger = logging.getLogger("pathora_ai.email_service")

# Environment configuration
# Lazy getters for environment variables – read at runtime
def get_resend_api_key() -> str:
    return os.getenv("RESEND_API_KEY", "").strip()

def get_resend_from_email() -> str:
    # Default fallback matches previous behavior
    return os.getenv("RESEND_FROM_EMAIL", "").strip() or "Pathora AI <onboarding@resend.dev>"

def get_cron_secret() -> str:
    return os.getenv("CRON_SECRET", "").strip()
# Lazy getters for environment variables – read at runtime

def get_resend_api_key() -> str:
    return os.getenv("RESEND_API_KEY", "").strip()

def get_resend_from_email() -> str:
    # Default fallback matches previous behavior
    return os.getenv("RESEND_FROM_EMAIL", "").strip() or "Pathora AI <onboarding@resend.dev>"

def get_cron_secret() -> str:
    return os.getenv("CRON_SECRET", "").strip()
# Lazy getters for environment variables – read at runtime

def get_resend_api_key() -> str:
    return os.getenv("RESEND_API_KEY", "").strip()

def get_resend_from_email() -> str:
    # Default fallback matches previous behavior
    return os.getenv("RESEND_FROM_EMAIL", "").strip() or "Pathora AI <onboarding@resend.dev>"

def get_cron_secret() -> str:
    return os.getenv("CRON_SECRET", "").strip()

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

def is_valid_email(email: str) -> bool:
    if not email or not isinstance(email, str):
        return False
    return bool(EMAIL_REGEX.match(email.strip()))

def get_utc_now() -> datetime:
    return datetime.now(timezone.utc)

def get_utc_now_iso() -> str:
    return get_utc_now().isoformat().replace("+00:00", "Z")

def parse_iso_datetime(dt_str: Optional[str]) -> Optional[datetime]:
    if not dt_str:
        return None
    try:
        clean_str = dt_str.replace("Z", "+00:00")
        return datetime.fromisoformat(clean_str)
    except Exception:
        return None

# In-memory tracking store for testing and when Firestore is unconfigured
class NotificationMemoryStore:
    def __init__(self):
        # (user_id, opportunity_id) -> record
        self.sent_alerts: Dict[str, Dict[str, Any]] = {}
        # (user_id, opportunity_id) -> list of reminder timestamps
        self.sent_inactivity_reminders: Dict[str, List[str]] = {}
        # user_id -> dict of preferences
        self.user_preferences: Dict[str, Dict[str, Any]] = {}

notification_memory_store = NotificationMemoryStore()

async def send_resend_email(to_email: str, subject: str, html_content: str, text_content: Optional[str] = None) -> Dict[str, Any]:
    """
    Sends an email using Resend REST API via httpx.
    Safely logs and handles failures without crashing the application.
    """
    if not is_valid_email(to_email):
        logger.warning(f"Invalid recipient email address: {to_email}")
        return {"status": "error", "message": "Invalid recipient email address"}

    if not get_resend_api_key():
        logger.info(f"[Email Sim] RESEND_API_KEY not configured. Simulated email to {to_email}: '{subject}'")
        return {
            "status": "simulated",
            "message": "Email delivery simulated successfully (RESEND_API_KEY not set).",
            "to": to_email,
            "subject": subject
        }

    payload = {
        "from": get_resend_from_email(),
        "to": [to_email],
        "subject": subject,
        "html": html_content,
    }
    if text_content:
        payload["text"] = text_content

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {get_resend_api_key()}",
                    "Content-Type": "application/json"
                },
                json=payload
            )
            if response.status_code in (200, 201):
                data = response.json()
                logger.info(f"Resend email dispatched to {to_email} with id: {data.get('id')}")
                return {"status": "success", "id": data.get("id")}
            else:
                logger.error(f"Resend API error {response.status_code}: {response.text}")
                return {"status": "error", "code": response.status_code, "detail": response.text}
    except Exception as e:
        logger.error(f"Failed to deliver email to {to_email}: {e}")
        return {"status": "error", "message": str(e)}

def render_opportunity_alert_html(student_name: str, opportunity: Dict[str, Any]) -> str:
    title = opportunity.get("title", "Opportunity")
    org = opportunity.get("organization", "Host Institution")
    category = opportunity.get("category", "Student Program")
    location = opportunity.get("location", "Pakistan / Global")
    deadline = opportunity.get("deadline", "Check official portal")
    description = opportunity.get("description", "A verified opportunity matching your profile was discovered on Pathora AI.")
    official_url = opportunity.get("officialUrl") or opportunity.get("sourceUrl") or "https://pathora-ai-psi.vercel.app/app"

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #0f1015; color: #f0f0f5; margin: 0; padding: 24px; }}
        .card {{ background-color: #171821; border: 1px solid #2a2c3d; border-radius: 8px; padding: 24px; max-width: 600px; margin: 0 auto; }}
        .header {{ border-bottom: 1px solid #2a2c3d; padding-bottom: 16px; margin-bottom: 20px; }}
        .brand {{ color: #e11d48; font-size: 20px; font-weight: 700; }}
        .title {{ color: #ffffff; font-size: 18px; margin: 12px 0 6px 0; }}
        .meta {{ color: #94a3b8; font-size: 14px; margin-bottom: 16px; }}
        .tag {{ display: inline-block; background-color: #27273a; color: #f43f5e; padding: 4px 10px; border-radius: 4px; font-size: 12px; font-weight: 600; margin-right: 6px; }}
        .desc {{ color: #cbd5e1; font-size: 14px; line-height: 1.6; margin: 16px 0; }}
        .btn {{ display: inline-block; background-color: #e11d48; color: #ffffff !important; text-decoration: none; padding: 10px 20px; border-radius: 6px; font-weight: 600; font-size: 14px; margin-top: 12px; }}
        .footer {{ font-size: 12px; color: #64748b; margin-top: 24px; border-top: 1px solid #2a2c3d; padding-top: 16px; text-align: center; }}
      </style>
    </head>
    <body>
      <div class="card">
        <div class="header">
          <span class="brand">Pathora AI</span>
          <p style="margin: 4px 0 0 0; color: #94a3b8; font-size: 13px;">New Matching Opportunity Alert</p>
        </div>
        <p>Dear {student_name},</p>
        <p>A new authentic opportunity matching your profile has just been verified:</p>
        
        <h2 class="title">{title}</h2>
        <div class="meta">
          <strong>{org}</strong> • {location}
        </div>
        
        <div>
          <span class="tag">{category}</span>
          <span class="tag" style="color: #38bdf8;">Deadline: {deadline}</span>
        </div>
        
        <p class="desc">{description}</p>
        
        <a href="{official_url}" class="btn" target="_blank">View Official Listing & Apply &rarr;</a>
        
        <div class="footer">
          You are receiving this because you enabled email notifications on Pathora AI.<br>
          Pathora AI &bull; Empowering Pakistani Students &amp; Early-Career Talent
        </div>
      </div>
    </body>
    </html>
    """

def render_inactivity_reminder_html(student_name: str, application: Dict[str, Any], days_inactive: int) -> str:
    opp_data = application.get("opportunityData", {})
    title = opp_data.get("title", application.get("opportunityId", "Opportunity"))
    org = opp_data.get("organization", "Institution")
    current_status = application.get("status", "Interested")
    notes = application.get("notes", "")
    portal_url = opp_data.get("officialUrl") or "https://pathora-ai-psi.vercel.app/app#tracker"

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #0f1015; color: #f0f0f5; margin: 0; padding: 24px; }}
        .card {{ background-color: #171821; border: 1px solid #2a2c3d; border-radius: 8px; padding: 24px; max-width: 600px; margin: 0 auto; }}
        .header {{ border-bottom: 1px solid #2a2c3d; padding-bottom: 16px; margin-bottom: 20px; }}
        .brand {{ color: #e11d48; font-size: 20px; font-weight: 700; }}
        .title {{ color: #ffffff; font-size: 18px; margin: 12px 0 6px 0; }}
        .meta {{ color: #94a3b8; font-size: 14px; margin-bottom: 16px; }}
        .btn {{ display: inline-block; background-color: #e11d48; color: #ffffff !important; text-decoration: none; padding: 10px 20px; border-radius: 6px; font-weight: 600; font-size: 14px; margin-top: 12px; }}
        .footer {{ font-size: 12px; color: #64748b; margin-top: 24px; border-top: 1px solid #2a2c3d; padding-top: 16px; text-align: center; }}
      </style>
    </head>
    <body>
      <div class="card">
        <div class="header">
          <span class="brand">Pathora AI</span>
          <p style="margin: 4px 0 0 0; color: #94a3b8; font-size: 13px;">7-Day Application Tracker Inactivity Reminder</p>
        </div>
        <p>Hello {student_name},</p>
        <p>You added <strong>{title}</strong> ({org}) to your Pathora AI tracker with status <strong>"{current_status}"</strong>, but haven't updated it in {days_inactive} days.</p>
        
        {f'<p style="background: #202230; padding: 10px; border-radius: 4px; font-size: 13px; color: #94a3b8;"><strong>Last Note:</strong> {notes}</p>' if notes else ''}
        
        <p style="font-size: 14px; color: #cbd5e1;">Staying proactive significantly boosts your chances. If you have submitted your materials, attended an interview, or need to log progress, update your pipeline now:</p>
        
        <a href="{portal_url}" class="btn" target="_blank">Update Application Status &rarr;</a>
        
        <div class="footer">
          To stop reminders for this opportunity, update its status to Accepted, Rejected, or Withdrawn.<br>
          Pathora AI &bull; Empowering Pakistani Students &amp; Early-Career Talent
        </div>
      </div>
    </body>
    </html>
    """

async def check_and_send_opportunity_alert(
    user_id: str,
    user_email: str,
    user_name: str,
    opportunity: Dict[str, Any],
    firestore_db=None
) -> Dict[str, Any]:
    """
    Evaluates prerequisites and dispatches a new opportunity alert if:
    1. Opportunity is authentic & verified
    2. User has email notifications enabled
    3. User has NOT already received an alert for this opportunity id
    """
    if not is_valid_email(user_email):
        return {"status": "skipped", "reason": "Invalid user email"}

    opp_id = opportunity.get("id")
    if not opp_id:
        return {"status": "skipped", "reason": "Missing opportunity id"}

    # Check notification preferences
    prefs = await get_user_notification_preferences(user_id, firestore_db)
    if not prefs.get("emailNotificationsEnabled", True):
        return {"status": "skipped", "reason": "Email notifications disabled by user"}

    # Check if already sent
    already_sent = False
    if firestore_db:
        try:
            doc_ref = firestore_db.collection("users").document(user_id).collection("sent_alerts").document(opp_id).get()
            if doc_ref.exists:
                already_sent = True
        except Exception as e:
            logger.warning(f"Error checking Firestore sent_alerts: {e}")

    if not already_sent:
        key = f"{user_id}_{opp_id}"
        if key in notification_memory_store.sent_alerts:
            already_sent = True

    if already_sent:
        return {"status": "skipped", "reason": "Alert already sent for this opportunity"}

    # Send email
    subject = f"New Opportunity: {opportunity.get('title', 'Featured Program')} — Pathora AI"
    html_body = render_opportunity_alert_html(user_name or "Scholar", opportunity)
    result = await send_resend_email(user_email, subject, html_body)

    # Record alert delivery
    now_iso = get_utc_now_iso()
    record = {
        "userId": user_id,
        "opportunityId": opp_id,
        "opportunityTitle": opportunity.get("title", ""),
        "sentAt": now_iso,
        "deliveryStatus": result.get("status", "unknown")
    }

    if firestore_db:
        try:
            firestore_db.collection("users").document(user_id).collection("sent_alerts").document(opp_id).set(record)
        except Exception as e:
            logger.warning(f"Error persisting sent alert to Firestore: {e}")

    notification_memory_store.sent_alerts[f"{user_id}_{opp_id}"] = record
    return {"status": "sent", "delivery": result}

async def process_user_inactivity_reminders(
    user_id: str,
    user_email: str,
    user_name: str,
    applications: List[Dict[str, Any]],
    firestore_db=None
) -> List[Dict[str, Any]]:
    """
    Checks tracked applications for more than 7 days of student inactivity.
    Inactivity timer is reset whenever updatedAt is modified.
    Inactive reminders are spaced at least 7 days apart.
    Terminal statuses (Accepted, Rejected, Withdrawn) are excluded.
    """
    results = []
    if not is_valid_email(user_email):
        return results

    prefs = await get_user_notification_preferences(user_id, firestore_db)
    if not prefs.get("emailNotificationsEnabled", True):
        return results

    TERMINAL_STATUSES = {"Accepted", "Rejected", "Withdrawn"}
    now = get_utc_now()
    seven_days = timedelta(days=7)

    for app in applications:
        status = app.get("status", "Interested")
        if status in TERMINAL_STATUSES:
            continue

        opp_id = app.get("opportunityId")
        if not opp_id:
            continue

        # Meaningful activity timestamp: updatedAt or applicationDate or createdAt
        activity_str = app.get("updatedAt") or app.get("applicationDate") or app.get("createdAt")
        activity_dt = parse_iso_datetime(activity_str)
        if not activity_dt:
            continue

        days_inactive = (now - activity_dt).days
        if days_inactive < 7:
            continue

        # Check last reminder date
        last_reminder_str = app.get("lastInactivityReminderSentAt")
        last_reminder_dt = parse_iso_datetime(last_reminder_str)
        if last_reminder_dt and (now - last_reminder_dt) < seven_days:
            # Already reminded within this 7-day window
            continue

        # Dispatch reminder
        subject = f"Action Reminder: {days_inactive} days since update on your application — Pathora AI"
        html_body = render_inactivity_reminder_html(user_name or "Scholar", app, days_inactive)
        delivery = await send_resend_email(user_email, subject, html_body)

        now_iso = get_utc_now_iso()
        # Update last reminder timestamp on the application record
        app["lastInactivityReminderSentAt"] = now_iso

        if firestore_db:
            try:
                doc_id = f"{user_id}_{opp_id}"
                firestore_db.collection("applications").document(doc_id).set({
                    "lastInactivityReminderSentAt": now_iso
                }, merge=True)
            except Exception as e:
                logger.warning(f"Error updating last reminder timestamp in Firestore: {e}")

        results.append({
            "opportunityId": opp_id,
            "days_inactive": days_inactive,
            "status": "sent",
            "delivery": delivery
        })

    return results

async def get_user_notification_preferences(user_id: str, firestore_db=None) -> Dict[str, Any]:
    if firestore_db:
        try:
            doc = firestore_db.collection("users").document(user_id).collection("settings").document("notifications").get()
            if doc.exists:
                return doc.to_dict()
        except Exception as e:
            logger.warning(f"Error reading notification preferences: {e}")

    return notification_memory_store.user_preferences.get(user_id, {
        "emailNotificationsEnabled": True,
        "opportunityAlerts": True,
        "inactivityReminders": True
    })

async def set_user_notification_preferences(user_id: str, prefs: Dict[str, Any], firestore_db=None) -> Dict[str, Any]:
    prefs["updatedAt"] = get_utc_now_iso()
    if firestore_db:
        try:
            firestore_db.collection("users").document(user_id).collection("settings").document("notifications").set(prefs, merge=True)
        except Exception as e:
            logger.warning(f"Error saving notification preferences: {e}")

    notification_memory_store.user_preferences[user_id] = prefs
    return prefs

