#!/bin/bash

# Generate self-signed SSL certificate for local development
# This creates certificates that browsers will need to trust

echo "Generating SSL certificate for localhost..."

# Create certificate
openssl req -x509 -out localhost.pem -keyout localhost-key.pem \
  -newkey rsa:2048 -nodes -sha256 \
  -subj '/CN=localhost' -extensions EXT -config <( \
   printf "[dn]\nCN=localhost\n[req]\ndistinguished_name = dn\n[EXT]\nsubjectAltName=DNS:localhost\nkeyUsage=digitalSignature\nextendedKeyUsage=serverAuth")

echo ""
echo "✅ Certificate generated!"
echo ""
echo "⚠️  IMPORTANT: You need to trust this certificate in your browser:"
echo ""
echo "macOS:"
echo "  1. Open Keychain Access"
echo "  2. Drag localhost.pem into 'login' keychain"
echo "  3. Double-click the certificate"
echo "  4. Expand 'Trust' and set to 'Always Trust'"
echo ""
echo "Chrome/Edge:"
echo "  - Visit chrome://settings/certificates"
echo "  - Click 'Authorities' tab"
echo "  - Click 'Import' and select localhost.pem"
echo "  - Check 'Trust this certificate for identifying websites'"
echo ""
echo "Firefox:"
echo "  - Visit about:preferences#privacy"
echo "  - Click 'View Certificates' → 'Authorities' → 'Import'"
echo "  - Select localhost.pem and check 'Trust this CA to identify websites'"
echo ""
