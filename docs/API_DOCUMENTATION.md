# CustomerSuccess API Documentation

## Overview

The CustomerSuccess API provides programmatic access to customer relationship management functionality for real estate professionals. The API follows RESTful conventions and returns JSON responses.

## Base URL

```
http://localhost:5000
```

## Authentication

Currently, the API uses session-based authentication. Users must log in through the web interface to access API endpoints.

## API Endpoints

### Customer Management

#### List Customers
```http
GET /customers
```

**Response:**
```json
{
  "customers": [
    {
      "id": 1,
      "name": "HCR",
      "created_at": "2023-01-01T00:00:00Z",
      "updated_at": "2023-01-01T00:00:00Z"
    }
  ]
}
```

#### Get Customer Details
```http
GET /customers/{customer_id}
```

**Response:**
```json
{
  "id": 1,
  "name": "HCR",
  "people": [
    {
      "id": 1,
      "name": "John Doe",
      "email": "john@example.com",
      "side": "customer"
    }
  ],
  "email_count": 150,
  "created_at": "2023-01-01T00:00:00Z"
}
```

#### Create Customer
```http
POST /customers/add
```

**Request Body:**
```json
{
  "name": "New Customer",
  "description": "Customer description"
}
```

**Response:**
```json
{
  "id": 2,
  "name": "New Customer",
  "message": "Customer created successfully"
}
```

### Embeddings API

#### Get Email Statistics
```http
GET /embeddings/api/customer/{customer_id}/stats
```

**Query Parameters:**
- `senders[]` (optional): Filter by sender email addresses
- `recipients[]` (optional): Filter by recipient email addresses

**Response:**
```json
{
  "2024": {
    "total": 150,
    "with_embeddings": 75,
    "months": {
      "1": {
        "total": 25,
        "with_embeddings": 12
      },
      "2": {
        "total": 30,
        "with_embeddings": 18
      }
    }
  }
}
```

#### Get Email Addresses
```http
GET /embeddings/api/customer/{customer_id}/email-addresses
```

**Response:**
```json
{
  "senders": [
    "john@wiredtriangle.com",
    "jane@knewvantage.com"
  ],
  "recipients": [
    "client@example.com",
    "partner@realestate.com"
  ]
}
```

#### Process Embeddings
```http
POST /embeddings/api/customer/{customer_id}/process
```

**Request Body:**
```json
{
  "year": 2024,
  "month": 12,
  "senders": ["john@wiredtriangle.com"],
  "recipients": ["client@example.com"],
  "embedding_method": "openai"
}
```

**Response:**
```json
{
  "task_id": "customer_1_1640995200",
  "message": "Started processing 25 emails",
  "total_emails": 25
}
```

#### Get Processing Status
```http
GET /embeddings/api/task/{task_id}/status
```

**Response:**
```json
{
  "task_id": "customer_1_1640995200",
  "status": "completed",
  "progress": 100,
  "processed": 25,
  "errors": 0,
  "skipped": 0,
  "duration": 2.5,
  "start_time": 1640995200.0,
  "end_time": 1640995202.5
}
```

#### Cancel Processing
```http
POST /embeddings/api/task/{task_id}/cancel
```

**Response:**
```json
{
  "message": "Task cancelled"
}
```

#### Get Topics
```http
GET /embeddings/api/customer/{customer_id}/topics
```

**Response:**
```json
{
  "main_topics": [
    {
      "name": "property valuation",
      "count": 15,
      "emails": [1, 2, 3, 4, 5]
    },
    {
      "name": "market analysis",
      "count": 12,
      "emails": [6, 7, 8, 9]
    }
  ],
  "sub_topics": [
    {
      "name": "residential appraisal",
      "count": 8,
      "emails": [1, 2, 3]
    }
  ],
  "total_emails": 100,
  "processed_emails": 75
}
```

#### Extract Topics
```http
POST /embeddings/api/customer/{customer_id}/extract-topics
```

**Request Body:**
```json
{
  "max_main_topics": 10,
  "max_sub_topics": 20
}
```

**Response:**
```json
{
  "main_topics": [...],
  "sub_topics": [...],
  "total_emails": 100,
  "processed_emails": 75
}
```

### Analytics API

#### Get Timeline Data
```http
GET /analytics/api/timeline/{customer_id}
```

**Query Parameters:**
- `person` (optional): Filter by person name
- `start_date` (optional): Start date (YYYY-MM-DD)
- `end_date` (optional): End date (YYYY-MM-DD)
- `view_mode` (optional): 'user' or 'topic'
- `senders[]` (optional): Filter by sender email addresses
- `recipients[]` (optional): Filter by recipient email addresses
- `main_topics[]` (optional): Filter by main topics
- `sub_topics[]` (optional): Filter by sub topics

**Response:**
```json
{
  "time_bins": ["2024-01-01", "2024-01-08", "2024-01-15"],
  "bin_type": "week",
  "total_emails": 45,
  "customer_senders": ["client@example.com"],
  "us_senders": ["john@wiredtriangle.com"],
  "volume_data": {
    "2024-01-01": {
      "customer": {
        "client@example.com": 5
      },
      "us": {
        "john@wiredtriangle.com": 3
      },
      "total_customer": 5
    }
  },
  "individual_emails": [
    {
      "date": "2024-01-01",
      "sender": "john@wiredtriangle.com",
      "subject": "Property Inquiry",
      "preview": "Following up on the property...",
      "time_bin": "2024-01-01"
    }
  ]
}
```

### File Upload API

#### Upload Google Takeout
```http
POST /uploads/google-takeout/{customer_id}
```

**Request:**
- Content-Type: multipart/form-data
- Field: `file` (ZIP file containing Google Takeout data)

**Response:**
```json
{
  "message": "Upload successful",
  "emails_imported": 150,
  "processing_time": 2.5
}
```

## Error Handling

The API uses standard HTTP status codes to indicate success or failure:

### Success Codes
- `200 OK` - Request successful
- `201 Created` - Resource created successfully

### Error Codes
- `400 Bad Request` - Invalid request parameters
- `401 Unauthorized` - Authentication required
- `403 Forbidden` - Insufficient permissions
- `404 Not Found` - Resource not found
- `500 Internal Server Error` - Server error

### Error Response Format
```json
{
  "error": "Error message description",
  "code": "ERROR_CODE",
  "details": {
    "field": "Additional error details"
  }
}
```

## Rate Limiting

Currently, no rate limiting is implemented. This may be added in future versions.

## Data Models

### Customer
```json
{
  "id": "integer",
  "name": "string",
  "description": "string",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

### Person
```json
{
  "id": "integer",
  "name": "string",
  "email": "string",
  "side": "string ('customer' or 'us')",
  "customer_id": "integer"
}
```

### EmailThread
```json
{
  "id": "integer",
  "subject": "string",
  "sender_email": "string",
  "recipient_email": "string",
  "date": "datetime",
  "body_preview": "string",
  "body_full": "string",
  "has_embedding": "boolean",
  "embedding": "string (JSON)",
  "embedding_model": "string",
  "embedding_processed_at": "datetime",
  "main_topics": "string (JSON array)",
  "sub_topics": "string (JSON array)",
  "customer_id": "integer"
}
```

## SDK Examples

### Python
```python
import requests

# Get customer statistics
response = requests.get(
    'http://localhost:5000/embeddings/api/customer/1/stats',
    params={'senders': ['john@wiredtriangle.com']}
)
stats = response.json()

# Process embeddings
response = requests.post(
    'http://localhost:5000/embeddings/api/customer/1/process',
    json={
        'year': 2024,
        'month': 12,
        'embedding_method': 'openai'
    }
)
task = response.json()
```

### JavaScript
```javascript
// Get customer statistics
const response = await fetch('/embeddings/api/customer/1/stats?senders=john@wiredtriangle.com');
const stats = await response.json();

// Process embeddings
const response = await fetch('/embeddings/api/customer/1/process', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
    },
    body: JSON.stringify({
        year: 2024,
        month: 12,
        embedding_method: 'openai'
    })
});
const task = await response.json();
```

### cURL
```bash
# Get customer statistics
curl -X GET "http://localhost:5000/embeddings/api/customer/1/stats?senders=john@wiredtriangle.com"

# Process embeddings
curl -X POST "http://localhost:5000/embeddings/api/customer/1/process" \
  -H "Content-Type: application/json" \
  -d '{
    "year": 2024,
    "month": 12,
    "embedding_method": "openai"
  }'
```

## Changelog

### Version 1.0.0
- Initial API release
- Customer management endpoints
- Embeddings processing endpoints
- Timeline analytics endpoints
- Google Takeout upload functionality

## Support

For API support and questions, please create an issue in the GitHub repository.