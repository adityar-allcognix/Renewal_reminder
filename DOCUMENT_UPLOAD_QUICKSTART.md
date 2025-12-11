# Document Upload Feature - Quick Start Guide

## 🚀 What We Built

A complete token-based document upload system where customers can text "UPLOAD" to receive a secure link to upload their insurance documents.

## 📁 New Files Created

### Backend
- `backend/app/api/sms_webhook.py` - SMS webhook handler for incoming messages
- `backend/app/api/test_upload.py` - Test endpoints for development
- `backend/app/services/sms_service.py` - SMS service wrapper
- `backend/test_document_upload.py` - Test script

### Frontend
- `frontend/app/upload/[token]/page.tsx` - Token-based upload page
- `frontend/.env.example` - Environment configuration example

### Documentation
- `DOCUMENT_UPLOAD.md` - Complete feature documentation

### Modified Files
- `backend/app/models/__init__.py` - Added `DOCUMENT_UPLOAD` to `CustomerTokenType`
- `backend/app/api/document_upload.py` - Enforced token type validation
- `backend/app/config.py` - Added `FRONTEND_URL` setting
- `backend/app/main.py` - Registered new routers

## 🧪 Testing (Twilio Trial Mode)

Since you're using a Twilio trial account, use these methods:

### Method 1: Test API Endpoint

```bash
# Start backend
cd backend
uvicorn app.main:app --reload

# In another terminal, test with a customer email
curl -X POST "http://localhost:8000/api/test/test-upload-request" \
  -H "Content-Type: application/json" \
  -d '{"customer_email": "your-test-customer@example.com"}'
```

The upload URL will be printed in the console!

### Method 2: Python Test Script

```bash
cd backend
python test_document_upload.py
```

Select option 1 to generate a test upload URL.

### Method 3: FastAPI Docs

1. Open http://localhost:8000/docs
2. Find `/api/test/test-upload-request`
3. Try it out with a test customer email
4. Check console for upload URL

## 🌐 Testing the Frontend

```bash
# Start frontend
cd frontend
npm run dev

# Open the generated URL from above tests
# Example: http://localhost:3000/upload/abc123def456...
```

**Test the upload page:**
1. Try dragging a PDF file
2. Test with different file types (should reject non-PDF/image files)
3. Test with large files (should reject >10MB)
4. Complete an upload and see success message

## 📊 Flow Diagram

```
┌─────────────┐
│  Customer   │
│ texts       │
│  "UPLOAD"   │
└──────┬──────┘
       │
       ▼
┌─────────────────┐
│ Twilio Webhook  │◄── Production: /api/sms/webhook
│                 │    Testing: /api/test/test-upload-request
└────────┬────────┘
         │
         ▼
┌──────────────────┐
│ Verify Customer  │
│ - Check phone    │
│ - Check policies │
│ - Rate limit     │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Generate Token   │
│ - 48hr expiry    │
│ - Single use     │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Build URL        │
│ Console Log ✓    │ ◄── Trial mode: just logs
│ Send SMS ✗       │ ◄── Disabled for trial
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Customer Opens   │
│ Upload Page      │
│ /upload/{token}  │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Upload Document  │
│ - PDF/JPEG/PNG   │
│ - Max 10MB       │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Token Marked     │
│ as Used          │
└──────────────────┘
```

## 🔐 Security Features

✅ **Token Security**
- Cryptographically secure (32-byte random)
- Single-use only
- 48-hour expiration
- Type-specific validation

✅ **Rate Limiting**
- 3 requests per customer per 24 hours
- Prevents abuse

✅ **File Validation**
- Type whitelist: PDF, JPEG, PNG only
- Size limit: 10MB max
- MIME type checking

✅ **Customer Verification**
- Phone number validation
- Active policy requirement
- Database verification

## 📝 Key Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/sms/webhook` | POST | Twilio SMS webhook |
| `/api/test/test-upload-request` | POST | Test token generation |
| `/api/test/test-admin-upload-link/{id}` | POST | Admin generate link |
| `/api/public/upload-document/{token}` | POST | Upload document |
| `/upload/{token}` | GET | Frontend upload page |

## 🔄 Production Setup

When ready for production:

1. **Enable SMS Sending** in `sms_webhook.py`:
   ```python
   # Uncomment this line:
   await send_sms(From, response_msg)
   ```

2. **Configure Twilio Webhook**:
   - Point to: `https://api.yourdomain.com/api/sms/webhook`

3. **Update Environment Variables**:
   ```bash
   FRONTEND_URL=https://yourdomain.com
   ```

4. **Deploy Both Apps**:
   - Frontend: Vercel/Netlify
   - Backend: Railway/Render/AWS

## 📈 Monitoring

Check these in production:

```sql
-- Total upload requests
SELECT COUNT(*) FROM customer_tokens 
WHERE token_type = 'document_upload';

-- Successful uploads
SELECT COUNT(*) FROM customer_tokens 
WHERE token_type = 'document_upload' AND is_used = true;

-- Success rate
SELECT 
  (COUNT(*) FILTER (WHERE is_used = true) * 100.0 / COUNT(*)) as success_rate
FROM customer_tokens 
WHERE token_type = 'document_upload';
```

## 🐛 Common Issues

**Issue: "Customer not found"**
- Make sure customer has a phone number in database
- Check phone format matches (try with/without +)

**Issue: "No active policies"**
- Customer needs at least one active policy
- Check `policies` table for customer

**Issue: "Rate limit exceeded"**
- Customer requested 3+ times in 24 hours
- Wait or manually reset in database

**Issue: Upload page shows "Invalid token"**
- Token expired (>48 hours old)
- Token already used
- Wrong token in URL

## 📚 Full Documentation

See `DOCUMENT_UPLOAD.md` for complete documentation including:
- Detailed API specs
- Database schema
- Configuration options
- Troubleshooting guide
- Production deployment steps

## 🎉 You're Ready!

Test the flow now:
```bash
# Terminal 1: Start backend
cd backend && uvicorn app.main:app --reload

# Terminal 2: Start frontend  
cd frontend && npm run dev

# Terminal 3: Generate test URL
curl -X POST "http://localhost:8000/api/test/test-upload-request" \
  -H "Content-Type: application/json" \
  -d '{"customer_email": "test@example.com"}'
```

Copy the URL from console and test the upload! 🚀
