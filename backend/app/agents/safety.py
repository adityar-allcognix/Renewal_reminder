"""
Safety Guardrails - Ensure AI responses are safe and compliant
"""

import re
from typing import Dict, Any, List, Optional, Tuple
import structlog

logger = structlog.get_logger()


class SafetyGuardrails:
    """
    Safety guardrails for AI agent responses.
    
    Ensures responses:
    - Don't contain hallucinated policy information
    - Don't make unauthorized promises
    - Don't reveal sensitive information
    - Stay within allowed topics
    """
    
    # Topics the AI should NOT discuss
    BLOCKED_TOPICS = [
        "legal advice",
        "medical advice", 
        "investment advice",
        "competitor pricing",
        "internal company policies",
        "employee information"
    ]
    
    # Patterns that indicate hallucination risk
    HALLUCINATION_PATTERNS = [
        r"your policy covers .* including.*",  # Overly specific claims
        r"you are guaranteed.*",
        r"we promise.*",
        r"100% coverage.*",
        r"no deductible.*",
        r"unlimited.*coverage"
    ]
    
    # Sensitive data patterns to redact
    SENSITIVE_PATTERNS = [
        (r"\b\d{3}-\d{2}-\d{4}\b", "[SSN REDACTED]"),  # SSN
        (r"\b\d{16}\b", "[CARD REDACTED]"),  # Credit card
        (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "[EMAIL]"),  # Email in responses
    ]
    
    @classmethod
    def validate_response(
        cls,
        response: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, str, List[str]]:
        """
        Validate an AI response for safety.
        
        Args:
            response: AI-generated response
            context: Optional context about the query
            
        Returns:
            Tuple of (is_valid, sanitized_response, warnings)
        """
        warnings = []
        sanitized = response
        
        # Check for blocked topics
        for topic in cls.BLOCKED_TOPICS:
            if topic.lower() in response.lower():
                warnings.append(f"Response may contain blocked topic: {topic}")
        
        # Check for hallucination patterns
        for pattern in cls.HALLUCINATION_PATTERNS:
            if re.search(pattern, response, re.IGNORECASE):
                warnings.append(f"Potential hallucination detected: {pattern}")
        
        # Redact sensitive information
        for pattern, replacement in cls.SENSITIVE_PATTERNS:
            if re.search(pattern, sanitized):
                sanitized = re.sub(pattern, replacement, sanitized)
                warnings.append(f"Sensitive data redacted")
        
        # Check response length (too short might indicate issue)
        if len(response) < 20:
            warnings.append("Response unusually short")
        
        # Response is valid if no critical warnings
        critical_warnings = [w for w in warnings if "hallucination" in w.lower()]
        is_valid = len(critical_warnings) == 0
        
        return is_valid, sanitized, warnings
    
    @classmethod
    def validate_tool_call(
        cls,
        tool_name: str,
        arguments: Dict[str, Any],
        customer_id: str
    ) -> Tuple[bool, str]:
        """
        Validate a tool call before execution.
        
        Args:
            tool_name: Name of the tool being called
            arguments: Tool arguments
            customer_id: ID of the customer making the request
            
        Returns:
            Tuple of (is_allowed, reason)
        """
        # Ensure customer can only access their own data
        if "customer_id" in arguments:
            if arguments["customer_id"] != customer_id:
                return False, "Cannot access another customer's data"
        
        # Validate specific tools
        sensitive_tools = [
            "update_policy_beneficiaries",
            "initiate_renewal",
            "update_customer_contact"
        ]
        
        if tool_name in sensitive_tools:
            # These tools need extra validation
            if not arguments:
                return False, "Sensitive tool requires arguments"
        
        # Block certain tool combinations
        if tool_name == "update_policy_beneficiaries":
            beneficiaries = arguments.get("beneficiaries", [])
            for b in beneficiaries:
                percentage = b.get("percentage", 0)
                if percentage < 0 or percentage > 100:
                    return False, "Invalid beneficiary percentage"
        
        return True, "Tool call allowed"


class ComplianceFilter:
    """
    Compliance filter for insurance-specific regulations.
    
    Ensures AI responses comply with:
    - Insurance regulations
    - Privacy requirements
    - Disclosure requirements
    """
    
    # Required disclosures for certain topics
    REQUIRED_DISCLOSURES = {
        "coverage": "Coverage details are subject to the terms and conditions of your specific policy. Please review your policy documents for complete information.",
        "claims": "Claim approval is subject to policy terms and investigation. Past claim results do not guarantee future outcomes.",
        "pricing": "Quoted amounts are estimates. Final pricing may vary based on underwriting.",
        "cancellation": "Cancellation may be subject to fees and coverage gaps. Consult with an agent before cancelling."
    }
    
    # Topics that require human handoff
    HUMAN_HANDOFF_TRIGGERS = [
        "lawsuit",
        "sue",
        "lawyer",
        "attorney",
        "discrimination",
        "fraud",
        "complaint to regulator",
        "insurance commissioner"
    ]
    
    @classmethod
    def add_required_disclosures(
        cls,
        response: str,
        topics: List[str]
    ) -> str:
        """
        Add required disclosures to a response based on topics discussed.
        
        Args:
            response: Original response
            topics: List of topics in the response
            
        Returns:
            Response with required disclosures appended
        """
        disclosures_to_add = []
        
        for topic in topics:
            if topic in cls.REQUIRED_DISCLOSURES:
                disclosures_to_add.append(cls.REQUIRED_DISCLOSURES[topic])
        
        if disclosures_to_add:
            disclosure_text = "\n\n---\n_" + " ".join(disclosures_to_add) + "_"
            return response + disclosure_text
        
        return response
    
    @classmethod
    def check_handoff_required(cls, message: str) -> Tuple[bool, Optional[str]]:
        """
        Check if a message requires human handoff.
        
        Args:
            message: Customer message
            
        Returns:
            Tuple of (handoff_required, reason)
        """
        message_lower = message.lower()
        
        for trigger in cls.HUMAN_HANDOFF_TRIGGERS:
            if trigger in message_lower:
                return True, f"Message contains sensitive topic: {trigger}"
        
        return False, None
    
    @classmethod
    def validate_policy_modification(
        cls,
        modification_type: str,
        current_coverage: Dict[str, Any],
        proposed_changes: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """
        Validate a policy modification request.
        
        Args:
            modification_type: Type of modification
            current_coverage: Current coverage details
            proposed_changes: Proposed changes
            
        Returns:
            Tuple of (is_allowed, reason)
        """
        # Check for significant coverage reductions
        if modification_type == "coverage_reduction":
            current_amount = current_coverage.get("coverage_amount", 0)
            new_amount = proposed_changes.get("coverage_amount", current_amount)
            
            if new_amount < current_amount * 0.5:
                return False, "Significant coverage reduction requires agent review"
        
        # Check for beneficiary changes
        if modification_type == "beneficiary_change":
            # Beneficiary changes should be verified
            return True, "Beneficiary change allowed - verification recommended"
        
        return True, "Modification allowed"


def apply_guardrails(
    response: str,
    tool_calls: List[Dict[str, Any]] = None,
    customer_id: str = None,
    detected_topics: List[str] = None
) -> Dict[str, Any]:
    """
    Apply all guardrails to a response.
    
    Args:
        response: AI response
        tool_calls: List of tool calls made
        customer_id: Customer ID
        detected_topics: Topics detected in conversation
        
    Returns:
        Dict with validated response and metadata
    """
    result = {
        "original_response": response,
        "validated_response": response,
        "is_safe": True,
        "warnings": [],
        "disclosures_added": False,
        "requires_handoff": False
    }
    
    # Apply safety guardrails
    is_valid, sanitized, warnings = SafetyGuardrails.validate_response(response)
    result["validated_response"] = sanitized
    result["warnings"].extend(warnings)
    result["is_safe"] = is_valid
    
    # Check for human handoff
    handoff_required, reason = ComplianceFilter.check_handoff_required(response)
    if handoff_required:
        result["requires_handoff"] = True
        result["handoff_reason"] = reason
    
    # Add required disclosures
    if detected_topics:
        result["validated_response"] = ComplianceFilter.add_required_disclosures(
            result["validated_response"],
            detected_topics
        )
        result["disclosures_added"] = True
    
    # Validate tool calls
    if tool_calls and customer_id:
        for tool_call in tool_calls:
            is_allowed, reason = SafetyGuardrails.validate_tool_call(
                tool_call.get("name", ""),
                tool_call.get("arguments", {}),
                customer_id
            )
            if not is_allowed:
                result["warnings"].append(f"Tool call blocked: {reason}")
                result["is_safe"] = False
    
    return result
