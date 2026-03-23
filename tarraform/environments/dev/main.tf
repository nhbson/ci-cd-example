provider "aws" {
  region = var.region
}

resource "aws_security_group" "crm_sg" {
  name = "crm-sg"

  ingress {
    from_port = 80
    to_port   = 80
    protocol  = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port = 22
    to_port   = 22
    protocol  = "tcp"
    cidr_blocks = ["0.0.0.0/0"] # for training only
  }

  egress {
    from_port = 0
    to_port   = 0
    protocol  = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_instance" "crm_server" {
  ami           = var.ami
  instance_type = "t2.micro"   # FREE TIER
  key_name      = var.key_name

  vpc_security_group_ids = [aws_security_group.crm_sg.id]

  user_data = <<-EOF
              #!/bin/bash
              yum update -y
              amazon-linux-extras install docker -y
              service docker start
              usermod -a -G docker ec2-user

              curl -L "https://github.com/docker/compose/releases/download/2.23.3/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
              chmod +x /usr/local/bin/docker-compose

              # Create app folder
              mkdir -p /home/ec2-user/app
              cd /home/ec2-user/app

              # Create docker-compose.yml
              cat <<EOT > docker-compose.yml
              version: '3.8'
              services:
                app:
                  image: php:8.2-fpm
                  container_name: app
                  volumes:
                    - ./app:/var/www/html

                nginx:
                  image: nginx:latest
                  ports:
                    - "80:80"
                  volumes:
                    - ./app:/var/www/html
                    - ./nginx.conf:/etc/nginx/conf.d/default.conf
                  depends_on:
                    - app

                db:
                  image: mysql:8
                  environment:
                    MYSQL_ROOT_PASSWORD: password
                    MYSQL_DATABASE: crm
                  ports:
                    - "3306:3306"
              EOT

              # Create nginx config
              cat <<EOT > nginx.conf
              server {
                listen 80;
                root /var/www/html;
                index index.php index.html;

                location / {
                  try_files $uri $uri/ /index.php?$query_string;
                }

                location ~ \.php$ {
                  fastcgi_pass app:9000;
                  include fastcgi_params;
                }
              }
              EOT

              mkdir app
              echo "<?php phpinfo(); ?>" > app/index.php

              docker-compose up -d
              EOF

  tags = {
    Name = "CRM-Free-Tier"
  }
}

output "public_ip" {
  value = aws_instance.crm_server.public_ip
}