"""Extract detailed interview information from interview request emails."""
import sys
import json
import os
from pathlib import Path
from datetime import datetime

# Add paths
project_root = Path(__file__).parent.parent.parent
api_dir = Path(__file__).parent / "api"
sys.path.insert(0, str(api_dir))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Email, Classification, InterviewEvent, Student
from dotenv import load_dotenv

# Load environment
env_file = project_root / ".env"
load_dotenv(env_file, override=True)

# Create database session
engine = create_engine('sqlite:///email_dashboard.db')
Session = sessionmaker(bind=engine)
db = Session()

print("Extracting interview details from emails...")
print()

# Get all interview request emails
interviews = db.query(Email, Classification).join(
    Classification, Email.id == Classification.email_id
).filter(
    Classification.category == "Interview Request"
).all()

print(f"Found {len(interviews)} interview request emails")
print()

# Import OpenAI
from openai import OpenAI
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

total_processed = 0
total_extracted = 0
total_skipped = 0

for email, classification in interviews:
    # Check if already processed
    existing = db.query(InterviewEvent).filter(
        InterviewEvent.email_id == email.id
    ).first()

    if existing:
        print(f"SKIP: {email.subject[:60]}... (already processed)")
        total_skipped += 1
        continue

    print(f"Processing: {email.subject[:60]}...")

    # Extract interview details using OpenAI
    try:
        # Prefer full_body, but if it's a placeholder, focus on subject
        body_content = email.full_body or email.body_preview or 'N/A'
        is_placeholder = "[Interview request detected from automated processing]" in body_content

        if is_placeholder:
            extraction_note = "Note: Only subject line is available. Extract what you can from it."
            body_to_analyze = "Not available - extract from subject line"
        else:
            extraction_note = "Extract from both subject and body."
            body_to_analyze = body_content

        prompt = f"""Extract interview details from this email. {extraction_note}

Subject: {email.subject}
From: {email.from_address}
Body: {body_to_analyze}
Already known company: {classification.company_name or 'Unknown'}

Extract the following information:
1. Student name (whose interview is this for? Look in body for "Hi [Name]" or recipient name)
2. Interview type - classify based on content:
   - "Interview Request" = invitation to schedule an interview, no confirmed date yet
   - "Phone Screen" = scheduled phone screening call with HR/recruiter
   - "Technical Interview" = coding test, technical assessment, or technical round
   - "Client Screen" = interview with end client or hiring manager
   - "Interview Cancelled" = previously scheduled interview has been cancelled
   - "Interview Rescheduled" = interview moved to a new date/time
   - "Job Machine" = email originates from the Job Machine platform
3. Company name (use the already known company if subject doesn't specify)
4. Position/role (extract from body if mentioned)
5. Contact person name (recruiter or sender name)
6. Contact email (from email address)
7. Interview date (YYYY-MM-DD format if scheduled date mentioned)
8. Interview time (HH:MM format if scheduled time mentioned)
9. Interview format (phone, video, in-person, panel if mentioned)
10. Meeting link if available

IMPORTANT: Only classify emails that are actual interview communications. Do not classify general job opportunity postings or recruiter cold outreach — those are not interviews.

Respond ONLY with valid JSON in this exact format:
{{
  "student_name": "Full Name or null",
  "interview_type": "Interview Request|Phone Screen|Technical Interview|Client Screen|Interview Cancelled|Interview Rescheduled|Job Machine|Other",
  "company_name": "Company or null",
  "position": "Position or null",
  "contact_name": "Name or null",
  "contact_email": "email or null",
  "interview_date": "YYYY-MM-DD or null",
  "interview_time": "HH:MM or null",
  "interview_format": "phone|video|in-person|panel|null",
  "meeting_link": "URL or null"
}}"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert at extracting structured information from interview request emails. Always respond with valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=500
        )

        result_text = response.choices[0].message.content.strip()

        # Remove markdown code blocks if present
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
            result_text = result_text.strip()

        details = json.loads(result_text)

        # Find or create student
        student = None
        if details.get('student_name'):
            student = db.query(Student).filter(
                Student.full_name == details['student_name']
            ).first()

            if not student:
                # Create new student
                student = Student(
                    username=details['student_name'].lower().replace(' ', '_'),
                    full_name=details['student_name'],
                    is_active=True,
                    created_at=datetime.utcnow()
                )
                db.add(student)
                db.flush()
                print(f"  Created student: {details['student_name']}")

        # Create interview event
        interview_event = InterviewEvent(
            email_id=email.id,
            student_id=student.id if student else None,
            sub_type=details.get('interview_type') or 'Other',
            company_name=details.get('company_name') or classification.company_name,
            position_title=details.get('position'),
            contact_name=details.get('contact_name'),
            contact_email=details.get('contact_email'),
            interview_date=details.get('interview_date'),
            interview_time=details.get('interview_time'),
            interview_format=details.get('interview_format'),
            meeting_link=details.get('meeting_link'),
            confidence=classification.confidence,
            raw_extraction=details,
            created_at=datetime.utcnow()
        )

        db.add(interview_event)
        db.commit()

        print(f"  Extracted: Student={details.get('student_name') or 'Unknown'}, "
              f"Type={details.get('interview_type') or 'Other'}, "
              f"Company={details.get('company_name') or 'Unknown'}")

        total_extracted += 1

    except Exception as e:
        print(f"  ERROR: {str(e)}")
        db.rollback()

    total_processed += 1

print()
print("=" * 60)
print(f"Extraction complete!")
print(f"  Total processed: {total_processed}")
print(f"  Successfully extracted: {total_extracted}")
print(f"  Skipped (already processed): {total_skipped}")
print("=" * 60)

db.close()
