"""
Query Agent - Handles customer questions using RAG and tool-calling
"""

from typing import Dict, Any, Optional, List
import structlog

from openai import AsyncOpenAI

logger = structlog.get_logger()


class QueryAgent:
    """
    AI Agent specialized in answering customer questions.
    
    Uses RAG (Retrieval-Augmented Generation) to provide accurate,
    document-grounded responses about policy details, coverage, and benefits.
    """
    
    SYSTEM_PROMPT = """You are a knowledgeable Insurance Customer Service AI Agent.
Your role is to answer customer questions accurately and helpfully.

Guidelines:
1. Always base your answers on the provided policy documents and data
2. If you're not sure about something, say so - never make up information
3. Be clear and concise in your explanations
4. Use simple language, avoiding jargon when possible
5. If a question is outside your knowledge, recommend contacting support

For policy-specific questions:
- Refer to the customer's actual policy details when available
- Quote relevant sections from policy documents
- Explain coverage limits and exclusions clearly

For general insurance questions:
- Provide helpful educational information
- Always note that specific coverage depends on individual policies
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
    
    async def answer_question(
        self,
        question: str,
        policy_context: Optional[Dict[str, Any]] = None,
        rag_results: Optional[List[Dict[str, Any]]] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Answer a customer question using available context.
        
        Args:
            question: Customer's question
            policy_context: Customer's policy details (if available)
            rag_results: Relevant document chunks from RAG search
            conversation_history: Previous messages in the conversation
            
        Returns:
            Response with answer and sources
        """
        messages = [{"role": "system", "content": self.SYSTEM_PROMPT}]
        
        # Add policy context if available
        if policy_context:
            context_msg = self._format_policy_context(policy_context)
            messages.append({
                "role": "system",
                "content": f"Customer's Policy Information:\n{context_msg}"
            })
        
        # Add RAG results if available
        if rag_results:
            rag_context = self._format_rag_results(rag_results)
            messages.append({
                "role": "system",
                "content": f"Relevant Policy Document Information:\n{rag_context}"
            })
        
        # Add conversation history
        if conversation_history:
            for msg in conversation_history[-6:]:  # Last 6 messages
                messages.append(msg)
        
        # Add the current question
        messages.append({"role": "user", "content": question})
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model_id,
                messages=messages,
                temperature=0.5,
                max_tokens=600
            )
            
            answer = response.choices[0].message.content
            
            # Extract sources if RAG was used
            sources = []
            if rag_results:
                sources = [
                    {
                        "document": r.get("document_name"),
                        "relevance": r.get("relevance_score")
                    }
                    for r in rag_results[:3]
                ]
            
            return {
                "answer": answer,
                "sources": sources,
                "intent": self._classify_intent(question),
                "confidence": "high" if rag_results else "medium"
            }
            
        except Exception as e:
            logger.error("Query agent error", error=str(e))
            return {
                "answer": "I apologize, but I'm having trouble finding that information. Please try rephrasing your question or contact our support team.",
                "sources": [],
                "intent": "unknown",
                "confidence": "low",
                "error": str(e)
            }
    
    async def classify_and_route(
        self,
        message: str
    ) -> Dict[str, str]:
        """
        Classify a message and determine routing.
        
        Args:
            message: Customer's message
            
        Returns:
            Classification with suggested routing
        """
        prompt = f"""Classify this customer message and suggest routing:

Message: "{message}"

Classify into one of:
- renewal: Related to policy renewal
- payment: Related to payment or billing
- coverage: Questions about coverage/benefits
- claims: Related to filing/checking claims
- account: Account updates (address, phone, etc.)
- complaint: Customer complaint or issue
- general: General inquiry

Respond with JSON: {{"category": "...", "confidence": 0.0-1.0, "route_to": "..."}}"""

        messages = [
            {"role": "system", "content": "You are a message classifier. Respond only with JSON."},
            {"role": "user", "content": prompt}
        ]
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model_id,
                messages=messages,
                temperature=0.1,
                max_tokens=100
            )
            
            import json
            result = json.loads(response.choices[0].message.content)
            return result
            
        except Exception as e:
            logger.error("Classification error", error=str(e))
            return {
                "category": "general",
                "confidence": 0.5,
                "route_to": "query_agent"
            }
    
    def _format_policy_context(self, policy: Dict[str, Any]) -> str:
        """Format policy details for context."""
        return f"""
- Policy Number: {policy.get('policy_number', 'N/A')}
- Policy Type: {policy.get('policy_type', 'N/A')}
- Coverage Type: {policy.get('coverage_type', 'N/A')}
- Coverage Amount: ${policy.get('coverage_amount', 0):,.2f}
- Premium: ${policy.get('premium_amount', 0):,.2f}
- Status: {policy.get('status', 'N/A')}
- Renewal Date: {policy.get('renewal_date', 'N/A')}
"""
    
    def _format_rag_results(self, results: List[Dict[str, Any]]) -> str:
        """Format RAG results for context."""
        formatted = []
        for i, r in enumerate(results[:3], 1):
            formatted.append(f"""
[Source {i}: {r.get('document_name', 'Unknown')}]
{r.get('content', '')}
""")
        return "\n".join(formatted)
    
    def _classify_intent(self, question: str) -> str:
        """Simple intent classification."""
        q_lower = question.lower()
        
        intents = {
            "coverage_inquiry": ["cover", "coverage", "include", "exclude", "benefit"],
            "payment_inquiry": ["pay", "payment", "cost", "price", "premium", "amount"],
            "renewal_inquiry": ["renew", "renewal", "expire", "expiring"],
            "claims_inquiry": ["claim", "file", "submit", "accident"],
            "account_inquiry": ["address", "phone", "email", "update", "change"],
            "general_inquiry": ["what", "how", "why", "when", "where", "who"]
        }
        
        for intent, keywords in intents.items():
            if any(kw in q_lower for kw in keywords):
                return intent
        
        return "general_inquiry"
