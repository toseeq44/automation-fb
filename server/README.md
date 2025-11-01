# ContentFlow Pro License Server

Backend API server for managing license activation, validation, and subscription management.

## Features

- ✅ License activation with hardware binding
- ✅ License validation with 3-day offline grace period
- ✅ License deactivation for device transfers
- ✅ Admin license generation
- ✅ Security logging and alerts
- ✅ Rate limiting protection
- ✅ SQLite/PostgreSQL support

## Installation

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env` and update values:

```bash
cp .env.example .env
```

Edit `.env`:
```
SECRET_KEY=your-super-secret-key-here
DEBUG=False
PORT=5000
DATABASE_URL=sqlite:///licenses.db
```

### 3. Run Server

```bash
python app.py
```

Server will start on `http://localhost:5000`

## API Endpoints

### 1. Health Check
```http
GET /api/health
```

Response:
```json
{
  "status": "healthy",
  "timestamp": "2025-10-23T14:30:00"
}
```

### 2. Activate License
```http
POST /api/license/activate
Content-Type: application/json

{
  "license_key": "CFPRO-XXXX-XXXX-XXXX-XXXX",
  "hardware_id": "sha256_hash",
  "device_name": "John's PC"
}
```

Response (Success):
```json
{
  "success": true,
  "message": "License activated successfully on John's PC",
  "plan_type": "monthly",
  "expiry_date": "2025-11-23T14:30:00",
  "days_remaining": 30
}
```

Response (Error - Already Activated):
```json
{
  "success": false,
  "message": "License is already activated on \"John's PC\". Deactivate it first to use on this device."
}
```

### 3. Validate License
```http
POST /api/license/validate
Content-Type: application/json

{
  "license_key": "CFPRO-XXXX-XXXX-XXXX-XXXX",
  "hardware_id": "sha256_hash"
}
```

Response:
```json
{
  "valid": true,
  "is_expired": false,
  "expiry_date": "2025-11-23T14:30:00",
  "plan_type": "monthly",
  "days_remaining": 30,
  "message": "License is valid"
}
```

### 4. Deactivate License
```http
POST /api/license/deactivate
Content-Type: application/json

{
  "license_key": "CFPRO-XXXX-XXXX-XXXX-XXXX",
  "hardware_id": "sha256_hash"
}
```

Response:
```json
{
  "success": true,
  "message": "License deactivated successfully. You can now activate it on another device."
}
```

### 5. Get License Status
```http
POST /api/license/status
Content-Type: application/json

{
  "license_key": "CFPRO-XXXX-XXXX-XXXX-XXXX"
}
```

Response:
```json
{
  "success": true,
  "license_key": "CFPRO-XXXX-XXXX-XXXX-XXXX",
  "email": "user@example.com",
  "plan_type": "monthly",
  "purchase_date": "2025-10-23T14:30:00",
  "expiry_date": "2025-11-23T14:30:00",
  "device_name": "John's PC",
  "is_active": true,
  "is_expired": false,
  "is_suspended": false,
  "days_remaining": 30,
  "last_validation": "2025-10-23T14:30:00"
}
```

### 6. Generate License (Admin Only)
```http
POST /api/admin/generate
Content-Type: application/json

{
  "email": "customer@example.com",
  "plan_type": "monthly",
  "admin_key": "CFPRO_ADMIN_2024_SECRET"
}
```

Plan types: `monthly` (30 days), `yearly` (365 days), `trial` (7 days)

Response:
```json
{
  "success": true,
  "license_key": "CFPRO-A1B2-C3D4-E5F6-G7H8",
  "email": "customer@example.com",
  "plan_type": "monthly",
  "expiry_date": "2025-11-23T14:30:00",
  "message": "License generated successfully"
}
```

## Database Schema

### Licenses Table
- `id` - Primary key
- `license_key` - Unique license key (indexed)
- `email` - Customer email
- `plan_type` - monthly/yearly/trial
- `purchase_date` - When license was created
- `expiry_date` - When license expires
- `hardware_id` - Hardware fingerprint (null until activated)
- `device_name` - Device name
- `is_active` - Active status
- `is_suspended` - Suspended status
- `activation_count` - Number of activations
- `last_validation` - Last validation timestamp
- `created_at` - Creation timestamp
- `updated_at` - Last update timestamp

### Validation Logs Table
- `id` - Primary key
- `license_key` - Foreign key to licenses
- `hardware_id` - Hardware ID used
- `ip_address` - Request IP
- `action` - activate/validate/deactivate
- `status` - success/failed/suspicious
- `message` - Log message
- `timestamp` - When action occurred

### Security Alerts Table
- `id` - Primary key
- `license_key` - Foreign key to licenses
- `alert_type` - Type of alert
- `description` - Alert details
- `severity` - low/medium/high/critical
- `is_resolved` - Resolution status
- `created_at` - Alert timestamp

## Security Features

### 1. Hardware Binding
- Each license can only be activated on ONE device at a time
- Hardware ID is a SHA-256 hash of multiple hardware components
- Device transfer requires deactivation first

### 2. Rate Limiting
- Global: 200 requests per day, 50 per hour
- API endpoints: 10 requests per minute
- Prevents brute force attacks

### 3. Activity Logging
- All activation/validation/deactivation attempts logged
- IP addresses recorded
- Failed attempts tracked

### 4. Security Alerts
- Automatic alerts for suspicious activity
- Multiple device attempts
- Hardware ID mismatches
- Rapid validation attempts

## Deployment

### Production Deployment (Heroku Example)

1. **Create Heroku app:**
```bash
heroku create cfpro-license-server
```

2. **Set environment variables:**
```bash
heroku config:set SECRET_KEY=your-secret-key
heroku config:set DEBUG=False
heroku config:set ADMIN_KEY=your-admin-key
```

3. **Add PostgreSQL:**
```bash
heroku addons:create heroku-postgresql:mini
```

4. **Deploy:**
```bash
git push heroku main
```

### Production Deployment (VPS Example)

1. **Install dependencies:**
```bash
sudo apt update
sudo apt install python3 python3-pip nginx certbot
pip3 install -r requirements.txt gunicorn
```

2. **Create systemd service** (`/etc/systemd/system/cfpro-license.service`):
```ini
[Unit]
Description=ContentFlow Pro License Server
After=network.target

[Service]
User=www-data
WorkingDirectory=/var/www/cfpro-license
Environment="PATH=/var/www/cfpro-license/venv/bin"
ExecStart=/var/www/cfpro-license/venv/bin/gunicorn -w 4 -b 127.0.0.1:5000 app:app

[Install]
WantedBy=multi-user.target
```

3. **Configure Nginx** (`/etc/nginx/sites-available/cfpro-license`):
```nginx
server {
    listen 80;
    server_name license.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

4. **Enable HTTPS with Let's Encrypt:**
```bash
sudo certbot --nginx -d license.yourdomain.com
```

5. **Start service:**
```bash
sudo systemctl enable cfpro-license
sudo systemctl start cfpro-license
```

## Testing

### Generate Test License
```bash
curl -X POST http://localhost:5000/api/admin/generate \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "plan_type": "trial",
    "admin_key": "CFPRO_ADMIN_2024_SECRET"
  }'
```

### Test Activation
```bash
curl -X POST http://localhost:5000/api/license/activate \
  -H "Content-Type: application/json" \
  -d '{
    "license_key": "CFPRO-XXXX-XXXX-XXXX-XXXX",
    "hardware_id": "test_hardware_id_12345",
    "device_name": "Test Device"
  }'
```

## Monitoring

Monitor the following:
- Database size and growth
- Failed validation attempts
- Security alerts
- Server resource usage
- API response times

## Backup

### SQLite Backup
```bash
cp licenses.db licenses.db.backup
```

### PostgreSQL Backup
```bash
pg_dump cfpro_licenses > backup.sql
```

## Support

For issues or questions:
- Email: support@contentflowpro.com
- GitHub: https://github.com/toseeq44/automation-fb

## License

Proprietary - All rights reserved
