"""
Communication Services - Email, SMS, and WhatsApp
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
import structlog

from app.config import settings

logger = structlog.get_logger()


class EmailService:
    """Email service using SendGrid."""
    
    def __init__(self):
        self.api_key = settings.SENDGRID_API_KEY
        self.from_email = settings.SENDGRID_FROM_EMAIL
        self.from_name = settings.SENDGRID_FROM_NAME
        self._client = None
    
    @property
    def client(self):
        """Lazy load SendGrid client."""
        if self._client is None and self.api_key:
            from sendgrid import SendGridAPIClient
            self._client = SendGridAPIClient(self.api_key)
        return self._client
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        plain_content: Optional[str] = None,
        template_id: Optional[str] = None,
        template_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
       
        if not self.client:
            logger.warning("SendGrid not configured, skipping email")
            return {"status": "skipped", "reason": "not_configured"}
        
        try:
            from sendgrid.helpers.mail import Mail, Email, To, Content
            
            message = Mail(
                from_email=Email(self.from_email, self.from_name),
                to_emails=To(to_email),
                subject=subject
            )
            
            if template_id:
                message.template_id = template_id
                if template_data:
                    message.dynamic_template_data = template_data
            else:
                message.add_content(Content("text/html", html_content))
                if plain_content:
                    message.add_content(Content("text/plain", plain_content))
            
            response = self.client.send(message)
            
            logger.info(
                "Email sent",
                to_email=to_email,
                subject=subject,
                status_code=response.status_code
            )
            
            return {
                "status": "sent",
                "status_code": response.status_code,
                "message_id": response.headers.get("X-Message-Id")
            }
            
        except Exception as e:
            logger.error("Email send failed", error=str(e), to_email=to_email)
            return {
                "status": "failed",
                "error": str(e)
            }
    
    async def send_renewal_reminder(
        self,
        to_email: str,
        customer_name: str,
        policy_number: str,
        renewal_date: str,
        renewal_amount: float,
        days_until_renewal: int
    ) -> Dict[str, Any]:
        """Send a renewal reminder email."""
        subject = f"Policy Renewal Reminder - {policy_number}"
        
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #2c5282;">Policy Renewal Reminder</h2>
                
                <p>Dear {customer_name},</p>
                
                <p>This is a friendly reminder that your insurance policy is due for renewal.</p>
                
                <div style="background: #f7fafc; padding: 20px; border-radius: 8px; margin: 20px 0;">
                    <p><strong>Policy Number:</strong> {policy_number}</p>
                    <p><strong>Renewal Date:</strong> {renewal_date}</p>
                    <p><strong>Days Until Renewal:</strong> {days_until_renewal}</p>
                    <p><strong>Renewal Amount:</strong> ${renewal_amount:,.2f}</p>
                </div>
                
                <p>To renew your policy, please visit our portal or contact our support team.</p>
                
                <a href="#" style="display: inline-block; background: #3182ce; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; margin: 20px 0;">
                    Renew Now
                </a>
                
                <p>If you have any questions, our support team is available to help you.</p>
                
                <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 30px 0;">
                
                <p style="color: #718096; font-size: 14px;">
                    This is an automated message. Please do not reply directly to this email.
                </p>
            </div>
        </body>
        </html>
        """
        
        return await self.send_email(to_email, subject, html_content)


class SMSService:
    """SMS service using Twilio."""
    
    def __init__(self):
        self.account_sid = settings.TWILIO_ACCOUNT_SID
        self.auth_token = settings.TWILIO_AUTH_TOKEN
        self.from_number = settings.TWILIO_PHONE_NUMBER
        self._client = None
    
    @property
    def client(self):
        """Lazy load Twilio client."""
        if self._client is None and self.account_sid and self.auth_token:
            from twilio.rest import Client
            self._client = Client(self.account_sid, self.auth_token)
        return self._client
    
    def _format_number(self, number: str) -> str:
        """Ensure number is in E.164 format."""
        cleaned = number.strip()
        if not cleaned.startswith("+"):
            # Default to India (+91) if no country code provided
            # This is a heuristic based on the user base
            return f"+91{cleaned}"
        return cleaned

    async def send_sms(
        self,
        to_number: str,
        message: str
    ) -> Dict[str, Any]:
        """
        Send an SMS via Twilio.
        
        Args:
            to_number: Recipient phone number (E.164 format)
            message: SMS message content (max 160 chars for single SMS)
            
        Returns:
            Dict with status and message_sid
        """
        if not self.client:
            logger.warning("Twilio not configured, skipping SMS")
            return {"status": "skipped", "reason": "not_configured"}
        
        formatted_number = self._format_number(to_number)
        
        try:
            sms = self.client.messages.create(
                body=message,
                from_=self.from_number,
                to=formatted_number
            )
            
            logger.info(
                "SMS sent",
                to_number=formatted_number,
                original_number=to_number,
                message_sid=sms.sid
            )
            
            return {
                "status": "sent",
                "message_sid": sms.sid,
                "to": sms.to
            }
            
        except Exception as e:
            logger.error("SMS send failed", error=str(e), to_number=formatted_number)
            return {
                "status": "failed",
                "error": str(e)
            }
    
    async def send_renewal_reminder(
        self,
        to_number: str,
        customer_name: str,
        policy_number: str,
        renewal_date: str,
        days_until_renewal: int
    ) -> Dict[str, Any]:
        """Send a renewal reminder SMS."""
        message = (
            f"Hi {customer_name}, your policy {policy_number} is due for renewal "
            f"on {renewal_date} ({days_until_renewal} days). "
            f"Reply RENEW to start or visit our portal."
        )
        
        return await self.send_sms(to_number, message)


class WhatsAppService:
    """WhatsApp service using Twilio."""
    
    def __init__(self):
        self.account_sid = settings.TWILIO_ACCOUNT_SID
        self.auth_token = settings.TWILIO_AUTH_TOKEN
        self.from_number = settings.TWILIO_WHATSAPP_NUMBER
        self._client = None
    
    @property
    def client(self):
        """Lazy load Twilio client."""
        if self._client is None and self.account_sid and self.auth_token:
            from twilio.rest import Client
            self._client = Client(self.account_sid, self.auth_token)
        return self._client
    
    def _format_number(self, number: str) -> str:
        """Ensure number is in E.164 format."""
        cleaned = number.strip()
        if not cleaned.startswith("+"):
            # Default to India (+91) if no country code provided
            return f"+91{cleaned}"
        return cleaned

    async def send_whatsapp(
        self,
        to_number: str,
        message: str,
        media_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send a WhatsApp message via Twilio.
        
        Args:
            to_number: Recipient phone number (E.164 format)
            message: Message content
            media_url: Optional URL for media attachment
            
        Returns:
            Dict with status and message_sid
        """
        if not self.client:
            logger.warning("Twilio WhatsApp not configured, skipping")
            return {"status": "skipped", "reason": "not_configured"}
        
        formatted_number = self._format_number(to_number)
        
        try:
            kwargs = {
                "body": message,
                "from_": f"whatsapp:{self.from_number}",
                "to": f"whatsapp:{formatted_number}"
            }
            
            if media_url:
                kwargs["media_url"] = [media_url]
            
            whatsapp_message = self.client.messages.create(**kwargs)
            
            logger.info(
                "WhatsApp sent",
                to_number=formatted_number,
                original_number=to_number,
                message_sid=whatsapp_message.sid
            )
            
            return {
                "status": "sent",
                "message_sid": whatsapp_message.sid,
                "to": whatsapp_message.to
            }
            
        except Exception as e:
            logger.error("WhatsApp send failed", error=str(e), to_number=formatted_number)
            return {
                "status": "failed",
                "error": str(e)
            }
    
    async def send_renewal_reminder(
        self,
        to_number: str,
        customer_name: str,
        policy_number: str,
        renewal_date: str,
        renewal_amount: float,
        days_until_renewal: int
    ) -> Dict[str, Any]:
        """Send a renewal reminder via WhatsApp."""
        message = f"""
🔔 *Policy Renewal Reminder*

Hi {customer_name}!

Your insurance policy is due for renewal:

📋 *Policy:* {policy_number}
📅 *Renewal Date:* {renewal_date}
⏰ *Days Remaining:* {days_until_renewal}
💰 *Amount:* ${renewal_amount:,.2f}

Reply with:
• *RENEW* - Start renewal process
• *DETAILS* - Get policy details
• *HELP* - Speak to an agent

Thank you for being a valued customer! 🙏
        """.strip()
        
        return await self.send_whatsapp(to_number, message)


class CommunicationGateway:
    """Unified communication gateway for multi-channel delivery."""
    
    def __init__(self):
        self.email_service = EmailService()
        self.sms_service = SMSService()
        self.whatsapp_service = WhatsAppService()

    async def send_reminder(
        self,
        channel: str,
        customer_data: Dict[str, Any],
        policy_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Send a reminder through the specified channel.
        
        Args:
            channel: Communication channel (email, sms, whatsapp)
            customer_data: Customer information
            policy_data: Policy and renewal information
            
        Returns:
            Result from the channel service
        """
        customer_name = customer_data.get("name", "Valued Customer")
        
        if channel == "email":
            return await self.email_service.send_renewal_reminder(
                to_email=customer_data["email"],
                customer_name=customer_name,
                policy_number=policy_data["policy_number"],
                renewal_date=policy_data["renewal_date"],
                renewal_amount=policy_data["renewal_amount"],
                days_until_renewal=policy_data["days_until_renewal"]
            )
        
        elif channel == "sms":
            return await self.sms_service.send_renewal_reminder(
                to_number=customer_data["phone"],
                customer_name=customer_name,
                policy_number=policy_data["policy_number"],
                renewal_date=policy_data["renewal_date"],
                days_until_renewal=policy_data["days_until_renewal"]
            )
        
        elif channel == "whatsapp":
            return await self.whatsapp_service.send_renewal_reminder(
                to_number=customer_data["phone"],
                customer_name=customer_name,
                policy_number=policy_data["policy_number"],
                renewal_date=policy_data["renewal_date"],
                renewal_amount=policy_data["renewal_amount"],
                days_until_renewal=policy_data["days_until_renewal"]
            )
        
        else:
            return {
                "status": "failed",
                "error": f"Unknown channel: {channel}"
            }


# ===========================================
# Helper function for sending reminders
# ===========================================

async def send_reminder_message(reminder, db) -> bool:
    """
    Send a reminder message through the appropriate channel.
    
    This is a helper function used by the reminders API to send
    individual reminders directly.
    
    Args:
        reminder: RenewalReminder model instance
        db: Database session
        
    Returns:
        bool: True if sent successfully, False otherwise
    """
    from sqlalchemy.orm import selectinload
    from sqlalchemy import select
    from app.models import Policy
    
    # Load policy and customer if not already loaded
    if not reminder.policy:
        query = (
            select(Policy)
            .options(selectinload(Policy.customer))
            .where(Policy.id == reminder.policy_id)
        )
        result = await db.execute(query)
        policy = result.scalar_one_or_none()
    else:
        policy = reminder.policy
    
    if not policy or not policy.customer:
        logger.error("Cannot send reminder - missing policy or customer",
                    reminder_id=str(reminder.id))
        return False
    
    customer = policy.customer
    gateway = CommunicationGateway()
    
    customer_data = {
        "name": customer.full_name,
        "email": customer.email,
        "phone": customer.phone
    }
    
    from datetime import date
    days_until = (policy.renewal_date - date.today()).days
    
    policy_data = {
        "policy_number": policy.policy_number,
        "renewal_date": policy.renewal_date.isoformat(),
        "renewal_amount": float(policy.premium_amount) * 1.03,
        "days_until_renewal": days_until
    }
    
    result = await gateway.send_reminder(
        channel=reminder.channel.value,
        customer_data=customer_data,
        policy_data=policy_data
    )
    
    # Update reminder with external ID if available
    if result.get("message_id"):
        reminder.external_id = result["message_id"]
    elif result.get("message_sid"):
        reminder.external_id = result["message_sid"]
    
    if result.get("status") == "failed":
        reminder.error_message = result.get("error", "Unknown error")
        return False
    
    return result.get("status") in ["sent", "delivered"]
