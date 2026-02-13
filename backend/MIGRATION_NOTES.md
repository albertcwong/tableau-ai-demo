# Migration: Add Unique Server URL and SSL Cert Path

## Status
⚠️ **Migration not yet run** - `ssl_cert_path` column is temporarily commented out in the model.

## To Complete the Migration

1. **Check for duplicate server URLs** (migration will fail if duplicates exist):
   ```bash
   cd backend
   source venv/bin/activate
   python3 check_migration_prereqs.py
   ```

2. **Run the migration**:
   ```bash
   alembic upgrade head
   ```

3. **After migration succeeds**, uncomment the `ssl_cert_path` column in the model:
   - File: `backend/app/models/user.py`
   - Line ~137: Uncomment `ssl_cert_path = Column(...)`

4. **Uncomment the code that uses ssl_cert_path**:
   - File: `backend/app/api/admin.py`
   - Line ~514: Uncomment `ssl_cert_path=...` in `create_tableau_config`
   - Line ~695-696: Uncomment the `if config_data.ssl_cert_path` block in `update_tableau_config`

## What the Migration Does

1. Normalizes existing server URLs (lowercase, removes trailing slashes and `/api` suffix)
2. Adds `ssl_cert_path` column to `tableau_server_configs` table
3. Adds unique constraint on `server_url` column

## Rollback

If you need to rollback:
```bash
alembic downgrade -1
```
