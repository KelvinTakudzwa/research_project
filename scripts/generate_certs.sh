#!/usr/bin/env bash
# generate_certs.sh — Creates a self-signed CA and Mosquitto server certificate
# for MQTTS (TLS 1.2) on port 8883.
#
# Run once from the project root:
#   bash scripts/generate_certs.sh
#
# Produces: mosquitto/certs/{ca.key, ca.crt, server.key, server.crt}
# The CA cert (ca.crt) is distributed to all clients (backend container + simulator).
# The CA key (ca.key) never leaves this directory.

set -e

CERT_DIR="mosquitto/certs"
mkdir -p "$CERT_DIR"

echo "[1/4] Generating CA private key..."
openssl genrsa -out "$CERT_DIR/ca.key" 2048

echo "[2/4] Generating self-signed CA certificate (valid 10 years)..."
openssl req -new -x509 -days 3650 \
    -key "$CERT_DIR/ca.key" \
    -out "$CERT_DIR/ca.crt" \
    -subj "/C=ZW/ST=Mashonaland/L=Harare/O=SolarPDMS/CN=SolarPDMS-CA"

echo "[3/4] Generating broker private key and CSR..."
openssl genrsa -out "$CERT_DIR/server.key" 2048
openssl req -new \
    -key "$CERT_DIR/server.key" \
    -out "$CERT_DIR/server.csr" \
    -subj "/C=ZW/ST=Mashonaland/L=Harare/O=SolarPDMS/CN=broker"

echo "[4/4] Signing broker certificate with CA (SAN: broker + localhost)..."
# SAN is required so both the Docker-internal 'broker' hostname and the
# host-facing 'localhost' hostname validate without certificate errors.
cat > "$CERT_DIR/server_ext.cnf" <<EOF
[req]
req_extensions = v3_req
[v3_req]
subjectAltName = @alt_names
[alt_names]
DNS.1 = broker
DNS.2 = localhost
IP.1  = 127.0.0.1
EOF

openssl x509 -req -days 3650 \
    -in      "$CERT_DIR/server.csr" \
    -CA      "$CERT_DIR/ca.crt" \
    -CAkey   "$CERT_DIR/ca.key" \
    -CAcreateserial \
    -out     "$CERT_DIR/server.crt" \
    -extfile "$CERT_DIR/server_ext.cnf" \
    -extensions v3_req

# Clean up temp files
rm -f "$CERT_DIR/server.csr" "$CERT_DIR/server_ext.cnf" "$CERT_DIR/ca.srl"

echo ""
echo "Done. Certificates written to $CERT_DIR/"
ls -la "$CERT_DIR/"
echo ""
echo "Next: docker compose down && docker compose up -d --build"
