variable "region" {
  default = "us-east-1"
}

variable "key_name" {
  default = "crm-k3s-key"
}

variable "public_key_path" {
  default = "~/.ssh/id_rsa.pub"
}

variable "ami" {
  default = "ami-0c02fb55956c7d316" # Amazon Linux 2 (us-east-1)
}