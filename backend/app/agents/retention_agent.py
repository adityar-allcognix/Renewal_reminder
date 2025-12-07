"""
Retention Agent - Manages retention outreach for customers at risk of lapsing
"""

from typing import Dict, Any, Optional, List
from datetime import date, timedelta
import structlog

from openai import AsyncOpenAI

logger = structlog.get_logger()


class RetentionAgent:
    """
    AI Agent specialized in customer retention.
    
    Responsibilities:
    - Identify at-risk customers
    - Generate personalized retention messages
    - Suggest retention strategies based on customer profile
    - Handle objections and concerns
    """
    
    SYSTEM_PROMPT = """You are a Customer Retention Specialist AI Agent for an insurance company.
Your goal is to help retain customers who may be at risk of not renewing their policies.

Guidelines:
1. Be empathetic and understanding - listen to customer concerns
2. Highlight the value and benefits of their current coverage
3. Offer solutions to address their specific concerns
4. Never be pushy or aggressive - maintain professionalism
5. If appropriate, suggest policy modifications that might better fit their needs

Retention Strategies:
- Emphasize continuous coverage benefits
- Remind of claims-free discounts earned
- Highlight any loyalty rewards or benefits
- Explain the risks of coverage gaps
- Offer payment plan options if cost is a concern
- Suggest policy adjustments to reduce premiums while maintaining essential coverage

Always be honest and never make promises you can't keep.
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
    
    async def generate_retention_message(
        self,
        customer_profile: Dict[str, Any],
        policy_details: Dict[str, Any],
        engagement_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate a personalized retention outreach message.
        
        Args:
            customer_profile: Customer information and preferences
            policy_details: Policy details including renewal info
            engagement_data: Customer engagement history
            
        Returns:
            Personalized retention message
        """
        # Build customer context
        context = self._build_customer_context(
            customer_profile, policy_details, engagement_data
        )
        
        prompt = f"""Generate a personalized retention message for this customer:

{context}

Create a warm, personalized message that:
1. Acknowledges their importance as a customer
2. Highlights relevant benefits of their policy
3. Addresses potential concerns based on their profile
4. Includes a clear call to action
5. Keeps a friendly, professional tone

Message should be 2-3 paragraphs, suitable for email or WhatsApp."""

        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model_id,
                messages=messages,
                temperature=0.7,
                max_tokens=400
            )
            
            message = response.choices[0].message.content
            
            return {
                "message": message,
                "strategy": self._determine_strategy(engagement_data),
                "urgency": self._calculate_urgency(policy_details),
                "personalization_score": self._calculate_personalization(
                    customer_profile
                )
            }
            
        except Exception as e:
            logger.error("Retention message generation error", error=str(e))
            return self._fallback_message(customer_profile, policy_details)
    
    async def handle_objection(
        self,
        customer_id: str,
        objection: str,
        customer_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle a customer objection during retention conversation.
        
        Args:
            customer_id: Customer UUID
            objection: Customer's stated objection or concern
            customer_context: Customer and policy information
            
        Returns:
            Response addressing the objection
        """
        prompt = f"""The customer has expressed this concern about renewing their policy:

Customer Concern: "{objection}"

Customer Context:
- Policy Type: {customer_context.get('policy_type')}
- Years as Customer: {customer_context.get('years_customer', 'Unknown')}
- Engagement Score: {customer_context.get('engagement_score', 50)}/100

Provide a thoughtful, empathetic response that:
1. Acknowledges their concern
2. Addresses it directly with helpful information
3. Offers potential solutions if applicable
4. Maintains a supportive, non-pushy tone

Keep the response concise (2-3 paragraphs)."""

        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model_id,
                messages=messages,
                temperature=0.6,
                max_tokens=300
            )
            
            return {
                "response": response.choices[0].message.content,
                "objection_type": self._classify_objection(objection),
                "recommended_action": self._recommend_action(objection)
            }
            
        except Exception as e:
            logger.error("Objection handling error", error=str(e))
            return {
                "response": "I understand your concern. Let me connect you with a specialist who can better assist you with this.",
                "objection_type": "unknown",
                "recommended_action": "escalate_to_human"
            }
    
    async def score_retention_probability(
        self,
        customer_profile: Dict[str, Any],
        policy_details: Dict[str, Any],
        interaction_history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Score the probability of retaining a customer.
        
        Args:
            customer_profile: Customer information
            policy_details: Policy details
            interaction_history: Recent interactions
            
        Returns:
            Retention probability score and factors
        """
        score = 50.0  # Base score
        factors = []
        
        # Factor 1: Engagement score
        engagement = customer_profile.get('engagement_score', 50)
        if engagement >= 70:
            score += 15
            factors.append(("High engagement", +15))
        elif engagement <= 30:
            score -= 15
            factors.append(("Low engagement", -15))
        
        # Factor 2: Customer tenure
        # This would come from customer creation date
        years = customer_profile.get('years_customer', 1)
        tenure_bonus = min(years * 3, 15)
        score += tenure_bonus
        factors.append((f"Customer for {years} years", +tenure_bonus))
        
        # Factor 3: Days until renewal
        days_until = policy_details.get('days_until_renewal', 30)
        if days_until <= 3:
            score -= 20
            factors.append(("Very urgent - 3 days or less", -20))
        elif days_until <= 7:
            score -= 10
            factors.append(("Urgent - within a week", -10))
        
        # Factor 4: Recent interactions
        recent_interactions = len([
            i for i in interaction_history 
            if i.get('days_ago', 999) <= 30
        ])
        if recent_interactions > 0:
            interaction_bonus = min(recent_interactions * 5, 10)
            score += interaction_bonus
            factors.append(("Recent interactions", +interaction_bonus))
        
        # Factor 5: Previous renewals
        renewals = customer_profile.get('previous_renewals', 0)
        if renewals >= 3:
            score += 10
            factors.append(("Multiple previous renewals", +10))
        
        # Clamp score
        score = max(0, min(100, score))
        
        return {
            "retention_probability": round(score, 1),
            "risk_level": self._get_risk_level(score),
            "factors": factors,
            "recommended_strategy": self._get_strategy_for_score(score)
        }
    
    def _build_customer_context(
        self,
        profile: Dict[str, Any],
        policy: Dict[str, Any],
        engagement: Dict[str, Any]
    ) -> str:
        """Build context string for message generation."""
        return f"""
Customer Profile:
- Name: {profile.get('name', 'Valued Customer')}
- Customer Since: {profile.get('customer_since', 'Unknown')}
- Preferred Channel: {profile.get('preferred_channel', 'email')}

Policy Details:
- Policy Type: {policy.get('policy_type')}
- Coverage: {policy.get('coverage_type')}
- Premium: ${policy.get('premium_amount', 0):,.2f}
- Renewal Date: {policy.get('renewal_date')}
- Days Until Renewal: {policy.get('days_until_renewal')}

Engagement:
- Engagement Score: {engagement.get('score', 50)}/100
- Last Interaction: {engagement.get('last_interaction', 'Unknown')}
- Response Rate: {engagement.get('response_rate', 'Unknown')}
"""
    
    def _determine_strategy(self, engagement: Dict[str, Any]) -> str:
        """Determine retention strategy based on engagement."""
        score = engagement.get('score', 50)
        
        if score >= 70:
            return "appreciation_focused"
        elif score >= 50:
            return "value_reminder"
        elif score >= 30:
            return "re_engagement"
        else:
            return "win_back"
    
    def _calculate_urgency(self, policy: Dict[str, Any]) -> str:
        """Calculate urgency level based on renewal date."""
        days = policy.get('days_until_renewal', 30)
        
        if days <= 1:
            return "critical"
        elif days <= 3:
            return "very_high"
        elif days <= 7:
            return "high"
        elif days <= 15:
            return "medium"
        else:
            return "low"
    
    def _calculate_personalization(self, profile: Dict[str, Any]) -> float:
        """Calculate personalization score based on available data."""
        score = 0.5
        
        if profile.get('name'):
            score += 0.1
        if profile.get('customer_since'):
            score += 0.1
        if profile.get('preferred_channel'):
            score += 0.1
        if profile.get('previous_interactions'):
            score += 0.2
        
        return min(score, 1.0)
    
    def _classify_objection(self, objection: str) -> str:
        """Classify the type of objection."""
        obj_lower = objection.lower()
        
        if any(w in obj_lower for w in ['expensive', 'cost', 'price', 'afford', 'money']):
            return "price_concern"
        elif any(w in obj_lower for w in ['coverage', 'cover', 'benefit', 'include']):
            return "coverage_concern"
        elif any(w in obj_lower for w in ['service', 'support', 'help', 'response']):
            return "service_concern"
        elif any(w in obj_lower for w in ['competitor', 'other company', 'better offer']):
            return "competitive_offer"
        elif any(w in obj_lower for w in ['need', 'necessary', 'want', 'use']):
            return "value_concern"
        else:
            return "general_concern"
    
    def _recommend_action(self, objection: str) -> str:
        """Recommend action based on objection type."""
        obj_type = self._classify_objection(objection)
        
        actions = {
            "price_concern": "offer_payment_plan_or_coverage_adjustment",
            "coverage_concern": "schedule_coverage_review",
            "service_concern": "escalate_to_service_manager",
            "competitive_offer": "request_competitor_quote_match_review",
            "value_concern": "provide_value_demonstration",
            "general_concern": "continue_conversation"
        }
        
        return actions.get(obj_type, "continue_conversation")
    
    def _get_risk_level(self, score: float) -> str:
        """Get risk level from score."""
        if score >= 70:
            return "low"
        elif score >= 50:
            return "medium"
        elif score >= 30:
            return "high"
        else:
            return "critical"
    
    def _get_strategy_for_score(self, score: float) -> str:
        """Get recommended strategy based on retention probability."""
        if score >= 70:
            return "standard_renewal_process"
        elif score >= 50:
            return "proactive_outreach"
        elif score >= 30:
            return "intensive_retention_campaign"
        else:
            return "executive_intervention"
    
    def _fallback_message(
        self,
        profile: Dict[str, Any],
        policy: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate fallback message if AI fails."""
        name = profile.get('name', 'Valued Customer')
        
        return {
            "message": f"""Dear {name},

We noticed your policy is coming up for renewal and wanted to reach out personally. Your coverage is important to us, and we're here to ensure you have the protection you need.

If you have any questions about your renewal or would like to discuss your coverage options, please don't hesitate to contact us. We're always happy to help!

Thank you for being a valued customer.""",
            "strategy": "standard",
            "urgency": self._calculate_urgency(policy),
            "personalization_score": 0.3
        }
