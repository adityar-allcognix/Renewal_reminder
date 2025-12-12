
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.api.customer_public import validate_token
from app.models import CustomerTokenType
from app.services.ocr_service import get_ocr_service
from datetime import datetime
from pathlib import Path
import structlog
import shutil
import os

logger = structlog.get_logger()

router = APIRouter()

# Upload directory
UPLOAD_DIR = Path(__file__).parent.parent.parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

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
    
    # Check if token is for document upload
    if customer_token.token_type != CustomerTokenType.DOCUMENT_UPLOAD:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This link is not valid for document uploads."
        )

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

    # Create customer directory
    customer_dir = UPLOAD_DIR / str(customer_token.customer_id)
    customer_dir.mkdir(exist_ok=True)
    
    # Generate unique filename
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    file_extension = Path(file.filename).suffix
    safe_filename = f"{timestamp}_{customer_token.customer_id}{file_extension}"
    file_path = customer_dir / safe_filename
    
    # Save file to disk
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        logger.info(
            "Document saved to disk",
            customer_id=str(customer_token.customer_id),
            filename=file.filename,
            saved_as=safe_filename,
            size=file_size,
            path=str(file_path)
        )
    except Exception as e:
        logger.error("Failed to save file", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save document"
        )
    
    # Process document with OCR
    ocr_result = {}
    try:
        ocr_service = get_ocr_service()
        
        # Get customer info from the relationship
        customer = customer_token.customer
        customer_name = customer.full_name if customer else None
        
        # Process document with customer name for validation
        ocr_result = ocr_service.process_document(
            str(file_path),
            customer_name=customer_name
        )
        
        logger.info(
            "Document processed with OCR",
            customer_id=str(customer_token.customer_id),
            customer_name=customer_name,
            policy_holder_name=ocr_result.get("policy_holder_name"),
            name_matches=ocr_result.get("name_matches"),
            validation_passed=ocr_result.get("validation_passed"),
            old_expiry_date=ocr_result.get("old_expiry_date"),
            new_start_date=ocr_result.get("new_start_date"),
            new_expiry_date=ocr_result.get("new_expiry_date")
        )
    except Exception as e:
        logger.warning("OCR processing failed", error=str(e))
        # Continue even if OCR fails
        ocr_result = {
            "old_expiry_date": None,
            "new_start_date": None,
            "new_expiry_date": None,
            "validation_passed": False,
            "error": str(e)
        }

    # Mark token as used
    try:
        customer_token.is_used = True
        customer_token.used_at = datetime.utcnow()
        customer_token.token_metadata = {
            "action": "document_upload",
            "filename": file.filename,
            "saved_filename": safe_filename,
            "file_path": str(file_path),
            "ip": request.client.host if request.client else None,
            "policy_holder_name": ocr_result.get("policy_holder_name"),
            "policy_number": ocr_result.get("policy_number"),
            "name_matches": ocr_result.get("name_matches"),
            "name_similarity": ocr_result.get("name_similarity"),
            "old_expiry_date": ocr_result.get("old_expiry_date"),
            "new_start_date": ocr_result.get("new_start_date"),
            "new_expiry_date": ocr_result.get("new_expiry_date"),
            "validation_passed": ocr_result.get("validation_passed"),
            "ocr_processed": True
        }
        
        await db.commit()
    except Exception as e:
        logger.error("Failed to update token", error=str(e))
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to complete upload process"
        )

    return {
        "message": "Document uploaded successfully.",
        "filename": file.filename,
        "policy_holder_name": ocr_result.get("policy_holder_name"),
        "policy_number": ocr_result.get("policy_number"),
        "name_matches": ocr_result.get("name_matches"),
        "name_similarity": ocr_result.get("name_similarity"),
        "old_expiry_date": ocr_result.get("old_expiry_date"),
        "new_start_date": ocr_result.get("new_start_date"),
        "new_expiry_date": ocr_result.get("new_expiry_date"),
        "validation_passed": ocr_result.get("validation_passed"),
        "extracted_text": ocr_result.get("extracted_text", "")
    }
