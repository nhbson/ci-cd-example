#!/bin/bash
# Anti-DDoS v3.4 - Port Guard System

set -e

echo "🔥 Anti-DDoS v3.4 Port Guard System Starting..."

# -----------------------------
# DETECT ENVIRONMENT
# -----------------------------
IS_WSL=false
if grep -qi microsoft /proc/version 2>/dev/null; then
    IS_WSL=true
fi

echo "🧠 Environment detected:"
$IS_WSL && echo "➡️ WSL Mode" || echo "➡️ EC2/Linux Mode"

# -----------------------------
# INSTALL DEPENDENCIES
# -----------------------------
echo "📦 Installing dependencies..."
sudo apt update -y
sudo apt install -y nginx fail2ban redis-server jq lsof net-tools docker.io

# -----------------------------
# PORT GUARD ENGINE
# -----------------------------
echo "🛡 Running Port Guard Engine..."

NGINX_PORT=80

# Detect port 80 usage
if sudo ss -ltnp | grep -q ':80'; then
    echo "⚠️ Port 80 is occupied → activating fallback mode"

    # Find process
    sudo ss -ltnp | grep :80 || true

    # Try auto cleanup safe processes
    sudo systemctl stop apache2 2>/dev/null || true
    sudo pkill -f nginx 2>/dev/null || true

    # re-check
    sleep 1

    if sudo ss -ltnp | grep -q ':80'; then
        echo "❌ Still occupied → switching to PORT 8080"
        NGINX_PORT=8080
    fi
fi

echo "📌 Selected Nginx port: $NGINX_PORT"

# -----------------------------
# NGINX CONFIG (DYNAMIC PORT)
# -----------------------------
echo "⚙️ Configuring Nginx..."

sudo tee /etc/nginx/sites-enabled/default > /dev/null <<EOF
server {
    listen $NGINX_PORT default_server;
    listen [::]:$NGINX_PORT default_server;

    server_name _;

    location / {
        return 200 "Anti-DDoS v3.4 active on port $NGINX_PORT\n";
    }
}
EOF

# -----------------------------
# VALIDATE NGINX
# -----------------------------
if sudo nginx -t; then
    echo "✅ Nginx config valid"
else
    echo "❌ Nginx invalid → aborting safe mode"
    exit 1
fi

# -----------------------------
# SAFE START NGINX
# -----------------------------
echo "🚀 Starting Nginx safely..."

sudo systemctl restart nginx 2>/dev/null || sudo service nginx restart

# -----------------------------
# FAIL2BAN SETUP
# -----------------------------
echo "🛠 Setting Fail2Ban..."

sudo tee /etc/fail2ban/filter.d/nginx-ddos.conf > /dev/null <<EOF
[Definition]
failregex = ^<HOST> -.*"(GET|POST|HEAD).*HTTP/.*" (401|403|429|500)
ignoreregex =
EOF

sudo tee /etc/fail2ban/jail.d/nginx-ddos.conf > /dev/null <<EOF
[nginx-ddos]
enabled = true
filter = nginx-ddos
logpath = /var/log/nginx/access.log
maxretry = 20
findtime = 60
bantime = 3600
ignoreip = 127.0.0.1/8 ::1
action = iptables-multiport[name=nginx-ddos, port="80,443", protocol=tcp]
EOF

# -----------------------------
# REDIS SAFE START
# -----------------------------
echo "🧠 Starting Redis..."

if ! sudo ss -ltnp | grep -q ':6379'; then
    sudo systemctl restart redis-server 2>/dev/null || sudo service redis-server restart
else
    echo "⚠️ Redis port already in use → skipping restart"
fi

# -----------------------------
# HEALTH CHECK
# -----------------------------
echo "🧠 Running system check..."

echo ""
echo "📊 SYSTEM STATUS"
echo "------------------------"

sudo ss -ltnp | grep nginx || true
sudo fail2ban-client status || true
sudo fail2ban-client status nginx-ddos || true

echo ""
echo "🛡 Anti-DDoS v3.4 PORT GUARD READY"
echo ""
echo "🔥 ACTIVE CONFIG:"
echo "Nginx Port: $NGINX_PORT"
echo ""
echo "👉 Commands:"
echo "  sudo ss -ltnp | grep :80"
echo "  sudo ss -ltnp | grep nginx"
echo "  sudo fail2ban-client status nginx-ddos"