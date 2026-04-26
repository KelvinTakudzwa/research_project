"""
generate_certs.py — Cross-platform TLS certificate generation for MQTTS.

Creates a self-signed CA and a broker certificate signed by it.
Both 'broker' (Docker-internal) and 'localhost' (host simulator) are
included as Subject Alternative Names so all clients validate without errors.

Usage (from project root, with .venv active):
    python scripts/generate_certs.py

Produces: mosquitto/certs/{ca.key, ca.crt, server.key, server.crt}
"""

import os
import datetime
from pathlib import Path

from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
import ipaddress

CERT_DIR = Path(__file__).parent.parent / "mosquitto" / "certs"
CERT_DIR.mkdir(parents=True, exist_ok=True)

COUNTRY      = "ZW"
STATE        = "Mashonaland"
LOCALITY     = "Harare"
ORG          = "SolarPDMS"
VALIDITY     = 3650  # 10 years

def _write_key(key, path: Path):
    path.write_bytes(key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ))
    print(f"  Written: {path}")

def _write_cert(cert, path: Path):
    path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    print(f"  Written: {path}")

now = datetime.datetime.now(datetime.timezone.utc)

# ── Step 1: CA key + self-signed certificate ──────────────────────────────────
print("[1/4] Generating CA private key...")
ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048,
                                   backend=default_backend())
_write_key(ca_key, CERT_DIR / "ca.key")

print("[2/4] Generating self-signed CA certificate (valid 10 years)...")
ca_name = x509.Name([
    x509.NameAttribute(NameOID.COUNTRY_NAME,             COUNTRY),
    x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME,   STATE),
    x509.NameAttribute(NameOID.LOCALITY_NAME,            LOCALITY),
    x509.NameAttribute(NameOID.ORGANIZATION_NAME,        ORG),
    x509.NameAttribute(NameOID.COMMON_NAME,              f"{ORG}-CA"),
])
ca_cert = (
    x509.CertificateBuilder()
    .subject_name(ca_name)
    .issuer_name(ca_name)
    .public_key(ca_key.public_key())
    .serial_number(x509.random_serial_number())
    .not_valid_before(now)
    .not_valid_after(now + datetime.timedelta(days=VALIDITY))
    .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
    .sign(ca_key, hashes.SHA256(), default_backend())
)
_write_cert(ca_cert, CERT_DIR / "ca.crt")

# ── Step 2: Server key + CSR + certificate signed by CA ──────────────────────
print("[3/4] Generating broker private key...")
server_key = rsa.generate_private_key(public_exponent=65537, key_size=2048,
                                       backend=default_backend())
_write_key(server_key, CERT_DIR / "server.key")

print("[4/4] Signing broker certificate (SANs: broker, localhost, 127.0.0.1)...")
server_name = x509.Name([
    x509.NameAttribute(NameOID.COUNTRY_NAME,             COUNTRY),
    x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME,   STATE),
    x509.NameAttribute(NameOID.LOCALITY_NAME,            LOCALITY),
    x509.NameAttribute(NameOID.ORGANIZATION_NAME,        ORG),
    x509.NameAttribute(NameOID.COMMON_NAME,              "broker"),
])
san = x509.SubjectAlternativeName([
    x509.DNSName("broker"),
    x509.DNSName("localhost"),
    x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
])
server_cert = (
    x509.CertificateBuilder()
    .subject_name(server_name)
    .issuer_name(ca_cert.subject)
    .public_key(server_key.public_key())
    .serial_number(x509.random_serial_number())
    .not_valid_before(now)
    .not_valid_after(now + datetime.timedelta(days=VALIDITY))
    .add_extension(san, critical=False)
    .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
    .sign(ca_key, hashes.SHA256(), default_backend())
)
_write_cert(server_cert, CERT_DIR / "server.crt")

print()
print("Done. Certificates written to:", CERT_DIR)
print()
for f in sorted(CERT_DIR.iterdir()):
    print(f"  {f.name:20s}  {f.stat().st_size:6d} bytes")
print()
print("Next steps:")
print("  1. docker compose down")
print("  2. docker compose up -d --build")
print("  3. python simulation/mqtt_stream.py --speed 30")
