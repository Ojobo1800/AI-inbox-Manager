"""
Notification drafting execution script.

Takes interview sub-classification results and student info to produce:
1. A populated email notification (from the correct template)
2. A short WhatsApp summary message

Design principles:
- Deterministic template population (no AI)
- Detects and reports missing fields
- Generates both email and WhatsApp drafts in one pass
"""

import logging
import os
import re
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

from execution.email_templates import select_template, EmailTemplate

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Default assistant name (configurable via env)
DEFAULT_ASSISTANT_NAME = os.getenv("STUDENT_ASSISTANT_NAME", "Robelyn")

# WhatsApp sender config
WHATSAPP_SENDERS = {
    "Jackie": os.getenv("WHATSAPP_SENDER_JACKIE", "214-607-8702"),
    "Ali": os.getenv("WHATSAPP_SENDER_ALI", "682-597-5784"),
}
DEFAULT_WHATSAPP_SENDER = os.getenv("WHATSAPP_DEFAULT_SENDER", "Jackie")

# Human-readable sub-type labels for WhatsApp messages
SUBTYPE_LABELS = {
    "Interview Request": "interview",
    "Phone Screen": "phone screening",
    "Client Screen": "client interview",
    "Technical Interview": "technical round",
    "Interview Cancelled": "interview cancellation",
    "Interview Rescheduled": "interview reschedule",
    "Job Machine": "interview",
}


def format_interview_datetime(
    interview_date: Optional[str],
    interview_time: Optional[str],
    interview_timezone: Optional[str] = None,
) -> str:
    """
    Format interview date and time into a human-readable string.

    Args:
        interview_date: Date in YYYY-MM-DD format
        interview_time: Time in HH:MM format
        interview_timezone: Timezone string (e.g., "EST")

    Returns:
        Formatted datetime string, or "TBD" if no date
    """
    if not interview_date:
        return "TBD"

    parts = [interview_date]
    if interview_time:
        parts.append(f"at {interview_time}")
    if interview_timezone:
        parts.append(interview_timezone)

    return " ".join(parts)


def build_template_data(
    classification: Dict[str, Any],
    student_info: Dict[str, Any],
    assistant_name: Optional[str] = None,
) -> Dict[str, str]:
    """
    Build the data dictionary for template placeholder substitution.

    Maps fields from classification result and student info to template placeholders.

    Args:
        classification: Sub-classification result from subclassify_interview.py
        student_info: Student info from fetch_student_info.py
        assistant_name: Name for the email signature

    Returns:
        Dictionary mapping placeholder names to values
    """
    interview_datetime = format_interview_datetime(
        classification.get("interview_date"),
        classification.get("interview_time"),
        classification.get("interview_timezone"),
    )

    return {
        # Student fields
        "student_name": student_info.get("full_name") or "Student",
        "assigned_gmail": student_info.get("assigned_gmail") or student_info.get("student_gmail") or "",
        "personal_email": student_info.get("personal_email") or "",
        # Interview fields
        "company_name": classification.get("company_name") or "",
        "position_title": classification.get("position_title") or "",
        "contact_name": classification.get("contact_name") or "",
        "contact_title": classification.get("contact_title") or "",
        "contact_email": classification.get("contact_email") or "",
        "contact_phone": classification.get("contact_phone") or "",
        "interview_datetime": interview_datetime,
        "num_interviewers": str(classification.get("num_interviewers") or ""),
        "job_description_url": classification.get("job_description_url") or "",
        # Config
        "assistant_name": assistant_name or DEFAULT_ASSISTANT_NAME,
    }


def populate_template(
    template: EmailTemplate,
    data: Dict[str, str],
) -> Dict[str, Any]:
    """
    Populate a template with data, detecting missing fields.

    Args:
        template: The EmailTemplate to populate
        data: Dictionary of placeholder values

    Returns:
        Dictionary with:
            - subject: Populated subject line
            - body: Populated body text
            - missing_fields: List of required fields that are empty/missing
    """
    missing_fields = []

    # Check required fields
    # "TBD" is treated as missing since it means data hasn't been determined
    for field_name in template.required_fields:
        value = data.get(field_name)
        if not value or value.strip() == "" or value.strip().upper() == "TBD":
            missing_fields.append(field_name)

    # Populate subject - use safe substitution
    subject = _safe_format(template.subject_template, data)
    body = _safe_format(template.body_template, data)

    return {
        "subject": subject,
        "body": body,
        "missing_fields": missing_fields,
    }


def _safe_format(template_str: str, data: Dict[str, str]) -> str:
    """
    Safely format a template string, leaving unfilled placeholders visible.

    Args:
        template_str: Template with {placeholder} markers
        data: Dictionary of values

    Returns:
        Formatted string with placeholders replaced
    """
    result = template_str
    # Find all {placeholders} in the template
    placeholders = re.findall(r"\{(\w+)\}", template_str)
    for placeholder in placeholders:
        value = data.get(placeholder, "")
        if value:
            result = result.replace("{" + placeholder + "}", value)
        else:
            # Leave placeholder visible so humans can fill it in
            result = result.replace(
                "{" + placeholder + "}", f"[{placeholder}]"
            )
    return result


def generate_whatsapp_message(
    classification: Dict[str, Any],
    student_info: Dict[str, Any],
) -> str:
    """
    Generate a short WhatsApp summary message.

    Args:
        classification: Sub-classification result
        student_info: Student info

    Returns:
        Short WhatsApp message text (2-3 sentences)
    """
    student_name = student_info.get("full_name") or "there"
    sub_type = classification.get("interview_sub_type", "")
    company = classification.get("company_name") or "a company"
    position = classification.get("position_title") or ""
    interview_date = classification.get("interview_date")
    interview_time = classification.get("interview_time")

    type_label = SUBTYPE_LABELS.get(sub_type, "interview update")

    # Build the message based on sub-type
    if sub_type == "Interview Cancelled":
        return (
            f"Hi {student_name}! Heads up - your interview with {company} "
            f"has been cancelled. Please check your personal email for details "
            f"and next steps."
        )

    if sub_type == "Interview Rescheduled":
        datetime_str = format_interview_datetime(interview_date, interview_time)
        return (
            f"Hi {student_name}! Your interview with {company} has been "
            f"rescheduled to {datetime_str}. "
            f"Please check your personal email for full details."
        )

    # For all other types (requests, screens, technical)
    position_part = f" for the {position} role" if position else ""
    datetime_part = ""
    if interview_date:
        datetime_str = format_interview_datetime(interview_date, interview_time)
        datetime_part = f" on {datetime_str}"

    return (
        f"Hi {student_name}! You have a {type_label} with {company}"
        f"{position_part}{datetime_part}. "
        f"Please check your personal email for full details and next steps."
    )


def draft_notification(
    classification: Dict[str, Any],
    student_info: Dict[str, Any],
    assistant_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Draft a complete notification (email + WhatsApp) for a student.

    Main entry point for notification drafting.

    Args:
        classification: Sub-classification result from subclassify_interview.py
        student_info: Student info from fetch_student_info.py
        assistant_name: Optional name for email signature

    Returns:
        Dictionary with:
            - template_id: Which template was used
            - template_name: Human-readable template name
            - email_subject: Populated subject line
            - email_body: Populated email body
            - recipient_email: Student's personal email
            - bcc: BCC address
            - missing_fields: List of unfilled required fields
            - draft_status: "ready" | "needs_review" | "no_template"
            - whatsapp_message: Short WhatsApp summary
            - whatsapp_recipient_phone: Student's phone number
            - whatsapp_sender_name: Sender name (Jackie/Ali)
            - whatsapp_sender_phone: Sender phone number
    """
    sub_type = classification.get("interview_sub_type", "")
    is_job_machine = classification.get("is_job_machine", False)
    is_next_round = classification.get("is_next_round", False)
    has_confirmed_date = bool(classification.get("interview_date"))

    # Resolve Job Machine sub-type to actual sub-type for template selection
    actual_sub_type = sub_type
    if sub_type == "Job Machine":
        jm_sub = classification.get("job_machine_sub_type", "interview")
        is_job_machine = True
        if jm_sub == "reschedule":
            actual_sub_type = "Interview Rescheduled"
        elif jm_sub == "cancellation":
            actual_sub_type = "Interview Cancelled"
        else:
            # Default to Interview Request for Job Machine interviews
            if has_confirmed_date:
                actual_sub_type = "Phone Screen"  # Scheduled via JM
            else:
                actual_sub_type = "Interview Request"

    # Select template
    template = select_template(
        sub_type=actual_sub_type,
        is_job_machine=is_job_machine,
        is_next_round=is_next_round,
        has_confirmed_date=has_confirmed_date,
    )

    if not template:
        logger.warning(f"No template found for sub-type: {sub_type}")
        whatsapp_msg = generate_whatsapp_message(classification, student_info)
        return {
            "template_id": None,
            "template_name": None,
            "email_subject": "",
            "email_body": "",
            "recipient_email": student_info.get("personal_email") or "",
            "bcc": "c_interviews@colaberry.com",
            "missing_fields": ["template"],
            "draft_status": "no_template",
            "whatsapp_message": whatsapp_msg,
            "whatsapp_recipient_phone": student_info.get("phone_number") or "",
            "whatsapp_sender_name": DEFAULT_WHATSAPP_SENDER,
            "whatsapp_sender_phone": WHATSAPP_SENDERS.get(
                DEFAULT_WHATSAPP_SENDER, ""
            ),
        }

    # Build data and populate template
    data = build_template_data(classification, student_info, assistant_name)
    populated = populate_template(template, data)

    # Determine draft status
    if populated["missing_fields"]:
        draft_status = "needs_review"
    else:
        draft_status = "ready"

    # Generate WhatsApp message
    whatsapp_msg = generate_whatsapp_message(classification, student_info)

    # Get WhatsApp sender info
    sender_name = DEFAULT_WHATSAPP_SENDER
    sender_phone = WHATSAPP_SENDERS.get(sender_name, "")

    return {
        "template_id": template.template_id,
        "template_name": template.template_name,
        "email_subject": populated["subject"],
        "email_body": populated["body"],
        "recipient_email": student_info.get("personal_email") or "",
        "bcc": "c_interviews@colaberry.com",
        "missing_fields": populated["missing_fields"],
        "draft_status": draft_status,
        "whatsapp_message": whatsapp_msg,
        "whatsapp_recipient_phone": student_info.get("phone_number") or "",
        "whatsapp_sender_name": sender_name,
        "whatsapp_sender_phone": sender_phone,
    }
