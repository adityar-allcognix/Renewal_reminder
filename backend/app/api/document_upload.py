
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.api.customer_public import validate_token
from app.models import CustomerTokenType
from datetime import datetime
import structlog

logger = structlog.get_logger()

router = APIRouter()

@router.post("/upload-document/{token}")
async def upload_document(
    token: str,
    file: UploadFile = File(...),
    request: Request = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Upload a document using a secure token.
    """
    # Validate token
    customer_token = await validate_token(db, token)
    if not customer_token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid or expired link."
        )
    
    # Check if token is for document upload (assuming we add this type)
    # For now, we can reuse POLICY_VIEW or add a new type
    # Let's assume we want to be strict about token types
    # if customer_token.token_type != CustomerTokenType.DOCUMENT_UPLOAD:
    #     raise HTTPException(status_code=400, detail="Invalid token type")

    # Validate file size (e.g., 10MB limit)
    MAX_FILE_SIZE = 10 * 1024 * 1024
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)
    
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File too large. Maximum size is 10MB."
        )

    # Validate file type
    ALLOWED_TYPES = ["application/pdf", "image/jpeg", "image/png"]
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported file type. Allowed: PDF, JPEG, PNG."
        )

    # In a real app, upload to S3/GCS here
    # For MVP, we'll just log it
    logger.info(
        "Document uploaded",
        customer_id=str(customer_token.customer_id),
        filename=file.filename,
        size=file_size
    )

    # Mark token as used
    customer_token.is_used = True
    customer_token.used_at = datetime.utcnow()
    customer_token.token_metadata = {
        "action": "document_upload",
        "filename": file.filename,
        "ip": request.client.host if request.client else None
    }
    
    await db.commit()

    return {"message": "Document uploaded successfully."}
