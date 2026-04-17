# 🚀 Anti-DDoS v3 Production System (EC2 + Nginx + Fail2Ban + Redis)

A multi-layer protection system for Laravel / API / SaaS infrastructure running on AWS EC2 + Docker.

---

# 🧠 Architecture

L1: Nginx Rate Limiting (fast drop)
L2: Fail2Ban (IP banning)
L3: Redis IP Reputation (behavior tracking)
L4: Laravel Middleware (API protection)
L5: AWS Security Group (final defense)

---

# ⚡ Features

- Block bot traffic at Nginx level
- Auto-ban abusive IPs via Fail2Ban
- Track IP reputation using Redis
- API-level rate limiting (Laravel)
- Docker-safe EC2 deployment
- Production-ready defaults

---

# 🚀 Quick Install

```bash
chmod +x setup-antiddos-v3.sh
sudo ./setup-antiddos-v3.sh