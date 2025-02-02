# Transcribo Secure

Transcribo Secure is a microservices‑based transcription system designed for secure, scalable, and observable processing of audio and video files. It consists of multiple services—including a backend API, frontend UI, transcriber service, and an observability container (otel‑lgtm)—all orchestrated using Docker Compose and routed via Traefik.

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Directory Structure](#directory-structure)
- [Environment Configuration](#environment-configuration)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation and Setup](#installation-and-setup)
  - [Running the Services](#running-the-services)
- [Testing](#testing)
  - [Running the Test Suite](#running-the-test-suite)
- [Observability](#observability)
- [Contributing](#contributing)
- [License](#license)

## Architecture Overview

The system is divided into the following microservices:
- **Backend API:** Provides endpoints for file uploads, job management, transcription status, and viewer generation.
- **Frontend:** A NiceGUI‑based user interface for file uploads, vocabulary management, job monitoring, and an integrated editor.
- **Transcriber:** Handles polling for transcription jobs, audio processing (including ZIP extraction and merging), transcription via Whisper and diarization, and result uploads.
- **Otel‑lgtm:** An observability container that replaces the separate Prometheus and Grafana services to collect and display metrics using OTEL, Loki, Tempo, and Grafana.

Traefik is used as a reverse proxy and load balancer, with routing rules for each service (e.g., `api.localhost`, `app.localhost`, `transcriber.localhost`, and `otel.localhost`).

## Directory Structure

n-onsh-transcribo_secure/ ├── .env.example # Environment variables sample file ├── README.md # This file ├── docker-compose.yml # Docker Compose orchestration ├── backend-api/ │ ├── Dockerfile # Backend API service Dockerfile │ ├── requirements.txt # Python dependencies for the API │ └── src/ │ ├── config.py # Configuration loading (Pydantic settings) │ ├── main.py # API application entrypoint │ ├── middleware/ # Custom middlewares (e.g., file validation) │ ├── models/ # Data models for files, jobs, vocabulary │ ├── routes/ # API route definitions │ └── services/ # Business logic for DB, storage, etc. ├── frontend/ │ ├── Dockerfile # Frontend Dockerfile │ ├── requirements.txt # Frontend dependencies │ └── src/ │ ├── main.py # Main UI application using NiceGUI │ ├── components/ # UI components (e.g., editor) │ ├── services/ # API service wrappers │ └── utils.py # Utility functions (formatting, etc.) ├── transcriber/ │ ├── Dockerfile # Transcriber Dockerfile (using PyTorch with CUDA) │ ├── requirements.txt # Transcriber dependencies │ └── src/ │ ├── main.py # Transcriber service entrypoint │ ├── services/ # Transcription and audio processing logic │ └── utils/ # Metrics and helper functions ├── infrastructure/ │ └── docker/ │ ├── otel/ # OTEL configuration for the otel-lgtm container │ ├── grafana/ # (Old Grafana dashboards and provisioning, now replaced) │ ├── postgres/ # PostgreSQL initialization scripts │ └── ... # Other infrastructure configurations └── tests/ # Test suite for the project (see below)

## Environment Configuration

The project uses a `.env` file (or an `.env.example` file for reference) to configure all services. Key variables include:

- **Application Settings:** `ENVIRONMENT`, `HF_AUTH_TOKEN`
- **Database Settings:** `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- **MinIO Settings:** `MINIO_HOST`, `MINIO_PORT`, `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`
- **Azure KeyVault Settings:** `AZURE_KEYVAULT_URL`, `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`
- **Backend API Settings:** `BACKEND_API_URL`, `MAX_UPLOAD_SIZE`
- **Transcriber Settings:** `DEVICE`, `BATCH_SIZE`, `METRICS_PORT`
- **Frontend Settings:** `FRONTEND_PORT`, `REFRESH_INTERVAL`
- **Observability (OTEL):** `OTEL_LOG_LEVEL`, `OTEL_DATA_DIR`, `OTEL_COLLECTOR_CONFIG`

See the [`.env.example`](.env.example) file for full details.

## Getting Started

### Prerequisites

- Docker and Docker Compose
- Python 3.10 (for local testing/development)
- [pytest](https://docs.pytest.org/) for running the tests

### Installation and Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/n-onsh-transcribo_secure.git
   cd n-onsh-transcribo_secure

2. Copy the .env.example file to .env and update values as necessary:

cp .env.example .env

3. Build and start the services using Docker Compose:

    docker-compose up --build

Running the Services

    The Traefik dashboard is available at http://localhost:8080.
    The Backend API is available at https://api.localhost.
    The Frontend UI is available at https://app.localhost.
    The Transcriber Service will poll for jobs and update statuses automatically.
    The OTEL‑lgtm observability UI is available at https://otel.localhost.

Testing

We use pytest to run tests for configuration, API endpoints, middleware behavior, and service functionality.
Running the Test Suite

    Install pytest in your virtual environment:

pip install pytest

From the project root, run the tests (set PYTHONPATH so that modules can be imported correctly):

    PYTHONPATH=backend-api/src pytest tests/

Observability

The project uses an OTEL‑based observability container (otel‑lgtm) that collects metrics from your services. Make sure the OTEL‑related environment variables are set in your .env file. The otel‑lgtm container scrapes metrics (from endpoints such as /metrics) and displays dashboards via Grafana at https://otel.localhost.
Contributing

Contributions are welcome! Please follow these steps:

    Fork the repository.
    Create a feature branch.
    Write tests for your changes.
    Submit a pull request.

License

This project is licensed under the MIT License.