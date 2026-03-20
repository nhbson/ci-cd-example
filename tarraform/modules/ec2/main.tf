resource "aws_instance" "this" {
  ami           = "ami-0df7a207adb9748c7"
  instance_type = var.instance_type

  tags = {
    Name = var.name
  }
}