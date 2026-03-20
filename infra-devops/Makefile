# Makefile
include .env
export

# 1. Initialize (Run this once or when adding new modules)
init:
	docker compose run --rm terraform -c "terraform init \
		-backend-config='bucket=$(TERRAFORM_BUCKET)' \
		-backend-config='region=$(AWS_DEFAULT_REGION)' \
		-backend-config='dynamodb_table=$(TF_STATE_LOCK_TABLE)'"

# 2. Quality Check (Junior must run this before every PR)
check:
	docker compose run --rm terraform -c "terraform fmt -recursive && tflint --init && tflint"

# 3. Plan (The Preview)
plan:
	docker compose run --rm terraform -c "terraform plan -out=tfplan"

# 4. Apply (The Execution)
apply:
	docker compose run --rm terraform -c "terraform apply tfplan"

# 5. Destroy (Careful!)
destroy:
	docker compose run --rm terraform -c "terraform destroy"