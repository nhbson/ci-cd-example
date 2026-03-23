# Laravel Octane Terraform Deployment

This project provisions a **production-ready Laravel Octane stack** on AWS using Terraform.  
It includes:

- EC2 auto-provisioning
- Docker + Docker Compose
- Laravel Octane scaling (`app1` + `app2`) with Swoole
- Nginx load balancing with upstream and rate limiting
- MySQL 8 database
- Redis 7 for cache/queue
- Soketi WebSocket server
- Queue worker
- Dev/Prod environment separation
- Security group + SSH key
- Ready for scaling

---

## 📁 Folder Structure
terraform/
├── environments/
│ ├── dev/
│ │ ├── main.tf
│ │ ├── provider.tf
│ │ ├── variables.tf
│ │ ├── terraform.tfvars
│ │ └── user_data.sh
│ └── prod/
│ ├── main.tf
│ ├── provider.tf
│ ├── variables.tf
│ ├── terraform.tfvars
│ └── user_data.sh
└── modules/
└── ec2-laravel-octane/
├── main.tf
├── variables.tf
└── outputs.tf

---

## ⚡ Features

1. **Scaling Laravel Octane**: 2 containers (`app1` + `app2`) using Swoole  
2. **Nginx Load Balancing**: upstream with `least_conn`  
3. **API Rate Limiting**: per-IP + User-Agent, custom 429 response  
4. **Full Stack**: Laravel, MySQL, Redis, Soketi, Queue  
5. **Auto-Provisioning**: EC2 → Docker → Docker Compose → Laravel Octane stack  
6. **Dev/Prod Separation**: reuse same module for both environments  
7. **Security**: SSH access limited by IP, only necessary ports exposed  
8. **Outputs**: Public IP & DNS of EC2 instance

---

## 🛠 Prerequisites

1. **AWS Account** with programmatic access
2. **Terraform >= 1.5** installed
3. **AWS CLI configured**
4. **SSH Key** for EC2 (`~/.ssh/id_rsa.pub`)
5. **Git** installed (for Laravel project clone)

---

## 🚀 How to Deploy (Dev Environment)

1. Navigate to environment folder:

```bash
cd terraform/environments/dev
terraform init
terraform plan
terraform apply
```

Wait for EC2 instance creation and provisioning. Docker Compose will automatically start the Laravel Octane stack.

🔑 Access
```bash
SSH:

ssh ec2-user@<EC2_PUBLIC_IP>
```

Laravel App:
Open in browser:

http://<EC2_PUBLIC_IP>:8000

Soketi WebSocket: 6001

MySQL: 3308

Redis: 6379
---

🧱 How It Works

Terraform provisions EC2 instance with a security group + SSH key

user_data.sh runs on EC2 creation:

Installs Docker & Docker Compose

Clones Laravel project from GitHub

Creates Dockerfile for PHP + Swoole + Redis

Creates docker-compose.yml with all services

Creates Nginx config with upstream load balancing & API throttling

Starts all containers (docker-compose up -d)

Nginx routes traffic to app1/app2 containers

Laravel Octane handles high concurrency via Swoole

Queue worker runs in a separate container

Soketi handles WebSocket communication

🟡 Dev / Prod Environments

Dev: smaller instance (t3.medium), debug/testing

Prod: larger instance, ready for autoscaling, secure

Same Terraform module reused to avoid duplication

📌 Next Steps / Recommendations

Enable Auto Scaling for multiple EC2 instances

Use AWS ALB for routing traffic across multiple EC2 instances

Store MySQL data on EBS volumes for persistence

Secure environment variables using AWS Secrets Manager or Parameter Store

CI/CD Integration: automatically build and deploy Laravel Octane containers

Monitoring & Logs: CloudWatch + Nginx logs + Laravel logs

📝 Notes

Replace YOUR_USERNAME/YOUR_LARAVEL_REPO in user_data.sh with your actual GitHub repository

Replace YOUR_IP/32 in terraform.tfvars with your actual IP for SSH access

This setup is production-ready for single EC2 instance, horizontally scalable with ALB + Auto Scaling

💡 Useful Commands

Check running containers:

docker ps

View logs:

docker-compose logs -f

Restart containers:

docker-compose restart

Destroy environment:

terraform destroy