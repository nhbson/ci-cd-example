# 🚀 DevOps Starter Guide: Docker + Jenkins + GitHub Auto Deploy (Laravel)

## 🎯 Goal

This guide helps you set up:

✅ Docker environment
✅ Jenkins (CI/CD)
✅ Laravel app container
✅ GitHub → Jenkins → Auto Deploy

---

# 🧱 System Overview

```
Developer → GitHub → Webhook → Jenkins → Docker → Laravel App → Nginx → User
```

---

# ⚙️ Prerequisites

* Ubuntu server (EC2 or VPS)
* Public IP (IMPORTANT ⚠️)
* GitHub repository (Laravel project)

---

# 🚀 Step 1: Run Setup Script

### 1. Create file

```bash
nano setup.sh
```

Paste the script → save.

---

### 2. Make executable

```bash
chmod +x setup.sh
```

---

### 3. Run

```bash
./setup.sh
```

---

# 📦 What This Script Installs

* Docker
* Docker Compose
* Jenkins container
* Nginx container
* Laravel (PHP-FPM) container
* MySQL database

---

# 🌐 Access Services

| Service | URL                        |
| ------- | -------------------------- |
| Jenkins | http://YOUR_SERVER_IP:8080 |
| Laravel | http://YOUR_SERVER_IP      |

---

# 🔐 Step 2: Setup Jenkins

## 1. Open Jenkins

```
http://YOUR_SERVER_IP:8080
```

Get password:

```bash
docker exec jenkins cat /var/jenkins_home/secrets/initialAdminPassword
```

---

## 2. Install Plugins

Go to:

```
Manage Jenkins → Plugins
```

Install:

* Git Plugin
* GitHub Integration Plugin
* Pipeline Plugin

---

# 🔗 Step 3: Connect GitHub

## 1. Create Pipeline Job

```
New Item → Pipeline → laravel-deploy
```

---

## 2. Enable Auto Trigger

Scroll to:

```
Build Triggers
```

Enable:

```
✔ GitHub hook trigger for GITScm polling
```

---

# 🌍 Step 4: Setup GitHub Webhook

Go to GitHub:

```
Repo → Settings → Webhooks → Add webhook
```

### Set:

* Payload URL:

```
http://YOUR_PUBLIC_IP:8080/github-webhook/
```

⚠️ MUST be public (NOT localhost)

---

* Content type:

```
application/json
```

---

# ⚙️ Step 5: Add Jenkins Pipeline

Paste this in Jenkins:

```groovy
pipeline {
    agent any

    stages {

        stage('Clone Code') {
            steps {
                git branch: 'main', url: 'https://github.com/YOUR_REPO.git'
            }
        }

        stage('Deploy') {
            steps {
                sh '''
                docker cp . laravel_app:/var/www
                docker exec laravel_app composer install
                docker exec laravel_app php artisan migrate --force
                docker exec laravel_app php artisan config:cache
                '''
            }
        }
    }
}
```

---

# 🧪 Step 6: Test Auto Deploy

Push code:

```bash
git add .
git commit -m "test deploy"
git push origin main
```

---

## ✅ Expected Result

* GitHub sends webhook
* Jenkins triggers build
* Laravel auto updates

---

# 🔍 Troubleshooting

## ❌ Webhook not working

* Do NOT use:

```
http://localhost:8080 ❌
```

Use:

```
http://PUBLIC_IP:8080 ✅
```

---

## ❌ Build not triggered

Check:

* Jenkins job has trigger enabled
* GitHub webhook shows **200 OK**

---

## ❌ App not updated

Run manually:

```bash
docker exec -it laravel_app bash
```

---

# 🔥 Important Notes

* `/github-webhook/` belongs to Jenkins (not Laravel)
* It only **triggers build**, not deploy directly
* Jenkins pipeline does the real work

---

# 🚀 Beginner Tips

* Always test with small commits
* Check Jenkins logs if something fails
* Do NOT edit production containers manually

---

# 🧠 Summary

You now have:

✅ Docker-based environment
✅ Jenkins CI/CD
✅ GitHub auto deploy
✅ Laravel running in container

---

# 📈 Next Steps (Recommended)

After this works, learn:

* Add SSL (HTTPS)
* Use domain (ci.yourdomain.com)
* Secure Jenkins (important)
* Improve deployment (no downtime)

---

# 🎉 Done!

You’ve built your first **real DevOps pipeline** 🚀
