resource "aws_instance" "crm" {
  instance_type = "t2.micro"
  ami           = var.ami
  key_name      = var.key_name

  user_data = <<-EOF
              #!/bin/bash
              yum update -y
              amazon-linux-extras install docker -y
              service docker start
              usermod -a -G docker ec2-user

              curl -L https://github.com/docker/compose/releases/download/2.23.3/docker-compose-linux-x86_64 -o /usr/local/bin/docker-compose
              chmod +x /usr/local/bin/docker-compose

              yum install git -y

              cd /home/ec2-user
              git clone https://github.com/YOUR_REPO/crm-devops.git
              cd crm-devops

              docker-compose up -d
              EOF
}