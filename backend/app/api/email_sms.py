from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict, Any
import structlog

from app.api.auth import get_current_user
from app.tasks.communication_tasks import send_email_sendgrid_task, send_sms_twilio_task

logger = structlog.get_logger()
router = APIRouter(prefix="/email-sms", tags=["Email & SMS"])

# Request Models
class SendEmailRequest(BaseModel):
    to_email: EmailStr
    subject: str
    html_content: str
    from_email: Optional[EmailStr] = None
    app_name: Optional[str] = None
    plain_content: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class SendSMSRequest(BaseModel):
    to_number: str = Field(..., description="Phone number in E.164 format (e.g., +1234567890)")
    message_body: str
    from_number: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class TaskStatusResponse(BaseModel):
    task_id: str
    message: str

# Routes
@router.post("/send-email-sendgrid", response_model=TaskStatusResponse, status_code=status.HTTP_202_ACCEPTED)
async def send_email_sendgrid(
    payload: SendEmailRequest, 
    # current_user: dict = Depends(get_current_user)
):
    """Send email via SendGrid using Celery task."""
    try:
        task = send_email_sendgrid_task.delay(
            to_email=payload.to_email,
            subject=payload.subject,
            html_content=payload.html_content,
            from_email=payload.from_email,
            app_name=payload.app_name,
            plain_content=payload.plain_content,
            metadata=payload.metadata
        )
        logger.info(f"Queued SendGrid email task {task.id} to {payload.to_email}")
        return TaskStatusResponse(task_id=task.id, message="Email send task queued successfully.")
    except Exception as e:
        logger.error(f"Failed to queue SendGrid email: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to queue email task: {str(e)}")

@router.post("/send-sms-twilio", response_model=TaskStatusResponse, status_code=status.HTTP_202_ACCEPTED)
async def send_sms_twilio(
    payload: SendSMSRequest, 
    # current_user: dict = Depends(get_current_user)
):
    """Send SMS via Twilio using Celery task."""
    try:
        task = send_sms_twilio_task.delay(
            to_number=payload.to_number,
            message_body=payload.message_body,
            from_number=payload.from_number,
            metadata=payload.metadata
        )
        logger.info(f"Queued Twilio SMS task {task.id} to {payload.to_number}")
        return TaskStatusResponse(task_id=task.id, message="SMS send task queued successfully.")
    except Exception as e:
        logger.error(f"Failed to queue Twilio SMS: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to queue SMS task: {str(e)}")
