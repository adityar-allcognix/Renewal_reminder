"""
RAG Tasks - Celery tasks for document processing and embedding
"""

import asyncio
import os
from typing import List, Optional
import structlog

from app.celery_app import celery_app
from app.database import AsyncSessionLocal

logger = structlog.get_logger()


def run_async(coro):
    """Helper to run async functions in Celery tasks."""
    loop = asyncio.get_event_loop()
    if loop.is_running():
        return asyncio.ensure_future(coro)
    return loop.run_until_complete(coro)


@celery_app.task(bind=True, max_retries=2)
def process_document(
    self,
    file_path: str,
    document_name: str,
    policy_type: Optional[str] = None
):
    """
    Process a document and add it to the RAG system.
    
    Args:
        file_path: Path to the document file
        document_name: Name to identify the document
        policy_type: Type of policy (auto, home, life, health)
    """
    logger.info("Celery: Processing document", 
               file_path=file_path, 
               document_name=document_name)
    
    async def _process():
        from app.services.rag import RAGService, DocumentProcessor
        
        async with AsyncSessionLocal() as db:
            try:
                # Determine document type
                ext = os.path.splitext(file_path)[1].lower()
                doc_type_map = {
                    '.pdf': 'pdf',
                    '.docx': 'docx',
                    '.doc': 'docx',
                    '.txt': 'txt'
                }
                
                doc_type = doc_type_map.get(ext, 'txt')
                
                # Extract content
                content = await DocumentProcessor.process_file(file_path)
                
                if not content:
                    return {"status": "failed", "error": "No content extracted"}
                
                # Add to RAG
                rag = RAGService(db)
                chunk_ids = await rag.add_document(
                    document_name=document_name,
                    document_type=doc_type,
                    content=content,
                    policy_type=policy_type,
                    metadata={
                        "source_file": file_path,
                        "processed_by": "celery_task"
                    }
                )
                
                return {
                    "status": "success",
                    "document_name": document_name,
                    "chunks_created": len(chunk_ids)
                }
                
            except Exception as e:
                logger.error("Celery: Document processing failed", error=str(e))
                raise
    
    try:
        result = run_async(_process())
        logger.info("Celery: Document processed", **result)
        return result
    except Exception as e:
        logger.error("Celery: Task failed", error=str(e))
        self.retry(exc=e, countdown=120)


@celery_app.task(bind=True)
def process_documents_batch(
    self,
    file_paths: List[str],
    policy_type: Optional[str] = None
):
    """
    Process multiple documents in batch.
    
    Args:
        file_paths: List of file paths to process
        policy_type: Type of policy for all documents
    """
    logger.info("Celery: Processing document batch", count=len(file_paths))
    
    results = []
    for file_path in file_paths:
        doc_name = os.path.basename(file_path)
        result = process_document.delay(file_path, doc_name, policy_type)
        results.append({
            "file": file_path,
            "task_id": result.id
        })
    
    return {
        "status": "queued",
        "documents": len(file_paths),
        "tasks": results
    }


@celery_app.task(bind=True)
def rebuild_embeddings(self, policy_type: Optional[str] = None):
    """
    Rebuild embeddings for all documents (or filtered by policy type).
    Useful when embedding model is updated.
    """
    logger.info("Celery: Rebuilding embeddings", policy_type=policy_type)
    
    async def _rebuild():
        from sqlalchemy import select
        from app.models import PolicyDocument
        from app.services.rag import RAGService
        
        async with AsyncSessionLocal() as db:
            try:
                query = select(PolicyDocument)
                if policy_type:
                    query = query.where(PolicyDocument.policy_type == policy_type)
                
                result = await db.execute(query)
                documents = result.scalars().all()
                
                rag = RAGService(db)
                updated = 0
                
                for doc in documents:
                    # Regenerate embedding
                    new_embedding = await rag.embed_text(doc.content)
                    doc.embedding = new_embedding
                    updated += 1
                
                await db.commit()
                return updated
                
            except Exception as e:
                logger.error("Celery: Embedding rebuild failed", error=str(e))
                await db.rollback()
                raise
    
    result = run_async(_rebuild())
    logger.info("Celery: Embeddings rebuilt", updated=result)
    return {"status": "success", "documents_updated": result}


@celery_app.task(bind=True)
def delete_document_task(self, document_name: str):
    """
    Delete a document from the RAG system.
    """
    logger.info("Celery: Deleting document", document_name=document_name)
    
    async def _delete():
        from app.services.rag import RAGService
        
        async with AsyncSessionLocal() as db:
            rag = RAGService(db)
            count = await rag.delete_document(document_name)
            return count
    
    result = run_async(_delete())
    logger.info("Celery: Document deleted", chunks_deleted=result)
    return {"status": "success", "chunks_deleted": result}


@celery_app.task(bind=True)
def search_documents_task(
    self,
    query: str,
    policy_type: Optional[str] = None,
    top_k: int = 5
):
    """
    Search documents asynchronously (for batch operations).
    """
    logger.info("Celery: Searching documents", query=query[:50])
    
    async def _search():
        from app.services.rag import RAGService
        
        async with AsyncSessionLocal() as db:
            rag = RAGService(db)
            results = await rag.search(query, policy_type=policy_type, top_k=top_k)
            return results
    
    results = run_async(_search())
    return {"status": "success", "results": results}
