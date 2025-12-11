# Document Upload Feature

## Overview

Token-based document upload system that allows customers to securely upload insurance documents without logging in. The system uses SMS triggers and secure token URLs.

## Architecture

```
Customer → SMS "UPLOAD" → Backend → Generate Token → Send URL → Upload Page
```

## Features

### 1. **SMS-Triggered Upload Request**
- Customer texts "UPLOAD" to your Twilio number
- System verifies customer by phone number
- Generates secure token with 48-hour expiry
- Sends upload URL via SMS

### 2. **Secure Token-Based Upload**
- Unique token per request
- Single-use tokens (invalidated after upload)
- 48-hour expiration
- Rate limiting (3 requests per 24 hours)

### 3. **User-Friendly Upload Page**
- Drag & drop interface
- File validation (PDF, JPEG, PNG only)
- Max 10MB file size
- Real-time error feedback
- Success confirmation

### 4. **Admin Controls**
- Manual link generation for customers
- Request tracking and audit logs
- Rate limit monitoring

## API Endpoints

### 1. SMS Webhook (Twilio)
```http
POST /api/sms/webhook
Content-Type: application/x-www-form-urlencoded

From=+1234567890
Body=UPLOAD
MessageSid=SM123...
```

**Response:**
```json
{
  "status": "success",
  "message": "Upload link generated",
  "customer_id": "uuid",
  "token": "secure-token",
  "upload_url": "http://localhost:3000/upload/token"
}
```

### 2. Admin Send Upload Link
```http
POST /api/sms/send-upload-link
Content-Type: application/json

{
  "customer_id": "uuid"
}
```

### 3. Upload Document
```http
POST /api/public/upload-document/{token}
Content-Type: multipart/form-data

file: [binary]
```

### 4. Test Endpoints

**Simulate SMS Request:**
```http
POST /api/test/test-upload-request
Content-Type: application/json

{
  "customer_email": "john@example.com"
}
```

**Admin Generate Link:**
```http
POST /api/test/test-admin-upload-link/{customer_id}
```

**Customer Lookup:**
```http
GET /api/test/test-customer-lookup?phone=+1234567890
```

## Setup Instructions

### Backend Setup

1. **Add Environment Variables**

```bash
# backend/.env
FRONTEND_URL=http://localhost:3000
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_PHONE_NUMBER=+1234567890
```

2. **Run Database Migrations** (if needed)

The `CustomerTokenType` enum now includes `DOCUMENT_UPLOAD`.

3. **Start Backend**

```bash
cd backend
uvicorn app.main:app --reload
```

### Frontend Setup

1. **Add Environment Variable**

```bash
# frontend/.env.local
NEXT_PUBLIC_API_URL=http://localhost:8000
```

2. **Start Frontend**

```bash
cd frontend
npm run dev
```

### Twilio Setup

1. **Configure Webhook URL**

In Twilio Console → Phone Numbers → Your Number → Messaging:

```
Webhook URL: https://your-domain.com/api/sms/webhook
HTTP Method: POST
```

## Testing (Trial Account)

Since Twilio trial accounts can't receive incoming messages, use the test endpoint:

### Method 1: Test Endpoint

```bash
curl -X POST "http://localhost:8000/api/test/test-upload-request" \
  -H "Content-Type: application/json" \
  -d '{"customer_email": "john@example.com"}'
```

**Console Output:**
```
======================================================================
🔗 DOCUMENT UPLOAD LINK GENERATED
======================================================================
Customer: John Doe
Phone: +1234567890
URL: http://localhost:3000/upload/abc123...
Expires: 48 hours
======================================================================
```

### Method 2: Admin API

```bash
curl -X POST "http://localhost:8000/api/test/test-admin-upload-link/{customer_id}"
```

### Method 3: Direct Token Generation

```bash
# In Python console or script
from app.database import get_db
from app.api.sms_webhook import create_upload_token

token = await create_upload_token(db, customer_id)
print(f"http://localhost:3000/upload/{token}")
```

## Usage Flow

### Customer-Initiated

1. Customer texts: **"UPLOAD"**
2. System checks:
   - Is phone number in database?
   - Does customer have active policies?
   - Has customer exceeded rate limit?
3. System generates token and URL
4. System logs URL to console (trial mode)
5. Customer opens URL in browser
6. Customer uploads document
7. Token is marked as used

### Agent-Initiated

1. Agent calls API with customer ID
2. System generates token and URL
3. System logs URL to console
4. Agent manually sends URL to customer
5. Customer uploads document

## Security Features

### 1. **Token Security**
- Cryptographically secure random tokens (32 bytes)
- Single-use tokens
- Time-based expiration (48 hours)
- Token type validation

### 2. **Rate Limiting**
- Max 3 requests per customer per 24 hours
- Prevents token abuse
- Configurable limits

### 3. **File Validation**
- File type whitelist (PDF, JPEG, PNG)
- Max file size: 10MB
- MIME type validation

### 4. **Customer Verification**
- Phone number matching
- Active policy check
- Database validation

### 5. **Audit Trail**
- All requests logged
- Token metadata stored
- Upload tracking

## Database Schema

### CustomerToken Table

```sql
CREATE TABLE customer_tokens (
    id UUID PRIMARY KEY,
    token VARCHAR(255) UNIQUE NOT NULL,
    token_type VARCHAR(50) NOT NULL, -- 'document_upload'
    customer_id UUID NOT NULL REFERENCES customers(id),
    policy_id UUID REFERENCES policies(id),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    used_at TIMESTAMP WITH TIME ZONE,
    is_used BOOLEAN DEFAULT FALSE,
    token_metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_token ON customer_tokens(token);
CREATE INDEX idx_customer_token ON customer_tokens(customer_id, token_type);
CREATE INDEX idx_expires ON customer_tokens(expires_at);
```

## Frontend Routes

### Upload Page
```
/upload/{token}
```

**Features:**
- Token validation
- Drag & drop upload
- File preview
- Upload progress
- Success/error handling
- Mobile responsive

## Configuration

### Rate Limits

Edit in `sms_webhook.py`:

```python
# Default: 3 requests per 24 hours
is_allowed, count = await check_rate_limit(
    db, 
    customer_id,
    max_requests=3,
    time_window_hours=24
)
```

### Token Expiry

Edit in `sms_webhook.py`:

```python
# Default: 48 hours
token = await create_upload_token(
    db, 
    customer_id, 
    expiry_hours=48
)
```

### File Limits

Edit in `document_upload.py`:

```python
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_TYPES = ["application/pdf", "image/jpeg", "image/png"]
```

## Monitoring

### Key Metrics

1. **Upload Requests**: Track via `CustomerToken` table
2. **Success Rate**: Compare requests vs successful uploads
3. **Token Usage**: Monitor `is_used` and `used_at` fields
4. **Rate Limit Hits**: Log when customers hit limits

### Sample Queries

```sql
-- Upload requests in last 24 hours
SELECT COUNT(*) 
FROM customer_tokens 
WHERE token_type = 'document_upload' 
  AND created_at > NOW() - INTERVAL '24 hours';

-- Successful uploads
SELECT COUNT(*) 
FROM customer_tokens 
WHERE token_type = 'document_upload' 
  AND is_used = true;

-- Average time to upload
SELECT AVG(used_at - created_at) 
FROM customer_tokens 
WHERE token_type = 'document_upload' 
  AND is_used = true;
```

## Production Deployment

### 1. Enable SMS Sending

In `sms_webhook.py`, uncomment:

```python
# Change from:
# await send_sms(From, response_msg)

# To:
await send_sms(From, response_msg)
```

### 2. Configure Twilio Webhook

Point Twilio to your production URL:
```
https://api.yourdomain.com/api/sms/webhook
```

### 3. Update Frontend URL

```bash
# backend/.env
FRONTEND_URL=https://yourdomain.com
```

### 4. Add SSL/TLS

Ensure both frontend and backend use HTTPS.

## Troubleshooting

### Issue: Token not found
- Check token expiration
- Verify token hasn't been used
- Check database for token record

### Issue: Customer not found
- Verify phone number format
- Check database for customer record
- Test with different phone formats

### Issue: Rate limit errors
- Check 24-hour window
- Review `check_rate_limit` function
- Adjust limits if needed

### Issue: Upload fails
- Check file size (<10MB)
- Verify file type (PDF/JPEG/PNG)
- Check backend logs

## API Documentation

Full API documentation available at:
```
http://localhost:8000/docs
```

## Support

For issues or questions:
1. Check console logs for detailed errors
2. Review Twilio webhook logs
3. Check database for token records
4. Monitor rate limit usage

## Future Enhancements

- [ ] Email-based upload requests
- [ ] Multiple file uploads
- [ ] File storage integration (S3/GCS)
- [ ] Document processing pipeline
- [ ] OCR for document extraction
- [ ] Customer notification on upload
- [ ] Admin dashboard for uploads
- [ ] Analytics and reporting
