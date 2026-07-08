#!/bin/bash
# Think IT Telugu - VPS AI Deployment Setup Script
# Restrict deployments strictly to this directory. NEVER touch `/opt` or other projects!

set -e

echo "===================================================="
echo "Starting Think IT Telugu AI Service Deployment..."
echo "===================================================="

# 1. Update package database
echo "[1/6] Updating system packages..."
sudo apt-get update -y

# 2. Check if Docker is installed, if not, install it
if ! command -v docker &> /dev/null; then
    echo "[2/6] Docker not found. Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    rm get-docker.sh
else
    echo "[2/6] Docker is already installed."
fi

# Install Docker Compose plugin if missing
if ! docker compose version &> /dev/null; then
    echo "Installing Docker Compose plugin..."
    sudo apt-get install -y docker-compose-plugin
fi

# 3. Install Nginx and Certbot
echo "[3/6] Installing Nginx and Certbot..."
sudo apt-get install -y nginx certbot python3-certbot-nginx

# 4. Configure Nginx Server Block for ai.thinkittelugu.in
echo "[4/6] Configuring Nginx reverse proxy..."
NGINX_CONF="/etc/nginx/sites-available/ai.thinkittelugu.in"

sudo bash -c "cat > \$NGINX_CONF" << 'EOF'
server {
    listen 80;
    server_name ai.thinkittelugu.in;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;

        # Disable buffering to support Server-Sent Events (SSE) streaming correctly
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_buffering off;
        proxy_cache off;
        chunked_transfer_encoding on;
        proxy_read_timeout 24h;
    }
}
EOF

# Enable the configuration
if [ ! -f /etc/nginx/sites-enabled/ai.thinkittelugu.in ]; then
    sudo ln -s \$NGINX_CONF /etc/nginx/sites-enabled/
fi

# Remove default site if it exists to avoid conflicts
if [ -f /etc/nginx/sites-enabled/default ]; then
    sudo rm /etc/nginx/sites-enabled/default
fi

# Test and reload Nginx
sudo nginx -t
sudo systemctl reload nginx

# 5. Build and launch Docker services
echo "[5/6] Building and running Docker containers..."
# Copy env file template if actual .env does not exist yet
if [ ! -f .env ]; then
    cp .env.example .env
fi
sudo docker compose down || true
sudo docker compose up -d --build

# 6. Pull Qwen 2.5 3B model inside Ollama container
echo "[6/6] Downloading Qwen 2.5 (3B) model inside Ollama (this might take a few minutes)..."
sudo docker exec -i ollama ollama pull qwen2.5:3b

echo "===================================================="
echo "Deployment successful!"
echo "AI Service is running on http://localhost:8000"
echo "Ollama is running on http://localhost:11434"
echo "===================================================="
echo "Next Steps:"
echo "1. Verify your DNS mapping points ai.thinkittelugu.in to this server IP."
echo "2. Run this command manually to configure SSL: sudo certbot --nginx -d ai.thinkittelugu.in"
echo "3. Run build_rag_index.py locally to upload your documentation data."
echo "===================================================="
