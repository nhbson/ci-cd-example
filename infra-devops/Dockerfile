# Dockerfile
FROM hashicorp/terraform:1.7.5

# Install AWS CLI and TFLint (Standard DevOps tools)
RUN apk add --no-cache aws-cli bash curl
RUN curl -s https://raw.githubusercontent.com/terraform-linters/tflint/master/install_linux.sh | bash

WORKDIR /workspace
ENTRYPOINT ["/bin/bash"]