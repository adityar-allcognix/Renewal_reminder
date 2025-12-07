"""
Chat API Routes - AI Agent Interface
"""

import time
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Customer, InteractionLog
from app.schemas import ChatMessage, ChatResponse

router = APIRouter()


@router.post("/message", response_model=ChatResponse)
async def send_chat_message(
    message: ChatMessage,
    db: AsyncSession = Depends(get_db)
):
    """Process a chat message through the AI agent."""
    start_time = time.time()
    
    # Verify customer exists
    customer = await db.get(Customer, message.customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    # Import AI agent service
    from app.services.ai_agent import process_customer_query
    
    # Process message through AI agent
    result = await process_customer_query(
        customer_id=message.customer_id,
        session_id=message.session_id,
        query=message.message,
        db=db
    )
    
    response_time_ms = int((time.time() - start_time) * 1000)
    
    # Log interaction
    interaction = InteractionLog(
        customer_id=message.customer_id,
        session_id=message.session_id,
        user_query=message.message,
        agent_response=result["response"],
        detected_intent=result.get("intent"),
        tools_used=result.get("tools_used", []),
        context=result.get("context", {}),
        response_time_ms=response_time_ms
    )
    db.add(interaction)
    
    # Update customer's last interaction
    customer.last_interaction_at = datetime.utcnow()
    
    await db.commit()
    
    return ChatResponse(
        session_id=message.session_id,
        response=result["response"],
        tools_used=result.get("tools_used", []),
        context=result.get("context"),
        response_time_ms=response_time_ms
    )


@router.get("/history/{customer_id}/{session_id}")
async def get_chat_history(
    customer_id: UUID,
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get chat history for a session."""
    from sqlalchemy import select
    
    query = (
        select(InteractionLog)
        .where(
            InteractionLog.customer_id == customer_id,
            InteractionLog.session_id == session_id
        )
        .order_by(InteractionLog.created_at)
    )
    
    result = await db.execute(query)
    interactions = result.scalars().all()
    
    return [
        {
            "id": str(i.id),
            "user_query": i.user_query,
            "agent_response": i.agent_response,
            "tools_used": i.tools_used,
            "created_at": i.created_at.isoformat()
        }
        for i in interactions
    ]


@router.websocket("/ws/{customer_id}/{session_id}")
async def websocket_chat(
    websocket: WebSocket,
    customer_id: UUID,
    session_id: str
):
    """WebSocket endpoint for real-time chat."""
    await websocket.accept()
    
    try:
        while True:
            # Receive message
            data = await websocket.receive_json()
            message = data.get("message", "")
            
            if not message:
                continue
            
            # Process through AI agent
            from app.services.ai_agent import process_customer_query
            from app.database import AsyncSessionLocal
            
            async with AsyncSessionLocal() as db:
                start_time = time.time()
                
                result = await process_customer_query(
                    customer_id=customer_id,
                    session_id=session_id,
                    query=message,
                    db=db
                )
                
                response_time_ms = int((time.time() - start_time) * 1000)
                
                # Log interaction
                interaction = InteractionLog(
                    customer_id=customer_id,
                    session_id=session_id,
                    user_query=message,
                    agent_response=result["response"],
                    detected_intent=result.get("intent"),
                    tools_used=result.get("tools_used", []),
                    response_time_ms=response_time_ms
                )
                db.add(interaction)
                await db.commit()
            
            # Send response
            await websocket.send_json({
                "type": "response",
                "response": result["response"],
                "tools_used": result.get("tools_used", []),
                "response_time_ms": response_time_ms
            })
            
    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "error": str(e)
        })
