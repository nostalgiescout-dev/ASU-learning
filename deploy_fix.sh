#!/bin/bash
# =============================================================================
# deploy_fix.sh — Full repair: Nginx + Gunicorn + systemd for elearning app
# Domain  : kachafafaqat.com
# App dir : /var/www/ASU-Learning
# Gunicorn: 127.0.0.1:8000
# Run as root: sudo bash deploy_fix.sh
# =============================================================================
set -e

APP_DIR="/var/www/ASU-Learning"
VENV_DIR="$APP_DIR/venv"
SERVICE_NAME="elearning"
LOG_DIR="/var/log/ASU-Learning"
DOMAIN="kachafafaqat.com"
NGINX_CONF="/etc/nginx/sites-available/elearning"
NGINX_ENABLED="/etc/nginx/sites-enabled/elearning"

echo "================================================================"
echo " Step 1 — Verify app directory"
echo "================================================================"
if [ ! -d "$APP_DIR" ]; then
    echo "[ERROR] App directory $APP_DIR not found."
    echo "        Copy your project there first, e.g.:"
    echo "        rsync -av /your/local/ASU-Learning/ $APP_DIR/"
    exit 1
fi
echo "[OK] App directory: $APP_DIR"

echo ""
echo "================================================================"
echo " Step 2 — Detect Python 3"
echo "================================================================"
PYTHON=$(command -v python3 || true)
if [ -z "$PYTHON" ]; then
    echo "[INFO] python3 not found — installing..."
    apt-get update -q && apt-get install -y python3 python3-pip python3-venv
fi
PYTHON=$(command -v python3)
echo "[OK] $PYTHON ($($PYTHON --version))"

echo ""
echo "================================================================"
echo " Step 3 — Create / repair virtual environment"
echo "================================================================"
if [ ! -f "$VENV_DIR/bin/python" ]; then
    echo "[INFO] venv missing or broken — recreating at $VENV_DIR"
    rm -rf "$VENV_DIR"
    $PYTHON -m venv "$VENV_DIR"
    echo "[OK] venv created"
else
    echo "[OK] venv already exists"
fi

echo ""
echo "================================================================"
echo " Step 4 — Install Gunicorn and app dependencies"
echo "================================================================"
"$VENV_DIR/bin/pip" install --upgrade pip --quiet
"$VENV_DIR/bin/pip" install gunicorn --quiet

if [ -f "$APP_DIR/requirements.txt" ]; then
    "$VENV_DIR/bin/pip" install -r "$APP_DIR/requirements.txt" --quiet
    echo "[OK] requirements.txt installed"
else
    echo "[WARN] No requirements.txt found — skipping app deps"
fi

if [ ! -f "$VENV_DIR/bin/gunicorn" ]; then
    echo "[ERROR] gunicorn binary still missing — aborting"
    exit 1
fi
echo "[OK] gunicorn: $VENV_DIR/bin/gunicorn"

echo ""
echo "================================================================"
echo " Step 5 — Create log directory"
echo "================================================================"
mkdir -p "$LOG_DIR"
chown www-data:www-data "$LOG_DIR"
echo "[OK] $LOG_DIR"

echo ""
echo "================================================================"
echo " Step 6 — Install systemd service"
echo "================================================================"
cat > /etc/systemd/system/${SERVICE_NAME}.service << 'UNIT'
[Unit]
Description=Gunicorn daemon for elearning Flask app
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/ASU-Learning
EnvironmentFile=/var/www/ASU-Learning/.env

ExecStart=/var/www/ASU-Learning/venv/bin/gunicorn \
    --workers 3 \
    --bind 127.0.0.1:8000 \
    --timeout 120 \
    --access-logfile /var/log/elearning/access.log \
    --error-logfile  /var/log/elearning/error.log \
    app:application

ExecReload=/bin/kill -s HUP $MAINPID
KillMode=mixed
TimeoutStopSec=5
PrivateTmp=true
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
echo "[OK] systemd service installed"

echo ""
echo "================================================================"
echo " Step 7 — Fix file ownership"
echo "================================================================"
chown -R www-data:www-data "$APP_DIR"
echo "[OK] Ownership: www-data"

echo ""
echo "================================================================"
echo " Step 8 — Install Nginx if missing"
echo "================================================================"
if ! command -v nginx &>/dev/null; then
    apt-get update -q && apt-get install -y nginx
fi
echo "[OK] $(nginx -v 2>&1)"

echo ""
echo "================================================================"
echo " Step 9 — Write Nginx site config"
echo "================================================================"
cat > "$NGINX_CONF" << 'NGINX'
server {
    listen 80;
    server_name kachafafaqat.com www.kachafafaqat.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name kachafafaqat.com www.kachafafaqat.com;

    ssl_certificate     /etc/letsencrypt/live/kachafafaqat.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/kachafafaqat.com/privkey.pem;

    ssl_protocols             TLSv1.2 TLSv1.3;
    ssl_ciphers               HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    location /static/ {
        alias /var/www/ASU-Learning/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
        access_log off;
    }

    location / {
        proxy_pass         http://127.0.0.1:8000;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;

        proxy_connect_timeout 60s;
        proxy_send_timeout    60s;
        proxy_read_timeout    60s;

        client_max_body_size 50M;
    }
}
NGINX

ln -sf "$NGINX_CONF" "$NGINX_ENABLED"

if [ -f /etc/nginx/sites-enabled/default ]; then
    rm -f /etc/nginx/sites-enabled/default
    echo "[INFO] Removed conflicting default Nginx site"
fi
echo "[OK] Nginx site config written"

echo ""
echo "================================================================"
echo " Step 10 — Issue SSL certificate (skip if already exists)"
echo "================================================================"
CERT="/etc/letsencrypt/live/$DOMAIN/fullchain.pem"
if [ -f "$CERT" ]; then
    echo "[OK] SSL certificate already exists — skipping certbot"
else
    echo "[INFO] Certificate not found — running certbot..."
    if ! command -v certbot &>/dev/null; then
        apt-get install -y certbot python3-certbot-nginx --quiet
    fi
    # Stop nginx temporarily so certbot can bind port 80
    systemctl stop nginx || true
    certbot certonly --standalone \
        -d "$DOMAIN" -d "www.$DOMAIN" \
        --non-interactive --agree-tos \
        --email admin@$DOMAIN
    echo "[OK] Certificate issued for $DOMAIN"
fi

echo ""
echo "================================================================"
echo " Step 11 — Test Nginx configuration"
echo "================================================================"
if nginx -t; then
    echo "[OK] Nginx config syntax is valid"
else
    echo "[ERROR] Nginx config test failed — check output above"
    exit 1
fi

echo ""
echo "================================================================"
echo " Step 12 — Start / restart services"
echo "================================================================"
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"
sleep 2
systemctl reload nginx 2>/dev/null || systemctl restart nginx
sleep 1

echo ""
echo "================================================================"
echo " Step 13 — Verify status"
echo "================================================================"
echo "--- Gunicorn (${SERVICE_NAME}.service) ---"
systemctl status "$SERVICE_NAME" --no-pager -l | head -20

echo ""
echo "--- Nginx ---"
systemctl status nginx --no-pager -l | head -20

echo ""
echo "================================================================"
echo " Step 14 — Port smoke tests"
echo "================================================================"
sleep 2
if ss -tlnp | grep -q ':8000'; then
    echo "[OK] Port 8000 listening — Gunicorn is up"
else
    echo "[WARN] Port 8000 not detected — check: journalctl -u $SERVICE_NAME -n 50"
fi

if ss -tlnp | grep -q ':443'; then
    echo "[OK] Port 443 listening — Nginx HTTPS is up"
fi

if ss -tlnp | grep -q ':80'; then
    echo "[OK] Port 80 listening — Nginx HTTP redirect is up"
fi

HTTP_CODE=$(curl -sk -o /dev/null -w "%{http_code}" https://$DOMAIN/ || echo "000")
echo "[INFO] HTTPS response from $DOMAIN: $HTTP_CODE"

echo ""
echo "================================================================"
echo " DONE"
echo "================================================================"
echo "  journalctl -u $SERVICE_NAME -n 50 -f    # live Gunicorn logs"
echo "  tail -f $LOG_DIR/error.log               # app error log"
echo "  nginx -t                                 # re-test nginx config"
echo "  systemctl restart $SERVICE_NAME          # restart Gunicorn"
echo "  systemctl reload nginx                   # reload Nginx"
echo "  certbot renew --dry-run                  # test SSL auto-renewal"
echo ""
