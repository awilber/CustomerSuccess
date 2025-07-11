#\!/bin/bash
apt-get update
apt-get install -y docker.io docker-compose git curl

# Start Docker
systemctl start docker
systemctl enable docker
usermod -aG docker ubuntu

# Install Docker Compose
curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Clone repository
cd /home/ubuntu
git clone https://github.com/awilber/CustomerSuccess.git
cd CustomerSuccess

# Set up environment
cat > .env << 'ENVEOF'
FLASK_ENV=production
SECRET_KEY=production-secret-key-change-me
DATABASE_URL=postgresql://postgres:password@db:5432/customersuccess
ENVEOF

# Start application
docker-compose up -d

# Set ownership
chown -R ubuntu:ubuntu /home/ubuntu/CustomerSuccess
EOF < /dev/null