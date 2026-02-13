# Auth0 Tableau Username Metadata Configuration Guide

This guide explains how to configure Auth0 to include custom metadata (Tableau username) in JWT tokens, which is then automatically extracted and mapped to users in the application.

## Overview

When users authenticate via Auth0, the application can automatically extract their Tableau username from custom metadata fields in the Auth0 token. This eliminates the need for manual Tableau username mapping in the admin panel.

**Note:** `tableau_username` is used for **Connected App (Direct Trust)** sign-in and main app user mapping. **OAuth 2.0 Trust** uses the admin-configured **EAS JWT Sub Claim** (e.g. `email` for Tableau OIDC, `tableau_username` for direct mapping) – see [OAuth 2.0 Trust Setup](./OAUTH_2_0_TRUST_SETUP.md).

## Step 1: Configure Custom Metadata in Auth0

### Option A: Using Auth0 Dashboard (Recommended for Testing)

1. **Log into Auth0 Dashboard**
   - Go to https://manage.auth0.com
   - Navigate to **User Management** → **Users**

2. **Edit User Metadata**
   - Click on a user to edit
   - Scroll to **Metadata** section
   - Choose one of the following:

   **For App Metadata (Recommended for Production):**
   - Click **App metadata** tab
   - Click **Edit** (pencil icon)
   - Add a new field:
     ```json
     {
       "tableau_username": "john.doe"
     }
     ```
   - Click **Save**

   **For User Metadata (User-editable):**
   - Click **User metadata** tab
   - Click **Edit** (pencil icon)
   - Add a new field:
     ```json
     {
       "tableau_username": "john.doe"
     }
     ```
   - Click **Save**

### Option B: Using Auth0 Management API (Recommended for Production)

For bulk updates or automated provisioning, use the Auth0 Management API:

```bash
# Update app_metadata for a user
curl -X PATCH "https://YOUR_TENANT.auth0.com/api/v2/users/USER_ID" \
  -H "Authorization: Bearer YOUR_MANAGEMENT_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "app_metadata": {
      "tableau_username": "john.doe"
    }
  }'
```

**Note:** App metadata is read-only for users and can only be modified via the Management API or Dashboard. User metadata can be modified by users themselves.

## Step 2: Configure Rules/Actions to Include Metadata in Tokens

By default, Auth0 includes `app_metadata` and `user_metadata` in the ID token, but **not** in the access token. To include metadata in access tokens (required for API authentication), you need to add a custom claim.

### Option A: Using Auth0 Actions (Recommended)

1. **Create a Login Action**
   - Go to **Actions** → **Flows** → **Login**
   - Click **+ Create Action**
   - Name it "Add Tableau Username to Token"
   - Select **Login / Post Login** trigger
   - Click **Create**

2. **Add Code**
   ```javascript
   exports.onExecutePostLogin = async (event, api) => {
     const namespace = 'https://tableau-ai-demo-api';
     
     // Extract tableau_username from app_metadata or user_metadata
     const tableauUsername = 
       event.user.app_metadata?.tableau_username ||
       event.user.user_metadata?.tableau_username;
     
     if (tableauUsername) {
       // Add as namespaced claim (recommended for access tokens)
       api.idToken.setCustomClaim(`${namespace}/tableau_username`, tableauUsername);
       api.accessToken.setCustomClaim(`${namespace}/tableau_username`, tableauUsername);
     }
   };
   ```

3. **Deploy the Action**
   - Click **Deploy**
   - Drag the action into the Login flow (between "Start" and "Complete")
   - Click **Apply**

### Option B: Using Auth0 Rules (Legacy)

If you're using Rules instead of Actions:

1. **Create a Rule**
   - Go to **Auth Pipeline** → **Rules**
   - Click **+ Create Rule**
   - Select **Empty Rule**
   - Name it "Add Tableau Username to Token"

2. **Add Code**
   ```javascript
   function (user, context, callback) {
     const namespace = 'https://tableau-ai-demo-api';
     
     // Extract tableau_username from app_metadata or user_metadata
     const tableauUsername = 
       user.app_metadata?.tableau_username ||
       user.user_metadata?.tableau_username;
     
     if (tableauUsername) {
       context.idToken[`${namespace}/tableau_username`] = tableauUsername;
       context.accessToken[`${namespace}/tableau_username`] = tableauUsername;
     }
     
     callback(null, user, context);
   }
   ```

3. **Save the Rule**
   - Click **Save Changes**

## Step 3: Configure Application Settings

1. **Go to Admin Panel**
   - Log into your application as an admin
   - Navigate to **Admin** → **Auth Configuration**

2. **Enable OAuth Authentication**
   - Check **Enable OAuth Authentication**
   - Fill in Auth0 configuration:
     - **Auth0 Domain**: `your-tenant.auth0.com`
     - **Auth0 Client ID**: Your application's client ID
     - **Auth0 Client Secret**: (Optional, for server-side apps)
     - **Auth0 Audience**: `https://tableau-ai-demo-api` (or your API identifier)

3. **Configure Metadata Field**
   - **Auth0 Tableau Metadata Field**: Enter the field path based on your configuration:
     
     **If using namespaced claim (from Action/Rule):**
     ```
     https://tableau-ai-demo-api/tableau_username
     ```
     
     **If using app_metadata directly:**
     ```
     app_metadata.tableau_username
     ```
     
     **If using user_metadata directly:**
     ```
     user_metadata.tableau_username
     ```
     
     **If using top-level claim:**
     ```
     tableau_username
     ```

4. **Save Configuration**
   - Click **Save Configuration**

## Step 4: Verify Configuration

1. **Test Login**
   - Log out and log back in via Auth0
   - The application should automatically extract the Tableau username

2. **Check User Profile**
   - Go to **Admin** → **Users**
   - Find your user
   - Verify that the **Tableau Username** field is populated

3. **Verify Token Claims**
   - You can decode your JWT token at https://jwt.io to verify the claim is present
   - Look for the `tableau_username` field in the token payload

## Field Path Examples

The **Auth0 Tableau Metadata Field** configuration supports different path formats:

| Auth0 Configuration | Field Path Example |
|---------------------|-------------------|
| Namespaced claim (Action/Rule) | `https://tableau-ai-demo-api/tableau_username` |
| App metadata | `app_metadata.tableau_username` |
| User metadata | `user_metadata.tableau_username` |
| Top-level claim | `tableau_username` |
| Nested metadata | `app_metadata.tableau.user.name` |

## Troubleshooting

### Tableau Username Not Being Extracted

1. **Check Token Claims**
   - Decode your JWT token at https://jwt.io
   - Verify the metadata field exists in the token
   - Check the exact field name and path

2. **Verify Field Path**
   - Ensure the field path in admin panel matches the token structure
   - Use dot notation for nested fields: `app_metadata.tableau_username`
   - Use full path for namespaced claims: `https://tableau-ai-demo-api/tableau_username`

3. **Check Action/Rule Execution**
   - Go to **Monitoring** → **Logs** in Auth0 Dashboard
   - Filter for login events
   - Check if your Action/Rule executed successfully
   - Look for any errors

4. **Verify Metadata is Set**
   - Go to **User Management** → **Users**
   - Check the user's metadata
   - Ensure `tableau_username` is set in `app_metadata` or `user_metadata`

### Common Issues

**Issue:** Field path doesn't match token structure
- **Solution:** Decode your token and use the exact path shown in the payload

**Issue:** Metadata not included in access token
- **Solution:** Use an Action/Rule to add custom claims to the access token

**Issue:** Metadata exists but not extracted
- **Solution:** Check the field path format - use dot notation for nested fields

## Best Practices

1. **Use App Metadata for Production**
   - App metadata is read-only for users
   - Prevents users from modifying their Tableau username
   - Use Management API for updates

2. **Use Namespaced Claims**
   - Prevents claim collisions
   - Follows Auth0 best practices
   - Use format: `https://your-api.com/claim_name`

3. **Validate Metadata Format**
   - Ensure Tableau usernames match your Tableau Server requirements
   - Consider case sensitivity
   - Handle special characters appropriately

4. **Bulk Updates**
   - Use Auth0 Management API for bulk user updates
   - Consider using Auth0's Bulk User Import feature
   - Automate metadata updates via user provisioning

## API Reference

### Management API Example

```python
from auth0.v3.authentication import GetToken
from auth0.v3.management import Auth0

# Get Management API token
domain = 'your-tenant.auth0.com'
client_id = 'YOUR_MANAGEMENT_API_CLIENT_ID'
client_secret = 'YOUR_MANAGEMENT_API_CLIENT_SECRET'

get_token = GetToken(domain)
token = get_token.client_credentials(
    client_id=client_id,
    client_secret=client_secret,
    audience=f'https://{domain}/api/v2/'
)

# Update user metadata
auth0 = Auth0(domain, token['access_token'])
auth0.users.update(
    user_id='auth0|123456789',
    body={
        'app_metadata': {
            'tableau_username': 'john.doe'
        }
    }
)
```

## Additional Resources

- [Auth0 Actions Documentation](https://auth0.com/docs/customize/actions)
- [Auth0 Rules Documentation](https://auth0.com/docs/customize/rules)
- [Auth0 Management API](https://auth0.com/docs/api/management/v2)
- [Auth0 Metadata Best Practices](https://auth0.com/docs/users/metadata)
