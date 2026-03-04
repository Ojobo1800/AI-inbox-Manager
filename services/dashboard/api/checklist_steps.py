"""
Interview process checklist step definitions.

Defines the rubric steps and sub-steps for each interview sub_type.
Step keys use dotted notation:
  - Main steps: "{sub_type}.{step_num}"
  - Sub-steps:  "{sub_type}.{step_num}.{sub_step_num}"

These are business process constants derived from the interview
processing rubric. Only completion state is stored in the database.
"""

CHECKLIST_DEFINITIONS = {
    "interview_request": {
        "sub_type": "interview_request",
        "label": "Interview Request",
        "steps": [
            {
                "key": "interview_request.1",
                "label": "Review the interview request email",
                "sub_steps": [
                    {
                        "key": "interview_request.1.1",
                        "label": "Open the interview request email",
                    },
                    {
                        "key": "interview_request.1.2",
                        "label": "Verify key details: interview type, sender, time slot options",
                    },
                ],
            },
            {
                "key": "interview_request.2",
                "label": "Notify the student via personal email",
                "sub_steps": [
                    {
                        "key": "interview_request.2.1",
                        "label": "Inform the student they have an interview",
                    },
                    {
                        "key": "interview_request.2.2",
                        "label": "Direct them to check their email for details",
                    },
                ],
            },
        ],
    },
    "phone_screen": {
        "sub_type": "phone_screen",
        "label": "Phone Screen",
        "steps": [
            {
                "key": "phone_screen.1",
                "label": "Review the phone screen request email",
                "sub_steps": [
                    {
                        "key": "phone_screen.1.1",
                        "label": "Verify details: type, sender, date, dial-in/phone number",
                    },
                ],
            },
            {
                "key": "phone_screen.2",
                "label": "Notify the student via personal email",
                "sub_steps": [
                    {
                        "key": "phone_screen.2.1",
                        "label": "Provide date/time and dial-in instructions",
                    },
                    {
                        "key": "phone_screen.2.2",
                        "label": "Confirm time with student",
                    },
                ],
            },
        ],
    },
    "client_screen": {
        "sub_type": "client_screen",
        "label": "Client Screen",
        "steps": [
            {
                "key": "client_screen.1",
                "label": "Review the client screen request email",
                "sub_steps": [
                    {
                        "key": "client_screen.1.1",
                        "label": "Verify details: second round, sender/HR team, date, attendees, materials needed",
                    },
                ],
            },
            {
                "key": "client_screen.2",
                "label": "Notify the student via personal email",
                "sub_steps": [
                    {
                        "key": "client_screen.2.1",
                        "label": "Mention interview attendees",
                    },
                    {
                        "key": "client_screen.2.2",
                        "label": "Include any preparation materials",
                    },
                ],
            },
        ],
    },
    "technical_interview": {
        "sub_type": "technical_interview",
        "label": "Technical Interview",
        "steps": [
            {
                "key": "technical_interview.1",
                "label": "Review the technical interview request email",
                "sub_steps": [
                    {
                        "key": "technical_interview.1.1",
                        "label": "Verify: type, sender/tech team lead, date, format/assessment type",
                    },
                ],
            },
            {
                "key": "technical_interview.2",
                "label": "Notify the student via personal email",
                "sub_steps": [
                    {
                        "key": "technical_interview.2.1",
                        "label": "Include technical preparation guidance",
                    },
                ],
            },
        ],
    },
    "cancelled": {
        "sub_type": "cancelled",
        "label": "Interview Cancelled",
        "steps": [
            {
                "key": "cancelled.1",
                "label": "Review the cancelled interview email",
                "sub_steps": [
                    {
                        "key": "cancelled.1.1",
                        "label": "Verify cancellation details and reason",
                    },
                ],
            },
            {
                "key": "cancelled.2",
                "label": "Notify the student via personal email",
                "sub_steps": [
                    {
                        "key": "cancelled.2.1",
                        "label": "Explain reason for cancellation",
                    },
                    {
                        "key": "cancelled.2.2",
                        "label": "Suggest rescheduling if applicable",
                    },
                ],
            },
        ],
    },
    "rescheduled": {
        "sub_type": "rescheduled",
        "label": "Interview Rescheduled",
        "steps": [
            {
                "key": "rescheduled.1",
                "label": "Review the rescheduled interview email",
                "sub_steps": [
                    {
                        "key": "rescheduled.1.1",
                        "label": "Verify new date/time/platform",
                    },
                ],
            },
            {
                "key": "rescheduled.2",
                "label": "Notify the student via personal email",
                "sub_steps": [
                    {
                        "key": "rescheduled.2.1",
                        "label": "Provide new date/time/platform details",
                    },
                    {
                        "key": "rescheduled.2.2",
                        "label": "Ensure student has enough time to prepare",
                    },
                ],
            },
        ],
    },
    "job_machine": {
        "sub_type": "job_machine",
        "label": "Job Machine",
        "steps": [
            {
                "key": "job_machine.1",
                "label": "Review the Job Machine notification email",
                "sub_steps": [
                    {
                        "key": "job_machine.1.1",
                        "label": "Identify Job Machine sub-type (interview/reschedule/cancellation)",
                    },
                    {
                        "key": "job_machine.1.2",
                        "label": "Extract actual interview details",
                    },
                ],
            },
            {
                "key": "job_machine.2",
                "label": "Notify the student via personal email",
                "sub_steps": [
                    {
                        "key": "job_machine.2.1",
                        "label": "Include Job Machine-specific instructions",
                    },
                ],
            },
        ],
    },
}


# Map DB sub_type values (title case from AI) to snake_case definition keys
_SUB_TYPE_NORMALIZE = {
    "Interview Request": "interview_request",
    "Phone Screen": "phone_screen",
    "Client Screen": "client_screen",
    "Technical Interview": "technical_interview",
    "Interview Cancelled": "cancelled",
    "Interview Rescheduled": "rescheduled",
    "Job Machine": "job_machine",
    # Identity mappings for values already in snake_case
    "interview_request": "interview_request",
    "phone_screen": "phone_screen",
    "client_screen": "client_screen",
    "technical_interview": "technical_interview",
    "cancelled": "cancelled",
    "rescheduled": "rescheduled",
    "job_machine": "job_machine",
}


def normalize_sub_type(sub_type: str) -> str:
    """Normalize a sub_type value to the snake_case key used in definitions.

    Handles both title case values from the AI pipeline and
    snake_case values that may already be normalized.

    Returns the original value if no mapping is found.
    """
    return _SUB_TYPE_NORMALIZE.get(sub_type, sub_type)


def get_all_step_keys(sub_type: str) -> list:
    """Return all valid step keys for a given sub_type."""
    normalized = normalize_sub_type(sub_type)
    defn = CHECKLIST_DEFINITIONS.get(normalized)
    if not defn:
        return []
    keys = []
    for step in defn["steps"]:
        keys.append(step["key"])
        for sub in step["sub_steps"]:
            keys.append(sub["key"])
    return keys
