"""
AI Worker - Background worker for AI agent tasks
"""

import asyncio
import json
import structlog
import redis.asyncio as redis
from typing import Dict, Any

from . import RenewalAgent, QueryAgent, RetentionAgent
from ..config import settings

logger = structlog.get_logger()


class AIWorker:
    """
    Background worker that processes AI agent tasks from Redis queue.
    """
    
    def __init__(self):
        self.redis_client = None
        self.renewal_agent = RenewalAgent(
            model_id=settings.AI_MODEL_ID,
            api_key=settings.GITHUB_TOKEN,
            api_base=settings.AI_MODEL_ENDPOINT
        )
        self.query_agent = QueryAgent(
            model_id=settings.AI_MODEL_ID,
            api_key=settings.GITHUB_TOKEN,
            api_base=settings.AI_MODEL_ENDPOINT
        )
        self.retention_agent = RetentionAgent(
            model_id=settings.AI_MODEL_ID,
            api_key=settings.GITHUB_TOKEN,
            api_base=settings.AI_MODEL_ENDPOINT
        )
    
    async def connect(self):
        """Connect to Redis."""
        self.redis_client = redis.from_url(settings.REDIS_URL)
        logger.info("Connected to Redis")
    
    async def disconnect(self):
        """Disconnect from Redis."""
        if self.redis_client:
            await self.redis_client.close()
    
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process an AI task.
        
        Args:
            task: Task dictionary with type and payload
            
        Returns:
            Task result
        """
        task_type = task.get("type")
        payload = task.get("payload", {})
        
        logger.info("Processing task", task_type=task_type)
        
        try:
            if task_type == "renewal_request":
                return await self.renewal_agent.process_renewal_request(
                    customer_id=payload.get("customer_id"),
                    policy_number=payload.get("policy_number"),
                    policy_details=payload.get("policy_details", {}),
                    customer_message=payload.get("message", "")
                )
            
            elif task_type == "generate_renewal_summary":
                return {
                    "summary": await self.renewal_agent.generate_renewal_summary(
                        policy_details=payload.get("policy_details", {}),
                        renewal_calculation=payload.get("renewal_calculation", {})
                    )
                }
            
            elif task_type == "answer_question":
                return await self.query_agent.answer_question(
                    question=payload.get("question", ""),
                    policy_context=payload.get("policy_context"),
                    rag_results=payload.get("rag_results"),
                    conversation_history=payload.get("history")
                )
            
            elif task_type == "classify_message":
                return await self.query_agent.classify_and_route(
                    message=payload.get("message", "")
                )
            
            elif task_type == "retention_message":
                return await self.retention_agent.generate_retention_message(
                    customer_profile=payload.get("customer_profile", {}),
                    policy_details=payload.get("policy_details", {}),
                    engagement_data=payload.get("engagement_data", {})
                )
            
            elif task_type == "handle_objection":
                return await self.retention_agent.handle_objection(
                    customer_id=payload.get("customer_id", ""),
                    objection=payload.get("objection", ""),
                    customer_context=payload.get("customer_context", {})
                )
            
            elif task_type == "retention_score":
                return await self.retention_agent.score_retention_probability(
                    customer_profile=payload.get("customer_profile", {}),
                    policy_details=payload.get("policy_details", {}),
                    interaction_history=payload.get("interaction_history", [])
                )
            
            else:
                logger.warning("Unknown task type", task_type=task_type)
                return {"error": f"Unknown task type: {task_type}"}
                
        except Exception as e:
            logger.error("Task processing error", error=str(e), task_type=task_type)
            return {"error": str(e)}
    
    async def run(self):
        """Run the worker loop."""
        await self.connect()
        
        queue_name = "ai_tasks"
        logger.info("AI Worker started", queue=queue_name)
        
        while True:
            try:
                # Block and wait for a task
                result = await self.redis_client.blpop(queue_name, timeout=30)
                
                if result:
                    _, task_json = result
                    task = json.loads(task_json)
                    
                    # Process the task
                    task_result = await self.process_task(task)
                    
                    # Store result if callback channel specified
                    callback_channel = task.get("callback_channel")
                    if callback_channel:
                        await self.redis_client.publish(
                            callback_channel,
                            json.dumps(task_result)
                        )
                    
            except asyncio.CancelledError:
                logger.info("Worker shutdown requested")
                break
            except Exception as e:
                logger.error("Worker error", error=str(e))
                await asyncio.sleep(5)  # Wait before retrying
        
        await self.disconnect()


async def main():
    """Main entry point."""
    worker = AIWorker()
    
    try:
        await worker.run()
    except KeyboardInterrupt:
        logger.info("Shutting down AI Worker")


if __name__ == "__main__":
    asyncio.run(main())
