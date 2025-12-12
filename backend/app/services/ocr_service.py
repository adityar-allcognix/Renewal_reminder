"""
OCR Service for Document Processing
Extracts text and renewal dates from uploaded insurance documents
"""

import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
import structlog
from pathlib import Path
from difflib import SequenceMatcher

logger = structlog.get_logger()


class OCRService:
    """Service for OCR and document text extraction."""
    
    def __init__(self):
        self.ocr_engine = None
        self._init_ocr_engine()
    
    def _init_ocr_engine(self):
        """Initialize OCR engine (EasyOCR or Tesseract)."""
        try:
            # Try EasyOCR first (better for insurance documents)
            import easyocr
            self.ocr_engine = easyocr.Reader(['en'], gpu=False)
            self.engine_type = "easyocr"
            logger.info("OCR engine initialized", engine="EasyOCR")
        except ImportError:
            try:
                # Fallback to Tesseract
                import pytesseract
                self.ocr_engine = pytesseract
                self.engine_type = "tesseract"
                logger.info("OCR engine initialized", engine="Tesseract")
            except ImportError:
                logger.warning("No OCR engine available. Install easyocr or pytesseract")
                self.engine_type = None
    
    def extract_text_from_image(self, image_path: str) -> str:
        """
        Extract text from an image file.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Extracted text as string
        """
        if not self.ocr_engine:
            logger.error("OCR engine not initialized")
            return ""
        
        try:
            if self.engine_type == "easyocr":
                result = self.ocr_engine.readtext(image_path)
                text = " ".join([item[1] for item in result])
                return text
            
            elif self.engine_type == "tesseract":
                from PIL import Image
                import pytesseract
                
                image = Image.open(image_path)
                text = pytesseract.image_to_string(image)
                return text
            
            return ""
        
        except Exception as e:
            logger.error("OCR extraction failed", error=str(e), path=image_path)
            return ""
    
    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """
        Extract text from PDF file.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Extracted text as string
        """
        try:
            import PyPDF2
            
            text = ""
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            
            # If PDF text extraction yields nothing, try OCR on converted images
            if not text.strip() and self.ocr_engine:
                logger.info("PDF text extraction empty, trying OCR", path=pdf_path)
                text = self._ocr_pdf_as_images(pdf_path)
            
            return text
        
        except Exception as e:
            logger.error("PDF text extraction failed", error=str(e), path=pdf_path)
            return ""
    
    def _ocr_pdf_as_images(self, pdf_path: str) -> str:
        """Convert PDF pages to images and OCR them."""
        try:
            from pdf2image import convert_from_path
            import tempfile
            
            text = ""
            images = convert_from_path(pdf_path)
            
            for i, image in enumerate(images):
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                    image.save(tmp.name, 'PNG')
                    page_text = self.extract_text_from_image(tmp.name)
                    text += page_text + "\n"
                    Path(tmp.name).unlink()
            
            return text
        
        except Exception as e:
            logger.error("PDF OCR failed", error=str(e))
            return ""
    
    def extract_text(self, file_path: str) -> str:
        """
        Extract text from file (auto-detect type).
        
        Args:
            file_path: Path to the file
            
        Returns:
            Extracted text as string
        """
        file_ext = Path(file_path).suffix.lower()
        
        if file_ext == '.pdf':
            return self.extract_text_from_pdf(file_path)
        elif file_ext in ['.jpg', '.jpeg', '.png']:
            return self.extract_text_from_image(file_path)
        else:
            logger.warning("Unsupported file type for OCR", extension=file_ext)
            return ""
    
    def find_renewal_date(self, text: str) -> Optional[datetime]:
        """
        Find renewal/expiry date in extracted text.
        
        Looks for patterns like:
        - Expiry Date: 01/15/2025
        - Renewal Date: January 15, 2025
        - Valid Until: 2025-01-15
        - Expires: 15 Jan 2025
        - Expiry Date: 14-12-2025
        
        Args:
            text: Extracted text from document
            
        Returns:
            Parsed datetime or None
        """
        if not text:
            return None
        
        # Normalize whitespace (handle non-breaking spaces, etc.)
        text = ' '.join(text.split())
        
        logger.info(
            "Searching for renewal date in text",
            text_sample=text[:200]
        )
        
        # Common date patterns in insurance documents
        patterns = [
            # MM/DD/YYYY or DD/MM/YYYY with / or -
            (r'(?:expir(?:y|es|ation)|renewal|valid\s+until|'
             r'policy\s+end)[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{4})'),
            # DD-Mon-YYYY (07-Jan-2027)
            (r'(?:expir(?:y|es|ation)|renewal|valid\s+until|'
             r'policy\s+end)[:\s]+(\d{1,2}-[A-Za-z]{3}-\d{4})'),
            # Month DD, YYYY
            (r'(?:expir(?:y|es|ation)|renewal|valid\s+until|'
             r'policy\s+end)[:\s]+([A-Za-z]+\s+\d{1,2},?\s+\d{4})'),
            # DD Month YYYY
            (r'(?:expir(?:y|es|ation)|renewal|valid\s+until|'
             r'policy\s+end)[:\s]+(\d{1,2}\s+[A-Za-z]+\s+\d{4})'),
            # YYYY-MM-DD
            (r'(?:expir(?:y|es|ation)|renewal|valid\s+until|'
             r'policy\s+end)[:\s]+(\d{4}-\d{1,2}-\d{1,2})'),
            # Standalone dates with various formats
            (r'(?:date|expir|renewal|valid)[^\n]{0,20}?'
             r'(\d{1,2}[/-]\d{1,2}[/-]\d{4})'),
            (r'(?:date|expir|renewal|valid)[^\n]{0,20}?'
             r'(\d{1,2}-[A-Za-z]{3}-\d{4})'),
        ]
        
        for i, pattern in enumerate(patterns):
            logger.debug(
                f"Trying pattern {i+1}/{len(patterns)}",
                pattern=pattern[:50]
            )
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                date_str = match.group(1)
                logger.info(
                    "Date pattern matched",
                    raw_date=date_str,
                    pattern_index=i+1
                )
                parsed_date = self._parse_date_string(date_str)
                if parsed_date:
                    logger.info(
                        "Renewal date found and parsed",
                        raw_date=date_str,
                        parsed_date=parsed_date.isoformat()
                    )
                    return parsed_date
                else:
                    logger.warning(
                        "Date matched but failed to parse",
                        raw_date=date_str
                    )
        
        logger.warning(
            "No renewal date found in document",
            text_length=len(text)
        )
        return None
    
    def extract_policy_holder_name(self, text: str) -> Optional[str]:
        """Extract policy holder name from document text."""
        if not text:
            return None
        
        # Normalize whitespace
        text = ' '.join(text.split())
        
        logger.info(
            "Extracting policy holder name",
            text_sample=text[:200]
        )
        
        # Common patterns for policy holder names in insurance documents
        patterns = [
            r'(?:policy\s+holder|insured\s+name|name\s+of\s+insured|'
            r'policyholder|holder\s+name)[:\s]+([A-Z][A-Za-z\s\.]{2,})',
            r'(?:customer\s+name)[:\s]+([A-Z][A-Za-z\s\.]{2,})',
            r'(?:name|full\s+name)[:\s]+([A-Z][A-Za-z\s\.]{2,})',
            r'Mr\.?\s+([A-Z][A-Za-z\s\.]{2,})',
            r'Ms\.?\s+([A-Z][A-Za-z\s\.]{2,})',
            r'Mrs\.?\s+([A-Z][A-Za-z\s\.]{2,})',
        ]
        
        for i, pattern in enumerate(patterns):
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                name = match.group(1).strip()
                # Remove trailing text after the name
                # Stop at common keywords that appear after names
                stop_words = [
                    'Policy', 'Vehicle', 'Email', 'Phone', 
                    'Number', 'Type', 'Previous', 'Issue',
                    'Start', 'Expiry', 'Premium'
                ]
                for stop_word in stop_words:
                    if stop_word in name:
                        name = name.split(stop_word)[0].strip()
                
                # Filter out common false positives
                if (len(name) > 3 and 
                    not any(word in name.lower() 
                           for word in ['insurance', 'company', 'policy'])):
                    logger.info(
                        "Policy holder name extracted",
                        name=name,
                        pattern_index=i+1
                    )
                    return name
        
        logger.warning("No policy holder name found in document")
        return None
    
    def extract_policy_number(self, text: str) -> Optional[str]:
        """Extract policy number from document text."""
        if not text:
            return None
        
        # Common patterns for policy numbers
        patterns = [
            r'(?:policy\s+no\.?|policy\s+number|policy\s+#)[:\s]+'
            r'([A-Z0-9/-]+)',
            r'policy[:\s]+([A-Z]{2,}[0-9]{4,})',
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                policy_num = match.group(1).strip()
                if len(policy_num) >= 5:  # Policy numbers are usually long
                    logger.info(
                        "Policy number extracted",
                        policy_number=policy_num
                    )
                    return policy_num
        
        logger.warning("No policy number found in document")
        return None
    
    def validate_name_match(
        self,
        extracted_name: Optional[str],
        customer_name: str,
        threshold: float = 0.6
    ) -> Tuple[bool, float]:
        """Validate if extracted name matches customer name.
        
        Args:
            extracted_name: Name extracted from document
            customer_name: Name from database
            threshold: Similarity threshold (0.0 to 1.0)
            
        Returns:
            Tuple of (matches, similarity_score)
        """
        if not extracted_name:
            return False, 0.0
        
        # Normalize names
        name1 = extracted_name.lower().strip()
        name2 = customer_name.lower().strip()
        
        # Check for exact match
        if name1 == name2:
            return True, 1.0
        
        # Check if one name contains the other
        if name1 in name2 or name2 in name1:
            return True, 0.9
        
        # Calculate similarity ratio
        similarity = SequenceMatcher(None, name1, name2).ratio()
        matches = similarity >= threshold
        
        logger.info(
            "Name validation result",
            extracted=extracted_name,
            customer=customer_name,
            similarity=similarity,
            matches=matches
        )
        
        return matches, similarity
    
    def calculate_new_renewal_dates(
        self,
        old_expiry_date: datetime,
        policy_tenure_years: int = 1
    ) -> Dict[str, datetime]:
        """Calculate new renewal dates based on standard insurance rule.
        
        Standard Rule:
        - New policy start date = previous expiry date + 1 day
        - New policy expiry date = start date + policy tenure
        
        Args:
            old_expiry_date: Previous policy expiry date
            policy_tenure_years: Policy tenure in years (default 1)
            
        Returns:
            Dict with new_start_date and new_expiry_date
        """
        new_start_date = old_expiry_date + timedelta(days=1)
        new_expiry_date = datetime(
            new_start_date.year + policy_tenure_years,
            new_start_date.month,
            new_start_date.day
        ) - timedelta(days=1)
        
        logger.info(
            "New renewal dates calculated",
            old_expiry=old_expiry_date.strftime("%d-%b-%Y"),
            new_start=new_start_date.strftime("%d-%b-%Y"),
            new_expiry=new_expiry_date.strftime("%d-%b-%Y")
        )
        
        return {
            "new_start_date": new_start_date,
            "new_expiry_date": new_expiry_date
        }
    
    def _parse_date_string(self, date_str: str) -> Optional[datetime]:
        """Parse various date string formats."""
        date_formats = [
            "%m/%d/%Y",      # 01/15/2025
            "%d/%m/%Y",      # 15/01/2025
            "%d-%m-%Y",      # 15-01-2025
            "%m-%d-%Y",      # 01-15-2025
            "%d-%b-%Y",      # 07-Jan-2027
            "%d-%B-%Y",      # 07-January-2027
            "%Y-%m-%d",      # 2025-01-15
            "%B %d, %Y",     # January 15, 2025
            "%b %d, %Y",     # Jan 15, 2025
            "%d %B %Y",      # 15 January 2025
            "%d %b %Y",      # 15 Jan 2025
            "%B %d %Y",      # January 15 2025
            "%b %d %Y",      # Jan 15 2025
        ]
        
        for fmt in date_formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
        
        return None
    
    def process_document(
        self,
        file_path: str,
        customer_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Complete document processing with validation.
        
        Extracts:
        - Text content
        - Policy holder name
        - Policy number
        - Old expiry date
        - Calculates new renewal dates
        - Validates name matches customer
        
        Args:
            file_path: Path to the uploaded document
            customer_name: Customer name from database for validation
            
        Returns:
            Dict with all extracted and calculated information
        """
        logger.info(
            "Processing document with validation",
            path=file_path,
            customer_name=customer_name
        )
        
        # Extract text
        extracted_text = self.extract_text(file_path)
        
        # Extract policy information
        policy_holder_name = self.extract_policy_holder_name(extracted_text)
        policy_number = self.extract_policy_number(extracted_text)
        old_expiry_date = self.find_renewal_date(extracted_text)
        
        # Validate name if customer name provided
        name_matches = False
        name_similarity = 0.0
        if customer_name and policy_holder_name:
            name_matches, name_similarity = self.validate_name_match(
                policy_holder_name,
                customer_name
            )
        
        # Calculate new renewal dates if old expiry found
        new_dates = None
        if old_expiry_date:
            new_dates = self.calculate_new_renewal_dates(old_expiry_date)
        
        result = {
            "extracted_text": (
                extracted_text[:500] if extracted_text else ""
            ),
            "full_text_length": len(extracted_text) if extracted_text else 0,
            "policy_holder_name": policy_holder_name,
            "policy_number": policy_number,
            "name_matches": name_matches,
            "name_similarity": round(name_similarity, 2),
            "old_expiry_date": (
                old_expiry_date.isoformat() if old_expiry_date else None
            ),
            "new_start_date": (
                new_dates["new_start_date"].isoformat() 
                if new_dates else None
            ),
            "new_expiry_date": (
                new_dates["new_expiry_date"].isoformat() 
                if new_dates else None
            ),
            "validation_passed": (
                name_matches and old_expiry_date is not None
            )
        }
        
        logger.info(
            "Document processing complete",
            text_length=result["full_text_length"],
            policy_holder_name=policy_holder_name,
            policy_number=policy_number,
            name_matches=name_matches,
            validation_passed=result["validation_passed"]
        )
        
        return result


# Singleton instance
_ocr_service = None

def get_ocr_service() -> OCRService:
    """Get or create OCR service singleton."""
    global _ocr_service
    if _ocr_service is None:
        _ocr_service = OCRService()
    return _ocr_service
