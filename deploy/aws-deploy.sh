#!/bin/bash

# AWS Deployment Script for CustomerSuccess
# This script sets up an EC2 instance with Docker and deploys the application

set -e

# Configuration
APP_NAME="customer-success"
INSTANCE_TYPE="t3.medium"
KEY_NAME="customer-success-key"
SECURITY_GROUP="customer-success-sg"
AMI_ID="ami-0c7217cdde317cfec"  # Ubuntu 22.04 LTS
REGION="us-west-2"

echo "🚀 Starting AWS deployment for CustomerSuccess..."

# Check if AWS CLI is configured
if ! aws sts get-caller-identity > /dev/null 2>&1; then
    echo "❌ AWS CLI not configured. Please run 'aws configure' first."
    exit 1
fi

# Create key pair if it doesn't exist
if ! aws ec2 describe-key-pairs --key-names $KEY_NAME --region $REGION > /dev/null 2>&1; then
    echo "📄 Creating EC2 key pair..."
    aws ec2 create-key-pair --key-name $KEY_NAME --region $REGION --query 'KeyMaterial' --output text > ${KEY_NAME}.pem
    chmod 400 ${KEY_NAME}.pem
    echo "✅ Key pair created: ${KEY_NAME}.pem"
fi

# Create security group if it doesn't exist
if ! aws ec2 describe-security-groups --group-names $SECURITY_GROUP --region $REGION > /dev/null 2>&1; then
    echo "🔒 Creating security group..."
    SECURITY_GROUP_ID=$(aws ec2 create-security-group \
        --group-name $SECURITY_GROUP \
        --description "Security group for CustomerSuccess application" \
        --region $REGION \
        --query 'GroupId' --output text)
    
    # Add inbound rules
    aws ec2 authorize-security-group-ingress \
        --group-id $SECURITY_GROUP_ID \
        --protocol tcp --port 22 --cidr 0.0.0.0/0 \
        --region $REGION
    
    aws ec2 authorize-security-group-ingress \
        --group-id $SECURITY_GROUP_ID \
        --protocol tcp --port 80 --cidr 0.0.0.0/0 \
        --region $REGION
    
    aws ec2 authorize-security-group-ingress \
        --group-id $SECURITY_GROUP_ID \
        --protocol tcp --port 443 --cidr 0.0.0.0/0 \
        --region $REGION
    
    echo "✅ Security group created: $SECURITY_GROUP_ID"
else
    SECURITY_GROUP_ID=$(aws ec2 describe-security-groups \
        --group-names $SECURITY_GROUP \
        --region $REGION \
        --query 'SecurityGroups[0].GroupId' --output text)
fi

# Create user data script
cat > user-data.sh << 'EOF'
#!/bin/bash
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
EOF

# Launch EC2 instance
echo "🚀 Launching EC2 instance..."
INSTANCE_ID=$(aws ec2 run-instances \
    --image-id $AMI_ID \
    --count 1 \
    --instance-type $INSTANCE_TYPE \
    --key-name $KEY_NAME \
    --security-group-ids $SECURITY_GROUP_ID \
    --user-data file://user-data.sh \
    --region $REGION \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$APP_NAME},{Key=Project,Value=CustomerSuccess}]" \
    --query 'Instances[0].InstanceId' --output text)

echo "⏳ Waiting for instance to be running..."
aws ec2 wait instance-running --instance-ids $INSTANCE_ID --region $REGION

# Get public IP
PUBLIC_IP=$(aws ec2 describe-instances \
    --instance-ids $INSTANCE_ID \
    --region $REGION \
    --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)

echo ""
echo "🎉 Deployment completed!"
echo "📋 Instance Details:"
echo "   Instance ID: $INSTANCE_ID"
echo "   Public IP: $PUBLIC_IP"
echo "   SSH Access: ssh -i ${KEY_NAME}.pem ubuntu@$PUBLIC_IP"
echo ""
echo "🌐 Application will be available at:"
echo "   http://$PUBLIC_IP"
echo ""
echo "⏰ Note: It may take 5-10 minutes for the application to be fully ready."
echo "💡 Monitor deployment: ssh -i ${KEY_NAME}.pem ubuntu@$PUBLIC_IP 'docker-compose logs -f'"

# Clean up
rm user-data.sh

echo ""
echo "🔧 Next steps:"
echo "1. Upload your credentials.json file to the instance"
echo "2. Configure your domain name to point to $PUBLIC_IP"
echo "3. Set up SSL certificates if needed"
echo "4. Update environment variables in production"