MINIKUBE_PROFILE := minikube
GKE_CLUSTER := voxoff-cluster
GCP_REGION := us-central1
GCP_PROJECT := bda-karaoke-app
DOCKER_REGISTRY := us-central1-docker.pkg.dev

# Get absolute path to the project root (one level up from this Makefile)
PROJECT_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))..)
SA_CREDS_PATH ?= $(PROJECT_ROOT)/voxoff-sa-creds.json

.PHONY: deploy-minikube deploy-gke teardown-minikube teardown-gke setup-minikube reset-docker-env create-gke-cluster init gke-auth print-usage

# ---------- Usage ----------

print-usage:
	@echo "Usage:"
	@echo "  make deploy-minikube     - Deploy app to Minikube"
	@echo "  make teardown-minikube   - Tear down Minikube deployment"
	@echo "  make deploy-gke          - Deploy app to GKE"
	@echo "  make teardown-gke        - Tear down GKE deployment"
	@echo "  make init                - Run 'terraform init'"
	@echo "  make gke-auth            - Fetch GKE credentials"
	@echo "  make reset-docker-env    - Reset Docker env to default"

# ---------- Deployment Targets ----------

deploy-minikube: setup-minikube
	@echo "Applying Terraform for Minikube..."
	cd "$(PROJECT_ROOT)/terraform" && terraform apply -auto-approve -var-file=environments/minikube.tfvars
	@echo "Minikube deployment complete."

deploy-gke: create-gke-cluster create-firestore-secret create-frontend-secret
	@echo "Applying Terraform for GKE..."
	cd "$(PROJECT_ROOT)/terraform" && terraform apply -auto-approve -var-file=environments/gke.tfvars
	@echo "GKE deployment complete."

# ---------- Frontend Env Secret ----------

create-frontend-secret:
	@if [ -z "$$GENIUS_API_KEY" ] || [ -z "$$GENIUS_SEARCH_URL" ] || [ -z "$$LASTFM_API_KEY" ] || [ -z "$$FLASK_SECRET" ]; then \
		echo "❌ One or more required environment variables are missing."; \
		echo "   Please set GENIUS_API_KEY, GENIUS_SEARCH_URL, LASTFM_API_KEY, and FLASK_SECRET."; \
		exit 1; \
	fi

	@echo "Creating 'frontend-env' secret in Kubernetes..."
	kubectl delete secret frontend-env --ignore-not-found --namespace=default
	kubectl create secret generic frontend-env \
		--from-literal=GENIUS_API_KEY="$$GENIUS_API_KEY" \
		--from-literal=GENIUS_SEARCH_URL="$$GENIUS_SEARCH_URL" \
		--from-literal=LASTFM_API_KEY="$$LASTFM_API_KEY" \
		--from-literal=FLASK_SECRET="$$FLASK_SECRET" \
		--namespace=default
	@echo "'frontend-env' secret created."


# ---------- Teardown Targets ----------

teardown-minikube: reset-docker-env
	@echo "Destroying Minikube resources..."
	cd "$(PROJECT_ROOT)/terraform" && terraform destroy -var-file=environments/minikube.tfvars -auto-approve
	minikube delete --profile $(MINIKUBE_PROFILE)
	@echo "Minikube cleaned up."

teardown-gke:
	@echo "Destroying GKE resources..."
	cd "$(PROJECT_ROOT)/terraform" && terraform destroy -var-file=environments/gke.tfvars -auto-approve
	@gcloud container clusters delete $(GKE_CLUSTER) \
		--region=$(GCP_REGION) --quiet || true
	@echo "GKE cluster deleted."

# ---------- Terraform Init ----------

init:
	@echo "Initializing Terraform..."
	cd "$(PROJECT_ROOT)/terraform" && terraform init
	@echo "Terraform initialized."

# ---------- GKE Auth ----------

gke-auth:
	@echo "Fetching credentials for GKE cluster '$(GKE_CLUSTER)'..."
	@gcloud container clusters get-credentials $(GKE_CLUSTER) --region=$(GCP_REGION) --project=$(GCP_PROJECT)
	@echo "Authenticated with GKE."

# ---------- Firestore Auth ----------
create-firestore-secret:
	@if [ ! -f "$(SA_CREDS_PATH)" ]; then \
		echo "❌ Service account key not found at: $(SA_CREDS_PATH)"; \
		exit 1; \
	fi

	@echo "Creating 'firestore-key' secret in Kubernetes..."
	kubectl delete secret firestore-key --ignore-not-found --namespace=default
	kubectl create secret generic firestore-key \
		--from-file=service-account.json="$(SA_CREDS_PATH)" \
		--namespace=default
	@echo "'firestore-key' secret created."


# ---------- Minikube Setup ----------

setup-minikube:
	@echo "Starting Minikube if not already running..."
	@if ! minikube status --profile $(MINIKUBE_PROFILE) | grep -q "host: Running"; then \
		minikube start --profile $(MINIKUBE_PROFILE); \
	else \
		echo "Minikube already running."; \
	fi

	@echo "Switching Docker daemon to Minikube..."
	@eval $$(minikube -p $(MINIKUBE_PROFILE) docker-env)

	@echo "Authenticating Docker to Google Artifact Registry..."
	@gcloud auth configure-docker $(DOCKER_REGISTRY) --quiet

	@echo "Recreating regcred secret in the default namespace..."
	@kubectl delete secret regcred --namespace=default --ignore-not-found

	@if [ ! -f "$(SA_CREDS_PATH)" ]; then \
		echo "Service account key not found at: $(SA_CREDS_PATH)"; \
		exit 1; \
	fi

	kubectl create secret docker-registry regcred \
		--docker-server=$(DOCKER_REGISTRY) \
		--docker-username=_json_key \
		--docker-password='$(shell cat "$(SA_CREDS_PATH)")' \
		--docker-email=unused@example.com \
		--namespace=default
	@echo "regcred secret created."

reset-docker-env:
	@echo "Resetting Docker environment to system default..."
	@eval $$(minikube docker-env -u)
	@echo "Docker environment reset."

# ---------- GKE Cluster Creation ----------

create-gke-cluster:
	@if ! gcloud container clusters list --filter="name=$(GKE_CLUSTER)" --format="value(name)" | grep -q "^$(GKE_CLUSTER)$$"; then \
		echo "GKE cluster '$(GKE_CLUSTER)' does not exist in project '$(GCP_PROJECT)'."; \
		read -p "Do you want to create it now? (y/N): " confirm; \
		if [ "$$confirm" = "y" ] || [ "$$confirm" = "Y" ]; then \
			echo "Creating GKE cluster..."; \
			gcloud container clusters create $(GKE_CLUSTER) \
				--region=$(GCP_REGION) \
				--project=$(GCP_PROJECT) \
				--num-nodes=1 \
				--quiet; \
		else \
			echo "Cluster creation aborted."; \
			exit 1; \
		fi \
	else \
		echo "GKE cluster '$(GKE_CLUSTER)' already exists."; \
	fi

	@echo "Fetching GKE credentials..."
	@gcloud container clusters get-credentials $(GKE_CLUSTER) \
		--region=$(GCP_REGION) \
		--project=$(GCP_PROJECT)
	@echo "GKE cluster credentials configured."
