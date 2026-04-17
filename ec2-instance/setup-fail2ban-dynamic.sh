#!/bin/bash
# setup-fail2ban-dynamic.sh
# Production-ready Fail2Ban for Nginx + EC2 + Docker-safe

set -e

LOG_FILE="/var/log/fail2ban-banned-ips.log"
JAIL_NAME="nginx-loadtest"
FILTER_NAME="nginx-loadtest"
ROTATE_CONF="/etc/logrotate.d/fail2ban-banned-ips"

echo "🔥 Installing Fail2Ban dependencies..."

sudo apt update -y
sudo apt install fail2ban mailutils jq -y

# -----------------------------
# 1. CREATE FILTER (SAFE NGINX LOG MATCH)
# -----------------------------
echo "🛠 Creating Fail2Ban filter..."

sudo tee /etc/fail2ban/filter.d/${FILTER_NAME}.conf > /dev/null <<'EOF'
[Definition]
failregex = ^<HOST> -.*"(GET|POST|HEAD).*HTTP/.*" (401|403|404|429|500|502|503|504)
ignoreregex =
EOF

# -----------------------------
# 2. CLEAN OLD JAIL CONFIG
# -----------------------------
echo "🧹 Preparing jail configuration..."

sudo touch /etc/fail2ban/jail.local

# remove old jail section safely
sudo sed -i "/\[$JAIL_NAME\]/,/^$/d" /etc/fail2ban/jail.local || true

# -----------------------------
# 3. CREATE JAIL (PRODUCTION SAFE)
# -----------------------------
echo "⚙️ Writing jail configuration..."

sudo tee -a /etc/fail2ban/jail.local > /dev/null <<EOF

[$JAIL_NAME]
enabled = true
port = http,https
filter = $FILTER_NAME
logpath = /var/log/nginx/access.log

# SECURITY THRESHOLDS
maxretry = 20
findtime = 60
bantime = 900

# SAFE WHITELIST (DO NOT USE DYNAMIC DOCKER IPs)
ignoreip = 127.0.0.1/8 ::1

# ACTION
action = %(action_mwl)s

allowipv6 = auto
EOF

# -----------------------------
# 4. LOG FILE SETUP
# -----------------------------
echo "📄 Ensuring log file exists..."

sudo touch $LOG_FILE
sudo chmod 644 $LOG_FILE

# -----------------------------
# 5. LOG ROTATION
# -----------------------------
echo "📦 Setting up log rotation..."

sudo tee $ROTATE_CONF > /dev/null <<EOF
$LOG_FILE {
    daily
    rotate 30
    compress
    missingok
    notifempty
    create 644 root root
}
EOF

# -----------------------------
# 6. START FAIL2BAN SAFELY
# -----------------------------
echo "🚀 Starting Fail2Ban..."

sudo systemctl enable fail2ban
sudo systemctl restart fail2ban

# Wait for daemon ready
echo "⏳ Waiting for Fail2Ban..."
for i in {1..10}; do
    if sudo fail2ban-client ping >/dev/null 2>&1; then
        echo "✅ Fail2Ban is ready"
        break
    fi
    sleep 1
done

# -----------------------------
# 7. RELOAD CONFIG
# -----------------------------
echo "🔄 Reloading Fail2Ban..."
sudo fail2ban-client reload || true

# -----------------------------
# 8. STATUS CHECK
# -----------------------------
echo "📊 Fail2Ban Status:"
sudo fail2ban-client status || true
sudo fail2ban-client status $JAIL_NAME || echo "⚠️ Jail not active (check nginx logs)"

# -----------------------------
# 9. OPTIONAL WHITELIST SCRIPT (SAFE MODE)
# -----------------------------
echo "🧰 Creating whitelist updater..."

sudo tee /usr/local/bin/fail2ban-update-whitelist.sh > /dev/null <<'EOF'
#!/bin/bash

JAIL_NAME="nginx-loadtest"

# SAFE MODE ONLY (DO NOT USE DYNAMIC DOCKER IPs IN PRODUCTION)
WHITELIST="127.0.0.1/8 ::1"

echo "Updating ignoreip..."

sudo sed -i "/\[$JAIL_NAME\]/,/^$/ s|^ignoreip =.*|ignoreip = $WHITELIST|" /etc/fail2ban/jail.local

echo "Reloading Fail2Ban..."
sudo fail2ban-client reload

echo "Done."
EOF

sudo chmod +x /usr/local/bin/fail2ban-update-whitelist.sh

# -----------------------------
# 10. DONE
# -----------------------------
echo "🛡 Fail2Ban setup completed successfully!"
echo ""
echo "📄 Log file: $LOG_FILE"
echo "📌 Jail: $JAIL_NAME"
echo ""
echo "👉 Useful commands:"
echo "  sudo fail2ban-client status $JAIL_NAME"
echo "  sudo fail2ban-client status"
echo "  sudo tail -f /var/log/fail2ban.log"
echo "  sudo /usr/local/bin/fail2ban-update-whitelist.sh"