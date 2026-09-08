#!/bin/bash
# User data de lt-app (guía §7.2). Los huecos los llena "bash infra/userdata.sh lt-app",
# que lee los nombres de infra/entorno.sh. No pegues este archivo tal cual: pegá su salida.
set -euxo pipefail

dnf install -y python3.11 python3.11-pip postgresql16 unzip

mkdir -p /opt/ateneo
cd /opt/ateneo

aws s3 cp s3://__BUCKET_DEPLOY__/backend/backend-latest.zip .
unzip -o backend-latest.zip
aws s3 cp s3://__BUCKET_DEPLOY__/config/backend.env /etc/ateneo.env
chmod 600 /etc/ateneo.env

# El sitio estático que esta instancia sirve en "/" (guía §10).
mkdir -p /opt/ateneo/web
aws s3 sync s3://__BUCKET_WEB__/ /opt/ateneo/web/

python3.11 -m venv venv
./venv/bin/pip install -q -r backend/requirements.txt

cat > /etc/systemd/system/ateneo-backend.service <<'EOF'
[Unit]
Description=Ateneo backend
Wants=network-online.target
After=network-online.target
[Service]
EnvironmentFile=-/etc/ateneo.env
WorkingDirectory=/opt/ateneo/backend
ExecStart=/opt/ateneo/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8080 --workers 2
Restart=always
[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now ateneo-backend
