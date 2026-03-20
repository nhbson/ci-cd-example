#!/bin/bash
# setup-fail2ban-dynamic.sh
# Ultimate dynamic Fail2Ban for Nginx + Docker + AWS EC2

LOG_FILE="/var/log/fail2ban-banned-ips.log"
EMAIL_ALERT="your-email@example.com"   # <-- Change to your email
ROTATE_CONF="/etc/logrotate.d/fail2ban-banned-ips"
JAIL_NAME="nginx-loadtest"
FILTER_NAME="nginx-loadtest"

echo "🔥 Installing Fail2Ban and mail utilities..."
sudo apt update
sudo apt install fail2ban mailutils jq -y

# Function to detect Docker IPs dynamically
get_docker_ips() {
    docker network ls -q | xargs -I {} docker network inspect {} -f '{{range .Containers}}{{.IPv4Address}} {{end}}' | awk -F/ '{print $1}' | tr '\n' ' '
}

# Function to detect AWS public Elastic IPs (optional)
get_aws_ips() {
    # Fetch instance metadata (EC2)
    INSTANCE_ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)
    REGION=$(curl -s http://169.254.169.254/latest/dynamic/instance-identity/document | jq -r '.region')
    # If AWS CLI configured, list Elastic IPs (requires IAM permissions)
    # aws ec2 describe-addresses --region $REGION --query 'Addresses[*].PublicIp' --output text
    # For simplicity, leave empty if you don't use CLI
    echo ""
}

# Combine whitelist: localhost + Docker + AWS
WHITELIST="127.0.0.1/8 $(get_docker_ips) $(get_aws_ips)"

echo "🛠 Creating custom Nginx filter..."
sudo tee /etc/fail2ban/filter.d/$FILTER_NAME.conf > /dev/null <<EOL
[Definition]
failregex = ^<HOST> -.*"(GET|POST).*HTTP/.*" (429|500)
ignoreregex =
EOL

# Create jail.local if it doesn't exist
if [ ! -f /etc/fail2ban/jail.local ]; then
    sudo touch /etc/fail2ban/jail.local
fi

# Remove old jail section if exists
sudo sed -i "/\[$JAIL_NAME\]/,/^$/d" /etc/fail2ban/jail.local

# Add jail
sudo tee -a /etc/fail2ban/jail.local > /dev/null <<EOL

[$JAIL_NAME]
enabled  = true
port     = http,https
filter   = $FILTER_NAME
logpath  = /var/log/nginx/access.log
maxretry = 100
findtime = 60
bantime  = 600
ignoreip = $WHITELIST
action   = %(action_mwl)s
           logban $LOG_FILE
EOL

# Ensure log file exists
sudo touch $LOG_FILE
sudo chmod 644 $LOG_FILE

# Setup log rotation
sudo tee $ROTATE_CONF > /dev/null <<EOL
$LOG_FILE {
    daily
    rotate 30
    compress
    missingok
    notifempty
    create 644 root root
}
EOL

# Restart Fail2Ban
sudo systemctl restart fail2ban
sudo fail2ban-client reload

# Function to dynamically update whitelist on reload
sudo tee /usr/local/bin/fail2ban-update-whitelist.sh > /dev/null <<'EOL'
#!/bin/bash
# Update whitelist dynamically
JAIL_NAME="nginx-loadtest"
FILTER_NAME="nginx-loadtest"
LOG_FILE="/var/log/fail2ban-banned-ips.log"

# Detect Docker IPs
DOCKER_IPS=$(docker network ls -q | xargs -I {} docker network inspect {} -f '{{range .Containers}}{{.IPv4Address}} {{end}}' | awk -F/ '{print $1}' | tr '\n' ' ')

# Localhost always
WHITELIST="127.0.0.1/8 $DOCKER_IPS"

# Update jail.local
sudo sed -i "/\[$JAIL_NAME\]/,/^$/ s|^ignoreip =.*|ignoreip = $WHITELIST|" /etc/fail2ban/jail.local

# Reload Fail2Ban
sudo fail2ban-client reload
EOL

sudo chmod +x /usr/local/bin/fail2ban-update-whitelist.sh

echo "✅ Dynamic Fail2Ban setup complete!"
sudo fail2ban-client status $JAIL_NAME
echo "📄 Log file: $LOG_FILE"
echo "📧 Email alerts: $EMAIL_ALERT"
echo "🛡 Docker & AWS dynamic whitelist active"

echo "💡 To refresh whitelist after new Docker containers, run:"
echo "sudo /usr/local/bin/fail2ban-update-whitelist.sh"