#!/bin/bash
echo "🚀 Deploying Laravel CRM on k3s..."

export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

kubectl apply -f k8s-deployment.yml
kubectl apply -f ingress.yml

echo "✅ Deployment complete!"