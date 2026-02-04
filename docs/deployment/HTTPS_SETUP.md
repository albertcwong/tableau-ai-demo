# HTTPS Setup for Development

This project requires HTTPS for the frontend to work with Tableau Server authentication.

## Quick Start

### Option 1: Using the included script (Recommended)

1. **Generate SSL certificate:**
   ```bash
   cd frontend
   npm run generate-cert
   ```

2. **Trust the certificate in your browser:**
   
   **macOS:**
   - Open Keychain Access
   - Drag `localhost.pem` into the "login" keychain
   - Double-click the certificate
   - Expand "Trust" section
   - Set "When using this certificate" to "Always Trust"

   **Chrome/Edge:**
   - Visit `chrome://settings/certificates`
   - Click "Authorities" tab
   - Click "Import" and select `localhost.pem`
   - Check "Trust this certificate for identifying websites"

   **Firefox:**
   - Visit `about:preferences#privacy`
   - Click "View Certificates" → "Authorities" → "Import"
   - Select `localhost.pem` and check "Trust this CA to identify websites"

3. **Start the HTTPS dev server:**
   ```bash
   npm run dev
   ```

4. **Access the app:**
   - Open `https://localhost:3000` in your browser
   - Accept the security warning if prompted (after trusting the cert)

### Option 2: Using mkcert (Alternative - easier certificate trust)

1. **Install mkcert:**
   ```bash
   # macOS
   brew install mkcert
   brew install nss  # for Firefox
   
   # Linux
   sudo apt install libnss3-tools
   wget https://github.com/FiloSottile/mkcert/releases/latest/download/mkcert-v1.4.4-linux-amd64
   sudo mv mkcert-v1.4.4-linux-amd64 /usr/local/bin/mkcert
   sudo chmod +x /usr/local/bin/mkcert
   ```

2. **Install local CA:**
   ```bash
   mkcert -install
   ```

3. **Generate certificate:**
   ```bash
   cd frontend
   mkcert localhost
   mv localhost.pem localhost.pem
   mv localhost-key.pem localhost-key.pem
   ```

4. **Start the HTTPS dev server:**
   ```bash
   npm run dev
   ```

## Switching Between HTTP and HTTPS

- **HTTPS (default):** `npm run dev`
- **HTTP:** `npm run dev:http`

## Troubleshooting

### Certificate errors
- Make sure you've trusted the certificate in your browser
- Clear browser cache and restart browser
- Try incognito/private mode to test

### Port already in use
- Make sure port 3000 is not being used by another process
- Change the port in `server.js` if needed

### Backend CORS errors
- Make sure `CORS_ORIGINS` in `.env` includes `https://localhost:3000`
- Restart the backend server after updating `.env`

## Notes

- The SSL certificates (`*.pem` files) are gitignored for security
- Each developer needs to generate their own certificates
- Certificates are valid for localhost only
- For production, use proper SSL certificates from a CA
