"""
Renewal Agent - Handles policy renewal conversations and processes
"""

from typing import Dict, Any, Optional, List
from datetime import date
import structlog

from openai import AsyncOpenAI

logger = structlog.get_logger()


class RenewalAgent:
    """
    AI Agent specialized in handling policy renewal conversations.
    
    Responsibilities:
    - Guide customers through renewal process
    - Calculate and explain renewal amounts
    - Process renewal requests
    - Handle policy modifications during renewal
    """
    
    SYSTEM_PROMPT = """You are a Renewal Specialist AI Agent for an insurance company.
Your role is to help customers understand and complete their policy renewals.

Guidelines:
1. Be professional, friendly, and helpful
2. Always verify policy details before processing renewals
3. Clearly explain renewal amounts and any changes
4. Guide customers step by step through the renewal process
5. If the customer has questions about coverage, answer them or transfer to the Query Agent
6. For complex modifications, recommend speaking with a human agent

When processing renewals:
- Confirm the policy number and customer identity
- Explain the renewal amount breakdown
- Ask for confirmation before processing
- Provide next steps after renewal is initiated
"""

    def __init__(
        self,
        model_id: str,
        api_key: str,
        api_base: str = "https://models.github.ai/inference"
    ):
        self.client = AsyncOpenAI(
            base_url=api_base,
            api_key=api_key
        )
        self.model_id = model_id
    
    async def process_renewal_request(
        self,
        customer_id: str,
        policy_number: str,
        policy_details: Dict[str, Any],
        customer_message: str
    ) -> Dict[str, Any]:
        """
        Process a renewal-related request from a customer.
        
        Args:
            customer_id: Customer UUID
            policy_number: Policy number
            policy_details: Current policy details
            customer_message: Customer's message
            
        Returns:
            Response with action and message
        """
        # Build context message
        context = f"""
Policy Details:
- Policy Number: {policy_number}
- Type: {policy_details.get('policy_type')}
- Coverage: {policy_details.get('coverage_type')}
- Current Premium: ${policy_details.get('premium_amount', 0):,.2f}
- Renewal Date: {policy_details.get('renewal_date')}
- Days Until Renewal: {policy_details.get('days_until_renewal')}
"""
        
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "system", "content": context},
            {"role": "user", "content": customer_message}
        ]
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model_id,
                messages=messages,
                temperature=0.7,
                max_tokens=500
            )
            
            return {
                "response": response.choices[0].message.content,
                "action": self._detect_action(customer_message),
                "policy_number": policy_number
            }
            
        except Exception as e:
            logger.error("Renewal agent error", error=str(e))
            return {
                "response": "I apologize, but I'm having trouble processing your request. Please try again.",
                "action": "error",
                "error": str(e)
            }
    
    async def generate_renewal_summary(
        self,
        policy_details: Dict[str, Any],
        renewal_calculation: Dict[str, Any]
    ) -> str:
        """
        Generate a renewal summary for the customer.
        
        Args:
            policy_details: Current policy details
            renewal_calculation: Calculated renewal amounts
            
        Returns:
            Formatted renewal summary
        """
        prompt = f"""Generate a clear, concise renewal summary for the customer based on:

Current Policy:
- Policy Number: {policy_details.get('policy_number')}
- Type: {policy_details.get('policy_type')}
- Coverage Amount: ${policy_details.get('coverage_amount', 0):,.2f}

Renewal Details:
- Current Premium: ${renewal_calculation.get('current_premium', 0):,.2f}
- New Premium: ${renewal_calculation.get('renewal_premium', 0):,.2f}
- Change: {renewal_calculation.get('premium_change_percent', 0):.1f}%
- Renewal Date: {policy_details.get('renewal_date')}

Create a friendly, professional summary explaining the renewal."""

        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model_id,
                messages=messages,
                temperature=0.5,
                max_tokens=400
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error("Summary generation error", error=str(e))
            return self._fallback_summary(policy_details, renewal_calculation)
    
    def _detect_action(self, message: str) -> str:
        """Detect the intended action from the message."""
        message_lower = message.lower()
        
        if any(w in message_lower for w in ["renew", "yes", "confirm", "proceed", "accept"]):
            return "confirm_renewal"
        elif any(w in message_lower for w in ["change", "modify", "update", "different"]):
            return "modify_policy"
        elif any(w in message_lower for w in ["cancel", "stop", "don't", "no"]):
            return "cancel_renewal"
        elif any(w in message_lower for w in ["question", "what", "how", "why", "explain"]):
            return "question"
        else:
            return "general"
    
    def _fallback_summary(
        self,
        policy_details: Dict[str, Any],
        renewal_calculation: Dict[str, Any]
    ) -> str:
        """Generate a fallback summary if AI fails."""
        return f"""
**Policy Renewal Summary**

**Policy Number:** {policy_details.get('policy_number')}
**Policy Type:** {policy_details.get('policy_type')}

**Premium Details:**
- Current Premium: ${renewal_calculation.get('current_premium', 0):,.2f}
- Renewal Premium: ${renewal_calculation.get('renewal_premium', 0):,.2f}
- Change: {renewal_calculation.get('premium_change_percent', 0):.1f}%

**Renewal Date:** {policy_details.get('renewal_date')}

To proceed with renewal, please confirm by replying "Yes, renew my policy."
"""
