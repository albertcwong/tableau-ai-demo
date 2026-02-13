#!/bin/bash
# Generate self-signed SSL certificate for localhost with SANs (Subject Alternative Names)

set -e

echo "Generating SSL certificate for localhost with SANs..."

# Create OpenSSL config file for SANs
cat > /tmp/openssl.conf <<EOF
[req]
distinguished_name = req_distinguished_name
req_extensions = v3_req
prompt = no

[req_distinguished_name]
CN = localhost

[v3_req]
basicConstraints = CA:FALSE
keyUsage = nonRepudiation, digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
DNS.1 = localhost
DNS.2 = *.localhost
IP.1 = 127.0.0.1
IP.2 = ::1
EOF

# Generate private key
openssl genrsa -out localhost-key.pem 2048

# Generate certificate signing request with SANs
openssl req -new -key localhost-key.pem -out localhost.csr -config /tmp/openssl.conf

# Generate self-signed certificate with SANs (valid for 365 days)
openssl x509 -req -days 365 -in localhost.csr -signkey localhost-key.pem -out localhost.pem -extensions v3_req -extfile /tmp/openssl.conf

# Clean up temporary files
rm localhost.csr
rm /tmp/openssl.conf

echo "✅ SSL certificates generated with SANs:"
echo "   - localhost-key.pem (private key)"
echo "   - localhost.pem (certificate)"
echo ""
echo "   Certificate includes:"
echo "   - localhost"
echo "   - *.localhost"
echo "   - 127.0.0.1"
echo "   - ::1"
echo ""
echo "⚠️  Note: You'll need to trust this certificate in your browser."
echo "   See docs/deployment/HTTPS_SETUP.md for instructions."
