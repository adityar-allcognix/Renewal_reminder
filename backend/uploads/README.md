# Uploaded Documents

This directory stores customer insurance documents uploaded via the token-based upload system.

## Structure

Documents are organized by customer ID:
```
uploads/
  {customer_id}/
    {timestamp}_{original_filename}
```

## Naming Convention

- Format: `{YYYYMMDD_HHMMSS}_{customer_id}_{original_filename}`
- Example: `20251212_143022_fe1f4b77-be44-49f8-8710-5b6e5cdfd74c_policy.pdf`

## Security

- Files are stored locally for development
- In production, consider using cloud storage (S3, Azure Blob, etc.)
- Directory should be excluded from version control (added to .gitignore)
