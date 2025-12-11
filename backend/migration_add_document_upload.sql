-- Migration: Add DOCUMENT_UPLOAD to CustomerTokenType enum
-- Date: 2025-12-11

-- First, remove the incorrectly cased value if it exists
-- Note: We can't directly remove enum values in PostgreSQL
-- So we need to add the correct uppercase version

-- Add new value to the enum (uppercase to match existing values)
ALTER TYPE customertokentype ADD VALUE IF NOT EXISTS 'DOCUMENT_UPLOAD';

-- Verify the change
-- SELECT enum_range(NULL::customertokentype);
