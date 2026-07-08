# Think IT Telugu - AI Server

This repository contains the backend and deployment configuration for hosting an open-weight AI model (Qwen 2.5) with RAG capabilities on a Hostinger VPS.

## Contents
- `vps-backend/`: FastAPI backend with RAG (vector search) capability.
- `docker-compose.yml`: Docker Compose configuration for running Ollama and FastAPI.
- `setup_vps.sh`: Script to automate server installation, Nginx config, Docker set up, and Let's Encrypt SSL.
- `build_rag_index.py`: Local script to parse docs and populate RAG database.
