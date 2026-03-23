provider "aws" {
  region = "ap-southeast-1"
  profile = "default"              # optional, if using AWS CLI profile
}

# 1️⃣ Security Group
resource "aws_security_group" "web_sg" {
  name = "web-sg"

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# 2️⃣ EC2 Instance
#resource "aws_instance" "my_server" {
#  ami           = "ami-0df7a207adb9748c7"
#  instance_type = "t2.micro"
#
#  vpc_security_group_ids = [aws_security_group.web_sg.id]
#
#  tags = {
#    Name = "dev-server"
#  }
#}

#module "ec2" {
#  source = "../../modules/ec2"
#
#  name           = "dev-server"
#  instance_type  = "t2.micro"
#}

#terraform {
#  required_providers {
#    aws = {
#      source  = "hashicorp/aws"
#      version = "~> 5.0"
#    }
#  }
#  required_version = ">= 1.5.0"
#}

resource "aws_instance" "my_server" {
  ami           = "ami-0df7a207adb9748c7"
  instance_type = "t2.micro"

  key_name = aws_key_pair.deployer.key_name
  vpc_security_group_ids = [aws_security_group.web_sg.id]

  user_data = <<-EOF
            #!/bin/bash
            # --------------------------
            # Update system & install dependencies
            # --------------------------
            yum update -y
            amazon-linux-extras install docker -y
            service docker start
            systemctl enable docker
            usermod -a -G docker ec2-user

            # Install Docker Compose
            curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
            chmod +x /usr/local/bin/docker-compose

            # Install git & unzip for Laravel project
            yum install -y git unzip zip curl

            # --------------------------
            # Create project folder
            # --------------------------
            mkdir -p /home/ec2-user/www
            cd /home/ec2-user/www

            # --------------------------
            # Clone your Laravel project
            # --------------------------
            git clone https://github.com/YOUR_USERNAME/YOUR_LARAVEL_REPO.git .
            # Replace YOUR_USERNAME/YOUR_LARAVEL_REPO

            # --------------------------
            # Create Dockerfile
            # --------------------------
            cat <<EOT > Dockerfile
            FROM php:8.3-cli

            WORKDIR /var/www

            # Install system dependencies
            RUN apt-get update && apt-get install -y \\
                git curl zip unzip \\
                libssl-dev zlib1g-dev libcurl4-openssl-dev pkg-config build-essential autoconf \\
                && docker-php-ext-install pdo pdo_mysql pcntl

            # Install Swoole
            RUN pecl install swoole && docker-php-ext-enable swoole

            # Install Redis extension
            RUN pecl install redis && docker-php-ext-enable redis

            # Copy Laravel project
            COPY ./www .

            CMD ["php", "-v"]
            EOT

            # --------------------------
            # Create Docker Compose file
            # --------------------------
            cat <<EOT > docker-compose.yml
            version: '3'

            services:
            nginx:
                image: nginx:latest
                ports:
                - "8000:80"
                volumes:
                - ./www:/var/www
                - ./nginx/default.conf:/etc/nginx/conf.d/default.conf
                depends_on:
                - app1
                - app2

            app1:
                build: .
                working_dir: /var/www
                command: php artisan octane:start --server=swoole --host=0.0.0.0 --port=8000
                volumes:
                - ./www:/var/www
                depends_on:
                - redis
                - mysql

            app2:
                build: .
                working_dir: /var/www
                command: php artisan octane:start --server=swoole --host=0.0.0.0 --port=8000
                volumes:
                - ./www:/var/www
                depends_on:
                - redis
                - mysql

            mysql:
                image: mysql:8
                environment:
                MYSQL_ROOT_PASSWORD: root
                MYSQL_DATABASE: app
                ports:
                - "3308:3306"

            redis:
                image: redis:7
                ports:
                - "6379:6379"

            soketi:
                image: quay.io/soketi/soketi:latest
                ports:
                - "6001:6001"
                environment:
                SOKETI_DEFAULT_APP_ID: "app-id"
                SOKETI_DEFAULT_APP_KEY: "app-key"
                SOKETI_DEFAULT_APP_SECRET: "app-secret"
                SOKETI_REDIS_HOST: redis

            queue:
                build: .
                working_dir: /var/www
                command: php artisan queue:work
                volumes:
                - ./www:/var/www
                depends_on:
                - redis
                - mysql
            EOT

            # --------------------------
            # Create Nginx config
            # --------------------------
            mkdir -p nginx
            cat <<EOT > nginx/default.conf
            upstream backend {
                least_conn;
                server app1:8000;
                server app2:8000;
            }

            map "\$binary_remote_addr\$http_user_agent" \$limit_key {
                default \$binary_remote_addr\$http_user_agent;
            }

            limit_req_zone \$limit_key zone=api_limit:10m rate=10r/s;

            server {
                listen 80;

                location /api/ {
                    limit_req zone=api_limit burst=20 nodelay;

                    proxy_pass http://backend;
                    proxy_http_version 1.1;
                    proxy_set_header Connection "";
                    proxy_set_header Host \$host;
                    proxy_set_header X-Real-IP \$remote_addr;
                    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
                    proxy_set_header X-Forwarded-Proto \$scheme;

                    if (\$http_user_agent ~* "(curl|wget|python|bot|crawler)") {
                        return 403 "Forbidden\\n";
                    }
                }

                location / {
                    proxy_pass http://backend;
                    proxy_http_version 1.1;
                    proxy_set_header Connection "";
                    proxy_set_header Host \$host;
                    proxy_set_header X-Real-IP \$remote_addr;
                    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
                }

                location /app {
                    proxy_pass http://soketi:6001;
                    proxy_http_version 1.1;
                    proxy_set_header Upgrade \$http_upgrade;
                    proxy_set_header Connection "Upgrade";
                    proxy_set_header Host \$host;
                    proxy_set_header X-Real-IP \$remote_addr;
                    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
                }

                error_page 429 = @too_many_requests;
                location @too_many_requests {
                    return 429 "Too Many Requests\\n";
                }
            }
            EOT

            # --------------------------
            # Start all containers
            # --------------------------
            /usr/local/bin/docker-compose up -d
            EOF

  tags = {
    Name = "dev-server"
  }
}