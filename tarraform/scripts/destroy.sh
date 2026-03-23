#!/bin/bash

echo "🔥 Destroying resources to avoid billing..."

cd terraform/dev
terraform destroy -auto-approve