# Deployment Guide

This directory contains deployment configurations for the CustomerSuccess application.

## AWS Deployment

### Prerequisites

1. **AWS CLI installed and configured**:
   ```bash
   aws configure
   ```

2. **Required permissions**:
   - EC2 full access
   - VPC read access
   - IAM read access

### Quick Deployment

```bash
# Deploy to AWS
./deploy/aws-deploy.sh
```

This script will:
- Create EC2 key pair
- Set up security group
- Launch t3.medium instance
- Install Docker and Docker Compose
- Clone and start the application

### Manual Deployment

1. **Launch EC2 instance** (Ubuntu 22.04 LTS)
2. **Connect via SSH**:
   ```bash
   ssh -i your-key.pem ubuntu@your-instance-ip
   ```

3. **Install dependencies**:
   ```bash
   sudo apt update
   sudo apt install -y docker.io docker-compose git
   sudo systemctl start docker
   sudo systemctl enable docker
   sudo usermod -aG docker ubuntu
   ```

4. **Clone and deploy**:
   ```bash
   git clone https://github.com/awilber/CustomerSuccess.git
   cd CustomerSuccess
   docker-compose up -d
   ```

## Docker Deployment

### Local Development

```bash
# Build and run locally
docker-compose up --build
```

### Production Deployment

```bash
# Set environment variables
export SECRET_KEY="your-production-secret"
export GOOGLE_CLIENT_ID="your-google-client-id"
export GOOGLE_CLIENT_SECRET="your-google-client-secret"

# Deploy with production settings
docker-compose -f docker-compose.yml up -d
```

## Environment Variables

### Required for Production

```bash
FLASK_ENV=production
SECRET_KEY=your-secret-key
DATABASE_URL=postgresql://user:pass@host:port/dbname
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
```

### Optional

```bash
REDIS_URL=redis://localhost:6379/0
SENTRY_DSN=your-sentry-dsn
AWS_ACCESS_KEY_ID=your-aws-key
AWS_SECRET_ACCESS_KEY=your-aws-secret
```

## SSL Certificate Setup

### Using Let's Encrypt

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Generate certificate
sudo certbot --nginx -d yourdomain.com

# Auto-renewal
sudo crontab -e
# Add: 0 12 * * * /usr/bin/certbot renew --quiet
```

### Using Custom Certificates

Place your certificates in `deploy/ssl/`:
- `cert.pem` - Certificate file
- `key.pem` - Private key file

## Monitoring and Logs

### Application Logs

```bash
# View application logs
docker-compose logs -f app

# View database logs
docker-compose logs -f db

# View nginx logs
docker-compose logs -f nginx
```

### Health Checks

- **Application**: `http://your-domain/health`
- **Database**: Built into Docker Compose
- **Nginx**: Built into Docker Compose

### Performance Monitoring

The application includes built-in monitoring endpoints:
- `/metrics` - Application metrics
- `/health` - Health check
- `/debug` - Debug information (development only)

## Scaling

### Horizontal Scaling

```bash
# Scale application containers
docker-compose up -d --scale app=3
```

### Database Scaling

For production, consider:
- AWS RDS PostgreSQL
- Google Cloud SQL
- Managed database services

### Load Balancing

Update `nginx.conf` to include multiple upstream servers:

```nginx
upstream app {
    server app1:5000;
    server app2:5000;
    server app3:5000;
}
```

## Backup and Recovery

### Database Backup

```bash
# Backup database
docker-compose exec db pg_dump -U postgres customersuccess > backup.sql

# Restore database
docker-compose exec -T db psql -U postgres customersuccess < backup.sql
```

### File Backup

```bash
# Backup uploaded files
docker run --rm -v customer-success_uploads_data:/data -v $(pwd):/backup ubuntu tar czf /backup/uploads-backup.tar.gz -C /data .

# Restore uploaded files
docker run --rm -v customer-success_uploads_data:/data -v $(pwd):/backup ubuntu tar xzf /backup/uploads-backup.tar.gz -C /data
```

## Troubleshooting

### Common Issues

1. **Port already in use**: Change ports in `docker-compose.yml`
2. **Database connection failed**: Check DATABASE_URL
3. **Google OAuth not working**: Verify credentials and redirect URIs
4. **File upload errors**: Check disk space and permissions

### Debug Commands

```bash
# Check container status
docker-compose ps

# Check container logs
docker-compose logs [service_name]

# Access container shell
docker-compose exec app /bin/bash

# Check disk usage
df -h
docker system df
```

## Security Considerations

### Production Checklist

- [ ] Change default passwords
- [ ] Set strong SECRET_KEY
- [ ] Enable HTTPS
- [ ] Configure firewall
- [ ] Regular security updates
- [ ] Database access restrictions
- [ ] File upload size limits
- [ ] Rate limiting enabled

### Backup Strategy

- Daily database backups
- Weekly full system backups
- Test restore procedures
- Off-site backup storage