MINIKUBE_PROFILE := minikube
GKE_CLUSTER := voxoff-cluster
GCP_REGION := us-central1
GCP_PROJECT := bda-karaoke-app
DOCKER_REGISTRY := us-central1-docker.pkg.dev

# Get absolute path to the project root (one level up from this Makefile)
PROJECT_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))..)
SA_CREDS_PATH ?= $(PROJECT_ROOT)/voxoff-sa-creds.json

.PHONY: deploy-minikube deploy-gke teardown-minikube teardown-gke setup-minikube reset-docker-env create-gke-cluster

# ---------- Deployment Targets ----------

deploy-minikube: setup-minikube
	@echo "Applying Terraform for Minikube..."
	cd "$(PROJECT_ROOT)/terraform" && terraform apply -auto-approve -var-file=environments/minikube.tfvars

deploy-gke: create-gke-cluster
	cd "$(PROJECT_ROOT)/terraform" && terraform apply -auto-approve -var-file=environments/gke.tfvars

# ---------- Teardown Targets ----------

teardown-minikube: reset-docker-env
	cd "$(PROJECT_ROOT)/terraform" && terraform destroy -var-file=environments/minikube.tfvars -auto-approve
	minikube delete --profile $(MINIKUBE_PROFILE)

teardown-gke:
	cd "$(PROJECT_ROOT)/terraform" && terraform destroy -var-file=environments/gke.tfvars -auto-approve
	@gcloud container clusters delete $(GKE_CLUSTER) \
		--region=$(GCP_REGION) --quiet || true

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
		echo "❌ Service account key not found at: $(SA_CREDS_PATH)"; \
		exit 1; \
	fi

	kubectl create secret docker-registry regcred \
		--docker-server=$(DOCKER_REGISTRY) \
		--docker-username=_json_key \
		--docker-password='$(shell cat "$(SA_CREDS_PATH)")' \
		--docker-email=unused@example.com \
		--namespace=default

reset-docker-env:
	@echo "Resetting Docker environment to system default..."
	@eval $$(minikube docker-env -u)

# ---------- GKE Cluster Creation ----------

create-gke-cluster:
	@if ! gcloud container clusters describe $(GKE_CLUSTER) --region $(GCP_REGION) --project $(GCP_PROJECT) > /dev/null 2>&1; then \
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
