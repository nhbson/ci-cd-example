# 🔥 Dynamic Fail2Ban Setup for Nginx + Docker + AWS EC2

Protect your Nginx server from brute-force attacks with **Fail2Ban** while automatically whitelisting Docker containers, localhost, and optional AWS IPs.

This guide is beginner-friendly with step numbers, emojis, and clickable references.

---

## 🎯 Objective

1. Protect Nginx from brute-force attacks
2. Automatically whitelist safe IPs (localhost, Docker, AWS)
3. Send email alerts when malicious activity is detected
4. Update whitelist dynamically when new Docker containers start

---

## 🛠 Prerequisites

* Ubuntu EC2 server
* Nginx installed
* Docker installed
* `sudo` privileges
* (Optional) AWS CLI configured for Elastic IP detection
* Valid email address for alerts

---

## 1️⃣ Upload the Script

Copy the script to your EC2 server:

```bash
scp setup-fail2ban-dynamic.sh ubuntu@YOUR_EC2_IP:/home/ubuntu/
```

---

## 2️⃣ Make Script Executable

```bash
chmod +x setup-fail2ban-dynamic.sh
```

---

## 3️⃣ Edit Email Variable

Open the script and set your email for alerts:

```bash
nano setup-fail2ban-dynamic.sh
# Change:
EMAIL_ALERT="your-email@example.com"
```

---

## 4️⃣ Run the Script

```bash
sudo ./setup-fail2ban-dynamic.sh
```

✅ **What the script does:**

* Installs Fail2Ban, `mailutils`, and `jq`
* Detects Docker IPs dynamically
* (Optional) Detects AWS public IPs
* Creates a custom Nginx filter for HTTP 429/500 errors
* Configures a Fail2Ban jail: `nginx-loadtest`
* Sets up log file `/var/log/fail2ban-banned-ips.log`
* Configures daily log rotation (keep 30 days, compressed)
* Provides helper script `/usr/local/bin/fail2ban-update-whitelist.sh`

---

## 5️⃣ Post-Setup Commands

| ✅ Task                                 | 🖥 Command                                         |
| -------------------------------------- | -------------------------------------------------- |
| Check Fail2Ban status                  | `sudo fail2ban-client status nginx-loadtest`       |
| Refresh whitelist after Docker changes | `sudo /usr/local/bin/fail2ban-update-whitelist.sh` |
| View banned IPs log                    | `cat /var/log/fail2ban-banned-ips.log`             |
| Restart Fail2Ban                       | `sudo systemctl restart fail2ban`                  |

---

## 6️⃣ How It Works

### 🔹 Dynamic IP Detection

* **Docker IPs** – Whitelisted automatically
* **AWS IPs** – Optional; whitelist Elastic IPs if AWS CLI configured

### 🔹 Fail2Ban Jail

* Jail name: `nginx-loadtest`
* Monitored logs: `/var/log/nginx/access.log`
* Max retries: `100`
* Find time: `60 seconds`
* Ban time: `600 seconds (10 min)`
* Whitelisted IPs: localhost, Docker IPs, AWS IPs

### 🔹 Log Rotation

* File: `/var/log/fail2ban-banned-ips.log`
* Rotate daily, keep 30 days
* Compressed automatically

### 🔹 Dynamic Whitelist Script

* Path: `/usr/local/bin/fail2ban-update-whitelist.sh`
* Updates `ignoreip` dynamically when Docker containers start
* Reloads Fail2Ban automatically

---

## 7️⃣ Tips for Juniors

* ✅ Verify that email alerts are working
* ✅ Docker whitelist updates automatically; AWS requires configuration if needed
* ✅ Backup `/etc/fail2ban/jail.local` before making changes
* ✅ Adjust `maxretry`, `findtime`, and `bantime` based on traffic

---

## 📄 References (Clickable)

* [Fail2Ban Official Documentation](https://www.fail2ban.org/wiki/index.php/Main_Page)
* [Logrotate Manual](https://linux.die.net/man/8/logrotate)
* [Docker Network Inspect](https://docs.docker.com/engine/reference/commandline/network_inspect/)

---

## 💡 Quick Command Summary

```bash
# Check Fail2Ban status
sudo fail2ban-client status nginx-loadtest

# Refresh whitelist after new Docker containers
sudo /usr/local/bin/fail2ban-update-whitelist.sh

# View banned IPs
cat /var/log/fail2ban-banned-ips.log

# Restart Fail2Ban
sudo systemctl restart fail2ban
```

---

🎉 **Congratulations! Dynamic Fail2Ban is now fully set up.**
