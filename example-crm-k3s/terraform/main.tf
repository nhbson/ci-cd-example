provider "aws" {
  region = var.region
}

resource "aws_key_pair" "ec2_key" {
  key_name   = var.key_name
  public_key = file(var.public_key_path)
}

resource "aws_security_group" "allow_ssh_http" {
  name   = "allow_ssh_http"
  vpc_id = data.aws_vpc.default.id

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
    from_port   = 30000
    to_port     = 32767
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

data "aws_vpc" "default" {
  default = true
}

resource "aws_instance" "k3s_node" {
  ami           = var.ami
  instance_type = "t2.micro"
  key_name      = aws_key_pair.ec2_key.key_name
  security_groups = [aws_security_group.allow_ssh_http.name]

  user_data = <<-EOF
              #!/bin/bash
              yum update -y
              amazon-linux-extras install docker -y
              systemctl start docker
              systemctl enable docker

              curl -sfL https://get.k3s.io | sh -

              export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
              mkdir -p /home/ec2-user/crm-k3s
              cd /home/ec2-user/crm-k3s
              git clone https://github.com/YOUR_GITHUB_REPO/crm-k3s.git .
              bash k3s/deploy.sh
              EOF
}