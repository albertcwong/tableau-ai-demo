# Functional Testing Instructions

This document provides comprehensive instructions for functional testing, manual database inspection, and service verification for the Tableau AI Demo application.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [Database Testing](#database-testing)
4. [API Testing](#api-testing)
5. [Cache Testing](#cache-testing)
6. [Frontend Testing](#frontend-testing)
7. [Integration Testing](#integration-testing)
8. [Manual Database Inspection](#manual-database-inspection)
9. [Service Health Checks](#service-health-checks)
10. [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before starting testing, ensure you have:

- Docker and Docker Compose installed
- Python 3.12+ installed
- Node.js 20+ and npm installed
- PostgreSQL client tools (optional, for direct database access)
- Redis client tools (optional, for direct cache access)

---

## Environment Setup

### 1. Start Infrastructure Services

```bash
# Start PostgreSQL and Redis
docker-compose up -d

# Verify services are running
docker-compose ps

# Check service logs
docker-compose logs postgres
docker-compose logs redis
```

### 2. Backend Setup

```bash
cd backend

# Create and activate virtual environment (if not already done)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp ../.env.example .env
# Edit .env with your configuration

# Run database migrations
alembic upgrade head

# Verify migration status
alembic current
alembic history
```

### 3. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Set up environment variables
# Create .env.local with:
# NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## Database Testing

### 1. Database Connection Test

```bash
cd backend
source venv/bin/activate

# Run database connection test
pytest tests/test_database.py -v

# Expected output: All tests should pass
```

### 2. Database Schema Verification

```bash
# Connect to PostgreSQL
docker-compose exec postgres psql -U postgres -d tableau_demo

# List all tables
\dt

# Verify table structure
\d conversations
\d messages
\d sessions
\d datasources
\d views

# Check indexes
\di

# Verify enum type exists
\dT+ message_role

# Exit PostgreSQL
\q
```

### 3. Model Testing

```bash
cd backend
source venv/bin/activate

# Run all model tests
pytest tests/test_chat_models.py -v
pytest tests/test_tableau_models.py -v

# Run specific test
pytest tests/test_chat_models.py::test_create_conversation -v
```

### 4. Migration Testing

```bash
cd backend
source venv/bin/activate

# Check current migration version
alembic current

# Test migration rollback (if needed)
alembic downgrade -1
alembic upgrade head

# Verify schema matches models
alembic check
```

---

## API Testing

### 1. Start Backend Server

```bash
cd backend
source venv/bin/activate

# Start FastAPI server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Server should start on http://localhost:8000
```

### 2. Health Check Endpoints

#### Basic Health Check

```bash
curl http://localhost:8000/api/v1/health

# Expected response:
# {"status":"healthy"}
```

#### Database Health Check

```bash
curl http://localhost:8000/api/v1/health/database

# Expected response (healthy):
# {"status":"healthy","service":"database"}

# Expected response (unhealthy):
# {"status":"unhealthy","service":"database"}
```

#### Cache Health Check

```bash
curl http://localhost:8000/api/v1/health/cache

# Expected response (healthy):
# {"status":"healthy","service":"cache"}
```

#### All Services Health Check

```bash
curl http://localhost:8000/api/v1/health/all

# Expected response:
# {
#   "status": "healthy",
#   "services": {
#     "database": "healthy",
#     "cache": "healthy"
#   }
# }
```

### 3. API Documentation

```bash
# OpenAPI JSON
curl http://localhost:8000/api/v1/openapi.json

# Swagger UI (open in browser)
open http://localhost:8000/api/v1/docs

# ReDoc (open in browser)
open http://localhost:8000/api/v1/redoc
```

### 4. Request Logging Verification

When making API requests, check the backend console for request logs:

```
INFO - Request: GET /api/v1/health
INFO - Response: GET /api/v1/health - Status: 200 - Time: 0.003s
```

### 5. API Versioning Test

```bash
# Root endpoint (should redirect to v1 docs)
curl http://localhost:8000/

# V1 API endpoints
curl http://localhost:8000/api/v1/health
```

---

## Cache Testing

### 1. Redis Connection Test

```bash
cd backend
source venv/bin/activate

# Run cache tests
pytest tests/test_cache.py -v

# Expected output: All tests should pass
```

### 2. Direct Redis Access

```bash
# Connect to Redis CLI
docker-compose exec redis redis-cli

# Test basic operations
PING
# Expected: PONG

SET test_key "test_value"
GET test_key
# Expected: "test_value"

# Check connection info
INFO clients

# Exit Redis
exit
```

### 3. Cache Health via API

```bash
# Test cache health endpoint
curl http://localhost:8000/api/v1/health/cache

# Stop Redis to test failure
docker-compose stop redis
curl http://localhost:8000/api/v1/health/cache
# Expected: {"status":"unhealthy","service":"cache"}

# Restart Redis
docker-compose start redis
```

---

## Frontend Testing

### 1. Start Frontend Development Server

```bash
cd frontend

# Start Next.js dev server
npm run dev

# Server should start on http://localhost:3000
```

### 2. Browser Testing

1. Open http://localhost:3000 in your browser
2. Open browser DevTools (F12)
3. Check Console for errors
4. Check Network tab for API calls
5. Verify API client retry logic:
   - Stop backend server temporarily
   - Make a request from frontend
   - Check console for retry attempts
   - Restart backend and verify request succeeds

### 3. API Client Testing

```bash
# Test API client timeout (if backend is slow)
# Modify timeout in frontend/lib/api.ts temporarily
# Make request and verify timeout handling

# Test error handling
# Stop backend, make request, verify error interceptor logs
```

### 4. Type Validation Testing

#### Option 1: Browser Console Testing (Recommended - No Setup Required)

**Step 1:** Add the ValidationLoader component to your layout:

```typescript
// In app/layout.tsx
import { ValidationLoader } from '@/components/ValidationLoader';

export default function RootLayout({ children }) {
  return (
    <html>
      <body>
        {process.env.NODE_ENV === 'development' && <ValidationLoader />}
        {children}
      </body>
    </html>
  );
}
```

**Step 2:** Start the dev server and open browser console:

```bash
cd frontend
npm run dev
# Open http://localhost:3000
```

**Step 3:** In browser console, run:

```javascript
// Check if schemas are available
if (window.__validationSchemas) {
  // Run automated tests
  window.__validationSchemas.testMessageValidation();
  window.__validationSchemas.testConversationValidation();
  
  // Or test manually
  const { MessageSchema } = window.__validationSchemas;
  
  const validMessage = {
    id: '123e4567-e89b-12d3-a456-426614174000',
    role: 'user',
    content: 'Hello',
    createdAt: new Date(),
  };
  
  try {
    const result = MessageSchema.parse(validMessage);
    console.log('✅ Valid message passed:', result);
  } catch (error) {
    console.error('❌ Validation failed:', error);
  }
} else {
  console.error('Schemas not loaded. Make sure ValidationLoader is in your layout.');
}
```

#### Option 2: Set Up Automated Testing (Optional)

If you want automated tests, set up Vitest:

```bash
cd frontend
npm install -D vitest @vitest/ui @testing-library/react @testing-library/jest-dom
```

Create `frontend/vitest.config.ts`:

```typescript
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './'),
    },
  },
});
```

Create `frontend/tests/validation.test.ts`:

```typescript
import { describe, test, expect } from 'vitest';
import { MessageSchema, ConversationSchema } from '@/types';

describe('Type Validation', () => {
  test('validates correct message', () => {
    const validMessage = {
      id: '123e4567-e89b-12d3-a456-426614174000',
      role: 'user',
      content: 'Hello',
      createdAt: new Date(),
    };

    const result = MessageSchema.parse(validMessage);
    expect(result.role).toBe('user');
  });

  test('rejects invalid role', () => {
    const invalidMessage = {
      id: '123e4567-e89b-12d3-a456-426614174000',
      role: 'invalid',
      content: 'Hello',
      createdAt: new Date(),
    };

    expect(() => MessageSchema.parse(invalidMessage)).toThrow();
  });
});
```

Add test script to `package.json`:

```json
{
  "scripts": {
    "test": "vitest",
    "test:ui": "vitest --ui"
  }
}
```

Run tests:
```bash
npm test
```

#### Option 2: Browser Console Testing

**Step 1:** Import the validation test utility in a client component. Create or update a component that runs in the browser:

```typescript
// In any client component (e.g., create frontend/components/ValidationLoader.tsx)
'use client';

import { useEffect } from 'react';

export function ValidationLoader() {
  useEffect(() => {
    // Dynamically import to make schemas available globally
    import('@/lib/validation-test');
  }, []);
  
  return null; // This component renders nothing
}
```

Then add it to your layout or page:

```typescript
// In app/layout.tsx
import { ValidationLoader } from '@/components/ValidationLoader';

export default function RootLayout({ children }) {
  return (
    <html>
      <body>
        {process.env.NODE_ENV === 'development' && <ValidationLoader />}
        {children}
      </body>
    </html>
  );
}
```

**Step 2:** In browser console (on http://localhost:3000), use the global schemas:

```javascript
// Check if schemas are available
if (window.__validationSchemas) {
  const { MessageSchema, ConversationSchema, testMessageValidation } = window.__validationSchemas;
  
  // Test valid message
  const validMessage = {
    id: '123e4567-e89b-12d3-a456-426614174000',
    role: 'user',
    content: 'Hello',
    createdAt: new Date(),
  };
  
  try {
    const result = MessageSchema.parse(validMessage);
    console.log('✅ Valid message passed:', result);
  } catch (error) {
    console.error('❌ Validation failed:', error);
  }
  
  // Test invalid role
  const invalidMessage = {
    id: '123e4567-e89b-12d3-a456-426614174000',
    role: 'invalid',
    content: 'Hello',
    createdAt: new Date(),
  };
  
  try {
    MessageSchema.parse(invalidMessage);
    console.log('❌ Invalid message should have failed');
  } catch (error) {
    console.log('✅ Invalid message correctly rejected:', error.message);
  }
  
  // Or use the test functions
  testMessageValidation();
} else {
  console.error('Schemas not available. Make sure ValidationLoader is imported.');
}
```

**Alternative: Manual Testing Without Imports**

If you can't use imports, test validation manually:

```javascript
// In browser console - manual validation checks
function validateMessage(msg) {
  const errors = [];
  
  // Check UUID format
  const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  if (!uuidRegex.test(msg.id)) {
    errors.push('ID must be a valid UUID');
  }
  
  // Check role
  if (!['user', 'assistant', 'system'].includes(msg.role)) {
    errors.push('Role must be user, assistant, or system');
  }
  
  // Check content
  if (!msg.content || msg.content.length === 0) {
    errors.push('Content cannot be empty');
  }
  if (msg.content.length > 100000) {
    errors.push('Content cannot exceed 100KB');
  }
  
  // Check date
  if (!(msg.createdAt instanceof Date)) {
    errors.push('createdAt must be a Date object');
  }
  
  return errors.length === 0 ? { valid: true } : { valid: false, errors };
}

// Test it
const testMsg = {
  id: '123e4567-e89b-12d3-a456-426614174000',
  role: 'user',
  content: 'Hello',
  createdAt: new Date(),
};

console.log(validateMessage(testMsg)); // Should be valid
console.log(validateMessage({ ...testMsg, role: 'invalid' })); // Should have errors
```

#### Option 3: Test via Next.js Page Component

Create a test page `frontend/app/test-validation/page.tsx`:

```typescript
'use client';

import { MessageSchema, ConversationSchema } from '@/types';
import { useEffect, useState } from 'react';

export default function ValidationTestPage() {
  const [results, setResults] = useState<string[]>([]);

  useEffect(() => {
    const testResults: string[] = [];

    // Test valid message
    try {
      const validMessage = {
        id: '123e4567-e89b-12d3-a456-426614174000',
        role: 'user' as const,
        content: 'Hello',
        createdAt: new Date(),
      };
      MessageSchema.parse(validMessage);
      testResults.push('✅ Valid message passed');
    } catch (error) {
      testResults.push(`❌ Valid message failed: ${error}`);
    }

    // Test invalid role
    try {
      const invalidMessage = {
        id: '123e4567-e89b-12d3-a456-426614174000',
        role: 'invalid' as any,
        content: 'Hello',
        createdAt: new Date(),
      };
      MessageSchema.parse(invalidMessage);
      testResults.push('❌ Invalid role should have failed');
    } catch (error: any) {
      testResults.push(`✅ Invalid role correctly rejected: ${error.message}`);
    }

    setResults(testResults);
  }, []);

  return (
    <div style={{ padding: '20px' }}>
      <h1>Type Validation Tests</h1>
      <ul>
        {results.map((result, i) => (
          <li key={i}>{result}</li>
        ))}
      </ul>
    </div>
  );
}
```

Visit `http://localhost:3000/test-validation` to see validation results.

---

## Integration Testing

### 1. End-to-End Flow Test

```bash
# 1. Start all services
docker-compose up -d
cd backend && source venv/bin/activate && uvicorn app.main:app --reload &
cd frontend && npm run dev &

# 2. Verify all services are healthy
curl http://localhost:8000/api/v1/health/all

# 3. Test frontend can connect to backend
# Open http://localhost:3000
# Check browser console for successful API calls

# 4. Test database operations
# Create test data via API (when endpoints are implemented)
# Verify data in database

# 5. Test cache operations
# Verify cache is being used (when implemented)
```

### 2. Database Connection Retry Test

```bash
# Stop PostgreSQL
docker-compose stop postgres

# Try to start backend (should handle gracefully)
cd backend
source venv/bin/activate
uvicorn app.main:app --reload

# Check logs for retry attempts
# Restart PostgreSQL
docker-compose start postgres

# Verify backend connects successfully
```

### 3. Cache Connection Retry Test

```bash
# Stop Redis
docker-compose stop redis

# Try to start backend (should handle gracefully)
# Check logs for retry attempts
# Restart Redis
docker-compose start redis

# Verify backend connects successfully
```

---

## Manual Database Inspection

### 1. Connect to Database

```bash
# Using Docker
docker-compose exec postgres psql -U postgres -d tableau_demo

# Or using psql directly (if configured)
psql -h localhost -U postgres -d tableau_demo
```

### 2. Inspect Tables

```sql
-- List all tables
\dt

-- View table structure
\d conversations
\d messages
\d sessions
\d datasources
\d views

-- Check table row counts
SELECT COUNT(*) FROM conversations;
SELECT COUNT(*) FROM messages;
SELECT COUNT(*) FROM sessions;
SELECT COUNT(*) FROM datasources;
SELECT COUNT(*) FROM views;
```

### 3. Verify Data Integrity

```sql
-- Check conversations and messages relationship
SELECT 
    c.id as conversation_id,
    c.created_at,
    COUNT(m.id) as message_count
FROM conversations c
LEFT JOIN messages m ON c.id = m.conversation_id
GROUP BY c.id, c.created_at
ORDER BY c.created_at DESC;

-- Check message roles (should only be USER, ASSISTANT, SYSTEM)
SELECT DISTINCT role FROM messages;

-- Check datasources and views relationship
SELECT 
    d.id as datasource_id,
    d.name,
    COUNT(v.id) as view_count
FROM datasources d
LEFT JOIN views v ON d.id = v.datasource_id
GROUP BY d.id, d.name;

-- Check for active vs inactive datasources
SELECT 
    is_active,
    COUNT(*) as count
FROM datasources
GROUP BY is_active;

-- Check sync timestamps
SELECT 
    tableau_id,
    name,
    updated_at,
    last_synced_at,
    CASE 
        WHEN last_synced_at IS NULL THEN 'Never synced'
        WHEN last_synced_at < updated_at THEN 'Out of sync'
        ELSE 'Synced'
    END as sync_status
FROM datasources
ORDER BY last_synced_at DESC NULLS LAST;
```

### 4. Check Indexes

```sql
-- List all indexes
\di

-- Check index usage (requires pg_stat_statements extension)
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan as index_scans
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY idx_scan DESC;
```

### 5. Verify Constraints

```sql
-- Check foreign key constraints
SELECT
    tc.table_name, 
    kcu.column_name, 
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name 
FROM information_schema.table_constraints AS tc 
JOIN information_schema.key_column_usage AS kcu
  ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage AS ccu
  ON ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY';

-- Check unique constraints
SELECT
    tc.table_name,
    tc.constraint_name,
    kcu.column_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
  ON tc.constraint_name = kcu.constraint_name
WHERE tc.constraint_type = 'UNIQUE';
```

### 6. Check Enum Types

```sql
-- List enum types
\dT+

-- Check enum values
SELECT enumlabel 
FROM pg_enum 
WHERE enumtypid = 'message_role'::regtype
ORDER BY enumsortorder;
```

### 7. Performance Inspection

```sql
-- Check table sizes
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Check for missing indexes on foreign keys
SELECT
    t.relname AS table_name,
    a.attname AS column_name
FROM pg_class t
JOIN pg_attribute a ON a.attrelid = t.oid
JOIN pg_constraint c ON c.conrelid = t.oid AND a.attnum = ANY(c.conkey)
LEFT JOIN pg_index i ON i.indrelid = t.oid AND a.attnum = ANY(i.indkey)
WHERE c.contype = 'f'
  AND i.indexrelid IS NULL
  AND t.relkind = 'r'
ORDER BY t.relname, a.attname;
```

---

## Service Health Checks

### 1. Backend Service

```bash
# Check if backend is running
curl http://localhost:8000/api/v1/health

# Check process
ps aux | grep uvicorn

# Check logs
tail -f backend/logs/app.log  # If logging to file
# Or check console output
```

### 2. Frontend Service

```bash
# Check if frontend is running
curl http://localhost:3000

# Check process
ps aux | grep next

# Check logs
# Check browser console for errors
```

### 3. PostgreSQL Service

```bash
# Check if PostgreSQL is running
docker-compose ps postgres

# Check logs
docker-compose logs postgres

# Test connection
docker-compose exec postgres pg_isready -U postgres

# Check database
docker-compose exec postgres psql -U postgres -c "\l"
```

### 4. Redis Service

```bash
# Check if Redis is running
docker-compose ps redis

# Check logs
docker-compose logs redis

# Test connection
docker-compose exec redis redis-cli PING

# Check info
docker-compose exec redis redis-cli INFO server
```

---

## Troubleshooting

### Database Connection Issues

**Problem:** Cannot connect to database

```bash
# Check if PostgreSQL is running
docker-compose ps postgres

# Check connection string in .env
cat backend/.env | grep DATABASE_URL

# Test connection manually
docker-compose exec postgres psql -U postgres -d tableau_demo

# Check database exists
docker-compose exec postgres psql -U postgres -c "\l" | grep tableau_demo
```

**Problem:** Migration fails

```bash
# Check current migration version
cd backend
source venv/bin/activate
alembic current

# Check migration history
alembic history

# Try manual migration
alembic upgrade head

# If stuck, check migration file for errors
cat alembic/versions/b182f78e08cb_add_enhancements_from_code_review.py
```

### Cache Connection Issues

**Problem:** Cannot connect to Redis

```bash
# Check if Redis is running
docker-compose ps redis

# Check connection string in .env
cat backend/.env | grep REDIS_URL

# Test connection manually
docker-compose exec redis redis-cli PING

# Check Redis logs
docker-compose logs redis
```

### API Issues

**Problem:** API endpoints not responding

```bash
# Check if backend is running
curl http://localhost:8000/api/v1/health

# Check backend logs for errors
# Check CORS configuration in backend/app/core/config.py

# Verify API versioning
curl http://localhost:8000/api/v1/health
```

### Frontend Issues

**Problem:** Frontend cannot connect to backend

```bash
# Check API URL configuration
cat frontend/.env.local | grep NEXT_PUBLIC_API_URL

# Check CORS settings in backend
# Verify backend allows frontend origin

# Check browser console for errors
# Check Network tab for failed requests
```

### Model/Enum Issues

**Problem:** Enum type errors

```bash
# Check enum exists in database
docker-compose exec postgres psql -U postgres -d tableau_demo -c "\dT+ message_role"

# If missing, run migration
cd backend
source venv/bin/activate
alembic upgrade head

# Check model definition matches database
# Verify MessageRole enum in backend/app/models/chat.py
```

---

## Test Checklist

Use this checklist to verify all functionality:

### Infrastructure
- [ ] PostgreSQL is running and accessible
- [ ] Redis is running and accessible
- [ ] Docker containers are healthy
- [ ] Environment variables are configured

### Database
- [ ] Database connection successful
- [ ] All tables exist with correct schema
- [ ] Indexes are created
- [ ] Foreign key constraints are enforced
- [ ] Enum types are created
- [ ] Migrations run successfully
- [ ] Model tests pass

### Backend API
- [ ] Backend server starts without errors
- [ ] Health check endpoint responds
- [ ] Database health check works
- [ ] Cache health check works
- [ ] All services health check works
- [ ] API versioning is correct (/api/v1/)
- [ ] Request logging works
- [ ] OpenAPI docs accessible
- [ ] CORS configured correctly

### Cache
- [ ] Redis connection successful
- [ ] Cache health check works
- [ ] Cache retry logic works
- [ ] Cache tests pass

### Frontend
- [ ] Frontend server starts without errors
- [ ] API client connects to backend
- [ ] Error handling works
- [ ] Retry logic works
- [ ] Type validation works
- [ ] No console errors

### Integration
- [ ] All services work together
- [ ] Database retry logic works
- [ ] Cache retry logic works
- [ ] End-to-end flow works

---

## Additional Resources

- **API Documentation:** http://localhost:8000/api/v1/docs
- **Database Schema:** See `backend/alembic/versions/` for migration files
- **Model Definitions:** See `backend/app/models/`
- **Test Files:** See `backend/tests/`

---

**Last Updated:** February 1, 2026
