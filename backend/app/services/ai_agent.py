"""
AI Agent Service - Main orchestrator for customer queries
Uses OpenAI for LLM inference with tool-calling capabilities
"""

import json
from typing import Dict, Any, Optional, List
from uuid import UUID
from datetime import date, timedelta
import structlog

from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models import Customer, Policy, PolicyStatus, PolicyDocument
from app.services.rag import RAGService

logger = structlog.get_logger()

# Initialize OpenAI client
client = AsyncOpenAI(
    api_key=settings.ai_api_key,
    base_url=settings.AI_MODEL_ENDPOINT if "openai.com" not in settings.AI_MODEL_ENDPOINT else None,
)

# Define tools for the AI agent
AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_policy_details",
            "description": "Get details of a specific policy by policy number or policy ID. Use this when the customer asks about their policy details, coverage, or premium.",
            "parameters": {
                "type": "object",
                "properties": {
                    "policy_number": {
                        "type": "string",
                        "description": "The policy number to look up"
                    },
                    "policy_id": {
                        "type": "string",
                        "description": "The UUID of the policy"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_customer_policies",
            "description": "Get all policies belonging to a customer. Use this to see all policies a customer has.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string",
                        "description": "The UUID of the customer"
                    },
                    "status": {
                        "type": "string",
                        "enum": ["active", "pending_renewal", "renewed", "lapsed", "cancelled"],
                        "description": "Filter by policy status"
                    }
                },
                "required": ["customer_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_renewal_amount",
            "description": "Calculate the renewal premium amount for a policy. Use when customer asks how much they need to pay for renewal.",
            "parameters": {
                "type": "object",
                "properties": {
                    "policy_number": {
                        "type": "string",
                        "description": "The policy number"
                    }
                },
                "required": ["policy_number"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_renewal_date",
            "description": "Get the renewal date for a policy. Use when customer asks when their policy is due for renewal.",
            "parameters": {
                "type": "object",
                "properties": {
                    "policy_number": {
                        "type": "string",
                        "description": "The policy number"
                    }
                },
                "required": ["policy_number"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_customer_contact",
            "description": "Update customer contact information like phone number, email, or address. Use when customer wants to update their contact details.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string",
                        "description": "The UUID of the customer"
                    },
                    "phone": {
                        "type": "string",
                        "description": "New phone number"
                    },
                    "email": {
                        "type": "string",
                        "description": "New email address"
                    },
                    "address_line1": {
                        "type": "string",
                        "description": "New address line 1"
                    },
                    "address_line2": {
                        "type": "string",
                        "description": "New address line 2"
                    },
                    "city": {
                        "type": "string",
                        "description": "New city"
                    },
                    "state": {
                        "type": "string",
                        "description": "New state"
                    },
                    "postal_code": {
                        "type": "string",
                        "description": "New postal code"
                    }
                },
                "required": ["customer_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "initiate_renewal",
            "description": "Initiate the renewal process for a policy. Use when customer confirms they want to renew.",
            "parameters": {
                "type": "object",
                "properties": {
                    "policy_number": {
                        "type": "string",
                        "description": "The policy number to renew"
                    }
                },
                "required": ["policy_number"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_policy_documents",
            "description": "Search policy documents for information about coverage, benefits, terms, and conditions. Use when customer asks about policy benefits, coverage details, or terms.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query about policy information"
                    },
                    "policy_type": {
                        "type": "string",
                        "enum": ["auto", "home", "life", "health"],
                        "description": "Type of policy to search documents for"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_policy_benefits",
            "description": "Get the benefits and coverage details for a specific policy type.",
            "parameters": {
                "type": "object",
                "properties": {
                    "policy_number": {
                        "type": "string",
                        "description": "The policy number"
                    }
                },
                "required": ["policy_number"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_policy_beneficiaries",
            "description": "Update the beneficiaries on a policy. Use when customer wants to change beneficiaries.",
            "parameters": {
                "type": "object",
                "properties": {
                    "policy_number": {
                        "type": "string",
                        "description": "The policy number"
                    },
                    "beneficiaries": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "relationship": {"type": "string"},
                                "percentage": {"type": "number"}
                            }
                        },
                        "description": "List of beneficiaries with name, relationship, and percentage"
                    }
                },
                "required": ["policy_number", "beneficiaries"]
            }
        }
    }
]

# System prompt for the renewal assistant
SYSTEM_PROMPT = """You are a helpful and professional insurance renewal assistant. Your role is to help customers with:

1. **Policy Renewals**: Answer questions about renewal dates, amounts, and process
2. **Policy Information**: Provide details about coverage, benefits, and terms
3. **Account Updates**: Help customers update their contact information or beneficiaries
4. **General Inquiries**: Answer questions about their policies using available information

**Guidelines**:
- Always be polite, professional, and helpful
- Use the available tools to fetch accurate information - NEVER make up policy details
- If you don't have information, say so and offer to help in another way
- For sensitive changes (beneficiary updates, cancellations), confirm details before proceeding
- Keep responses concise but informative
- If a customer wants to renew, guide them through the process step by step

**Important**:
- You can ONLY access information for the customer you're chatting with
- Never disclose information about other customers
- For payment processing, direct customers to the secure payment portal
- Always verify policy numbers before making changes
"""


async def execute_tool(
    tool_name: str, 
    arguments: Dict[str, Any], 
    customer_id: UUID,
    db: AsyncSession
) -> Dict[str, Any]:
    """Execute a tool call and return the result."""
    logger.info("Executing tool", tool=tool_name, args=arguments)
    
    if tool_name == "get_policy_details":
        return await tool_get_policy_details(arguments, customer_id, db)
    elif tool_name == "get_customer_policies":
        return await tool_get_customer_policies(arguments, customer_id, db)
    elif tool_name == "calculate_renewal_amount":
        return await tool_calculate_renewal_amount(arguments, customer_id, db)
    elif tool_name == "get_renewal_date":
        return await tool_get_renewal_date(arguments, customer_id, db)
    elif tool_name == "update_customer_contact":
        return await tool_update_customer_contact(arguments, customer_id, db)
    elif tool_name == "initiate_renewal":
        return await tool_initiate_renewal(arguments, customer_id, db)
    elif tool_name == "search_policy_documents":
        return await tool_search_policy_documents(arguments, db)
    elif tool_name == "get_policy_benefits":
        return await tool_get_policy_benefits(arguments, customer_id, db)
    elif tool_name == "update_policy_beneficiaries":
        return await tool_update_policy_beneficiaries(arguments, customer_id, db)
    else:
        return {"error": f"Unknown tool: {tool_name}"}


async def tool_get_policy_details(
    args: Dict[str, Any], 
    customer_id: UUID, 
    db: AsyncSession
) -> Dict[str, Any]:
    """Get details of a specific policy."""
    policy_number = args.get("policy_number")
    policy_id = args.get("policy_id")
    
    query = select(Policy).options(selectinload(Policy.customer))
    
    if policy_number:
        query = query.where(Policy.policy_number == policy_number)
    elif policy_id:
        query = query.where(Policy.id == policy_id)
    else:
        return {"error": "Either policy_number or policy_id is required"}
    
    # Ensure the policy belongs to the customer
    query = query.where(Policy.customer_id == customer_id)
    
    result = await db.execute(query)
    policy = result.scalar_one_or_none()
    
    if not policy:
        return {"error": "Policy not found or does not belong to this customer"}
    
    days_until_renewal = (policy.renewal_date - date.today()).days
    
    return {
        "policy_number": policy.policy_number,
        "policy_type": policy.policy_type,
        "coverage_type": policy.coverage_type,
        "coverage_amount": float(policy.coverage_amount),
        "premium_amount": float(policy.premium_amount),
        "payment_frequency": policy.payment_frequency,
        "start_date": policy.start_date.isoformat(),
        "end_date": policy.end_date.isoformat(),
        "renewal_date": policy.renewal_date.isoformat(),
        "days_until_renewal": days_until_renewal,
        "status": policy.status.value,
        "beneficiaries": policy.beneficiaries or [],
        "add_ons": policy.add_ons or []
    }


async def tool_get_customer_policies(
    args: Dict[str, Any], 
    customer_id: UUID, 
    db: AsyncSession
) -> Dict[str, Any]:
    """Get all policies for a customer."""
    status_filter = args.get("status")
    
    query = select(Policy).where(Policy.customer_id == customer_id)
    
    if status_filter:
        query = query.where(Policy.status == PolicyStatus(status_filter))
    
    result = await db.execute(query)
    policies = result.scalars().all()
    
    return {
        "policies": [
            {
                "policy_number": p.policy_number,
                "policy_type": p.policy_type,
                "coverage_type": p.coverage_type,
                "premium_amount": float(p.premium_amount),
                "renewal_date": p.renewal_date.isoformat(),
                "days_until_renewal": (p.renewal_date - date.today()).days,
                "status": p.status.value
            }
            for p in policies
        ],
        "total_policies": len(policies)
    }


async def tool_calculate_renewal_amount(
    args: Dict[str, Any], 
    customer_id: UUID, 
    db: AsyncSession
) -> Dict[str, Any]:
    """Calculate renewal amount for a policy."""
    policy_number = args.get("policy_number")
    
    query = (
        select(Policy)
        .where(Policy.policy_number == policy_number)
        .where(Policy.customer_id == customer_id)
    )
    
    result = await db.execute(query)
    policy = result.scalar_one_or_none()
    
    if not policy:
        return {"error": "Policy not found"}
    
    # Calculate renewal premium (simple example - can be made more complex)
    base_premium = float(policy.premium_amount)
    
    # Add any adjustments (example: 3% annual increase)
    adjustment_rate = 0.03
    renewal_premium = base_premium * (1 + adjustment_rate)
    
    # Calculate add-on costs
    add_on_costs = sum(
        addon.get("cost", 0) for addon in (policy.add_ons or [])
    )
    
    total_renewal = renewal_premium + add_on_costs
    
    return {
        "policy_number": policy_number,
        "current_premium": base_premium,
        "renewal_premium": round(renewal_premium, 2),
        "add_on_costs": add_on_costs,
        "total_renewal_amount": round(total_renewal, 2),
        "premium_change_percent": adjustment_rate * 100,
        "renewal_date": policy.renewal_date.isoformat(),
        "payment_frequency": policy.payment_frequency,
        "breakdown": {
            "base_premium": round(renewal_premium, 2),
            "add_ons": add_on_costs,
            "taxes_fees": 0  # Can be calculated based on region
        }
    }


async def tool_get_renewal_date(
    args: Dict[str, Any], 
    customer_id: UUID, 
    db: AsyncSession
) -> Dict[str, Any]:
    """Get renewal date for a policy."""
    policy_number = args.get("policy_number")
    
    query = (
        select(Policy)
        .where(Policy.policy_number == policy_number)
        .where(Policy.customer_id == customer_id)
    )
    
    result = await db.execute(query)
    policy = result.scalar_one_or_none()
    
    if not policy:
        return {"error": "Policy not found"}
    
    days_until = (policy.renewal_date - date.today()).days
    
    return {
        "policy_number": policy_number,
        "renewal_date": policy.renewal_date.isoformat(),
        "days_until_renewal": days_until,
        "is_overdue": days_until < 0,
        "is_urgent": 0 <= days_until <= 7,
        "status": policy.status.value
    }


async def tool_update_customer_contact(
    args: Dict[str, Any], 
    customer_id: UUID, 
    db: AsyncSession
) -> Dict[str, Any]:
    """Update customer contact information."""
    # Ensure we're updating the correct customer
    if str(customer_id) != args.get("customer_id"):
        return {"error": "Cannot update another customer's information"}
    
    customer = await db.get(Customer, customer_id)
    if not customer:
        return {"error": "Customer not found"}
    
    updates = {}
    for field in ["phone", "email", "address_line1", "address_line2", "city", "state", "postal_code"]:
        if field in args and args[field]:
            setattr(customer, field, args[field])
            updates[field] = args[field]
    
    if updates:
        await db.commit()
        return {
            "success": True,
            "message": "Contact information updated successfully",
            "updated_fields": updates
        }
    else:
        return {"error": "No fields to update provided"}


async def tool_initiate_renewal(
    args: Dict[str, Any], 
    customer_id: UUID, 
    db: AsyncSession
) -> Dict[str, Any]:
    """Initiate the renewal process for a policy."""
    policy_number = args.get("policy_number")
    
    query = (
        select(Policy)
        .where(Policy.policy_number == policy_number)
        .where(Policy.customer_id == customer_id)
    )
    
    result = await db.execute(query)
    policy = result.scalar_one_or_none()
    
    if not policy:
        return {"error": "Policy not found"}
    
    if policy.status not in [PolicyStatus.ACTIVE, PolicyStatus.PENDING_RENEWAL]:
        return {"error": f"Cannot renew policy in {policy.status.value} status"}
    
    # Update status to pending renewal
    policy.status = PolicyStatus.PENDING_RENEWAL
    await db.commit()
    
    # In production, this would trigger actual renewal workflow
    return {
        "success": True,
        "message": "Renewal process initiated",
        "policy_number": policy_number,
        "renewal_amount": float(policy.premium_amount) * 1.03,  # Example calculation
        "renewal_date": policy.renewal_date.isoformat(),
        "next_steps": [
            "Review your renewal quote",
            "Complete payment through secure portal",
            "Receive confirmation email within 24 hours"
        ],
        "payment_link": f"/payment/renew/{policy_number}"  # Example link
    }


async def tool_search_policy_documents(
    args: Dict[str, Any], 
    db: AsyncSession
) -> Dict[str, Any]:
    """Search policy documents using RAG."""
    query = args.get("query")
    policy_type = args.get("policy_type")
    
    rag_service = RAGService(db)
    results = await rag_service.search(query, policy_type=policy_type)
    
    if not results:
        return {
            "found": False,
            "message": "No relevant information found in policy documents."
        }
    
    return {
        "found": True,
        "results": results,
        "sources": [r.get("document_name") for r in results]
    }


async def tool_get_policy_benefits(
    args: Dict[str, Any], 
    customer_id: UUID, 
    db: AsyncSession
) -> Dict[str, Any]:
    """Get benefits for a specific policy."""
    policy_number = args.get("policy_number")
    
    query = (
        select(Policy)
        .where(Policy.policy_number == policy_number)
        .where(Policy.customer_id == customer_id)
    )
    
    result = await db.execute(query)
    policy = result.scalar_one_or_none()
    
    if not policy:
        return {"error": "Policy not found"}
    
    # Get benefits from policy metadata and search documents
    rag_service = RAGService(db)
    doc_results = await rag_service.search(
        f"{policy.policy_type} {policy.coverage_type} benefits coverage",
        policy_type=policy.policy_type
    )
    
    return {
        "policy_number": policy_number,
        "policy_type": policy.policy_type,
        "coverage_type": policy.coverage_type,
        "coverage_amount": float(policy.coverage_amount),
        "add_ons": policy.add_ons or [],
        "document_info": doc_results[:3] if doc_results else []
    }


async def tool_update_policy_beneficiaries(
    args: Dict[str, Any], 
    customer_id: UUID, 
    db: AsyncSession
) -> Dict[str, Any]:
    """Update beneficiaries on a policy."""
    policy_number = args.get("policy_number")
    beneficiaries = args.get("beneficiaries", [])
    
    query = (
        select(Policy)
        .where(Policy.policy_number == policy_number)
        .where(Policy.customer_id == customer_id)
    )
    
    result = await db.execute(query)
    policy = result.scalar_one_or_none()
    
    if not policy:
        return {"error": "Policy not found"}
    
    # Validate beneficiary percentages
    total_percentage = sum(b.get("percentage", 0) for b in beneficiaries)
    if total_percentage != 100:
        return {"error": f"Beneficiary percentages must total 100% (currently {total_percentage}%)"}
    
    # Update beneficiaries
    policy.beneficiaries = beneficiaries
    await db.commit()
    
    return {
        "success": True,
        "message": "Beneficiaries updated successfully",
        "policy_number": policy_number,
        "beneficiaries": beneficiaries
    }


async def process_customer_query(
    customer_id: UUID,
    session_id: str,
    query: str,
    db: AsyncSession
) -> Dict[str, Any]:
    """
    Process a customer query through the AI agent.
    
    Args:
        customer_id: UUID of the customer
        session_id: Chat session ID
        query: Customer's message
        db: Database session
        
    Returns:
        Dict with response, intent, tools_used, and context
    """
    logger.info("Processing customer query", 
                customer_id=str(customer_id), 
                session_id=session_id)
    
    # Get customer info for context
    customer = await db.get(Customer, customer_id)
    if not customer:
        return {
            "response": "I'm sorry, but I couldn't find your account. Please contact support.",
            "intent": "error",
            "tools_used": [],
            "context": {}
        }
    
    # Build conversation messages
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "system", 
            "content": f"Current customer: {customer.full_name} (ID: {customer_id})"
        },
        {"role": "user", "content": query}
    ]
    
    tools_used = []
    max_iterations = 5  # Prevent infinite loops
    
    try:
        for iteration in range(max_iterations):
            # Call the AI model
            response = await client.chat.completions.create(
                model=settings.AI_MODEL_ID,
                messages=messages,
                tools=AGENT_TOOLS,
                tool_choice="auto",
                temperature=0.7,
                max_tokens=1000
            )
            
            assistant_message = response.choices[0].message
            
            # Check if there are tool calls
            if assistant_message.tool_calls:
                messages.append(assistant_message.model_dump())
                
                # Execute each tool call
                for tool_call in assistant_message.tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)
                    
                    # Execute the tool
                    tool_result = await execute_tool(
                        tool_name, tool_args, customer_id, db
                    )
                    
                    tools_used.append(tool_name)
                    
                    # Add tool result to messages
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(tool_result)
                    })
            else:
                # No tool calls, return the response
                return {
                    "response": assistant_message.content,
                    "intent": detect_intent(query),
                    "tools_used": tools_used,
                    "context": {"iteration_count": iteration + 1}
                }
        
        # Max iterations reached
        return {
            "response": "I apologize, but I'm having trouble processing your request. Please try again or contact support.",
            "intent": "error",
            "tools_used": tools_used,
            "context": {"max_iterations_reached": True}
        }
        
    except Exception as e:
        logger.error("Error processing query", error=str(e))
        return {
            "response": "I'm sorry, but I encountered an error. Please try again later or contact support.",
            "intent": "error",
            "tools_used": tools_used,
            "context": {"error": str(e)}
        }


def detect_intent(query: str) -> str:
    """Simple intent detection based on keywords."""
    query_lower = query.lower()
    
    if any(word in query_lower for word in ["renew", "renewal", "extend"]):
        return "renewal_inquiry"
    elif any(word in query_lower for word in ["pay", "payment", "amount", "cost", "price", "premium"]):
        return "payment_inquiry"
    elif any(word in query_lower for word in ["due", "date", "when", "expire"]):
        return "date_inquiry"
    elif any(word in query_lower for word in ["coverage", "benefit", "cover", "included"]):
        return "coverage_inquiry"
    elif any(word in query_lower for word in ["update", "change", "modify", "address", "phone"]):
        return "update_request"
    elif any(word in query_lower for word in ["beneficiary", "nominee"]):
        return "beneficiary_update"
    elif any(word in query_lower for word in ["cancel", "terminate", "stop"]):
        return "cancellation_inquiry"
    else:
        return "general_inquiry"
