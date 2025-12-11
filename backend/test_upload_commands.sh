#!/bin/bash

# Document Upload Test Script
# Quick test commands for the document upload feature

API_URL="http://localhost:8000"
FRONTEND_URL="http://localhost:3000"

echo "=================================================="
echo "Document Upload Feature - Test Commands"
echo "=================================================="
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}1. Test Upload Request (by email)${NC}"
echo "   This will generate an upload URL for a customer"
echo ""
echo "curl -X POST \"$API_URL/api/test/test-upload-request\" \\"
echo "  -H \"Content-Type: application/json\" \\"
echo "  -d '{\"customer_email\": \"john@example.com\"}'"
echo ""

echo -e "${BLUE}2. Test Upload Request (by phone)${NC}"
echo ""
echo "curl -X POST \"$API_URL/api/test/test-upload-request\" \\"
echo "  -H \"Content-Type: application/json\" \\"
echo "  -d '{\"customer_phone\": \"+1234567890\"}'"
echo ""

echo -e "${BLUE}3. Admin Generate Upload Link${NC}"
echo "   Replace {customer_id} with actual UUID"
echo ""
echo "curl -X POST \"$API_URL/api/test/test-admin-upload-link/{customer_id}\""
echo ""

echo -e "${BLUE}4. Customer Lookup (by phone)${NC}"
echo ""
echo "curl -X GET \"$API_URL/api/test/test-customer-lookup?phone=+1234567890\""
echo ""

echo -e "${BLUE}5. Customer Lookup (by email)${NC}"
echo ""
echo "curl -X GET \"$API_URL/api/test/test-customer-lookup?email=john@example.com\""
echo ""

echo -e "${BLUE}6. Upload Document${NC}"
echo "   Replace {token} with actual token from above"
echo ""
echo "curl -X POST \"$API_URL/api/public/upload-document/{token}\" \\"
echo "  -F \"file=@/path/to/your/document.pdf\""
echo ""

echo -e "${YELLOW}Quick Test:${NC}"
echo "Run this to generate a test URL right now:"
echo ""
echo -e "${GREEN}curl -X POST \"$API_URL/api/test/test-upload-request\" \\"
echo "  -H \"Content-Type: application/json\" \\"
echo -e "  -d '{\"customer_email\": \"john@example.com\"}' | jq${NC}"
echo ""

echo "=================================================="
echo "API Documentation: $API_URL/docs"
echo "=================================================="
