# ContentFlow Pro - Complete Setup Guide

This guide will walk you through setting up ContentFlow Pro from scratch, including the license server.

---

## 📋 Table of Contents

1. [System Prerequisites](#system-prerequisites)
2. [Installing Dependencies](#installing-dependencies)
3. [Setting Up License Server](#setting-up-license-server)
4. [Configuring Client Application](#configuring-client-application)
5. [First Run](#first-run)
6. [Generating Test Licenses](#generating-test-licenses)
7. [Testing the System](#testing-the-system)
8. [Production Deployment](#production-deployment)

---

## 1. System Prerequisites

### Required Software

- **Python 3.8+**: [Download](https://www.python.org/downloads/)
- **FFmpeg**: [Download](https://ffmpeg.org/download.html)
- **yt-dlp**: Installed via pip
- **Git** (optional): For cloning repository

### Operating System Support

- ✅ Windows 10/11
- ✅ macOS 10.15+
- ✅ Linux (Ubuntu 20.04+, Debian, Fedora)

---

## 2. Installing Dependencies

### Step 2.1: Install System Dependencies

#### Windows

1. **Install Python**:
   - Download from [python.org](https://www.python.org/downloads/)
   - Check "Add Python to PATH" during installation
   - Verify: `python --version`

2. **Install FFmpeg**:
   - Download from [ffmpeg.org](https://ffmpeg.org/download.html)
   - Extract to `C:\ffmpeg`
   - Add `C:\ffmpeg\bin` to system PATH
   - Verify: `ffmpeg -version`

#### macOS

```bash
# Install Homebrew (if not installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install dependencies
brew install python3 ffmpeg

# Verify
python3 --version
ffmpeg -version
```

#### Linux (Ubuntu/Debian)

```bash
# Update package list
sudo apt update

# Install dependencies
sudo apt install -y python3 python3-pip python3-venv ffmpeg git

# Verify
python3 --version
ffmpeg -version
```

### Step 2.2: Clone Repository

```bash
# Clone repository
git clone https://github.com/toseeq44/automation-fb.git
cd automation-fb
```

Or download ZIP from GitHub and extract.

### Step 2.3: Create Virtual Environment (Recommended)

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate

# On macOS/Linux:
source venv/bin/activate
```

### Step 2.4: Install Python Dependencies

```bash
# Install client dependencies
pip install -r requirements.txt

# Verify installation
pip list
```

---

## 3. Setting Up License Server

### Step 3.1: Install Server Dependencies

```bash
cd server
pip install -r requirements.txt
cd ..
```

### Step 3.2: Configure Server

```bash
cd server

# Copy example environment file
cp .env.example .env

# Edit .env file
nano .env  # or use your preferred editor
```

Edit `.env`:

```env
# Flask Configuration
SECRET_KEY=YOUR_SUPER_SECRET_KEY_HERE_CHANGE_THIS
DEBUG=False
PORT=5000

# Database Configuration
DATABASE_URL=sqlite:///licenses.db

# Admin Configuration (for generating licenses)
ADMIN_KEY=YOUR_ADMIN_SECRET_KEY_CHANGE_THIS
```

**Important**: Change `SECRET_KEY` and `ADMIN_KEY` to random secure values!

### Step 3.3: Start License Server

```bash
# Make sure you're in the server directory
cd server

# Start server
python app.py
```

You should see:

```
    ╔════════════════════════════════════════════════════════════╗
    ║   ContentFlow Pro License Server                           ║
    ║   Running on: http://localhost:5000                        ║
    ║   Debug Mode: False                                        ║
    ╚════════════════════════════════════════════════════════════╝

✅ Database tables created successfully
 * Serving Flask app 'app'
 * Running on http://0.0.0.0:5000
```

**Leave this terminal open** - the server needs to keep running.

### Step 3.4: Verify Server

Open a new terminal and test:

```bash
curl http://localhost:5000/api/health
```

Expected response:
```json
{
  "status": "healthy",
  "timestamp": "2024-10-23T14:30:00"
}
```

---

## 4. Configuring Client Application

### Step 4.1: Update License Server URL

If your license server is running on a different machine or port, update the config:

```bash
# Open config directory (will be created on first run)
# On Windows: C:\Users\YourName\.contentflow\
# On macOS/Linux: ~/.contentflow/

# Edit config.json
nano ~/.contentflow/config.json
```

Update license server URL:

```json
{
  "license": {
    "server_url": "http://localhost:5000"
  }
}
```

**For remote server**:
```json
{
  "license": {
    "server_url": "https://your-license-server.com"
  }
}
```

---

## 5. First Run

### Step 5.1: Launch Application

Open a **new terminal** (keep server running in the first one):

```bash
# Activate virtual environment (if using one)
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Run application
python main.py
```

### Step 5.2: Activation Dialog

On first run, you'll see the **License Activation Dialog**.

You have two options:

1. **Enter an existing license key** (if you have one)
2. **Generate a test license** (see next section)

---

## 6. Generating Test Licenses

### Step 6.1: Generate License via API

Open another terminal:

```bash
# Generate a 7-day trial license
curl -X POST http://localhost:5000/api/admin/generate \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "plan_type": "trial",
    "admin_key": "YOUR_ADMIN_SECRET_KEY_CHANGE_THIS"
  }'
```

**Replace** `YOUR_ADMIN_SECRET_KEY_CHANGE_THIS` with the admin key from your `.env` file.

Response:
```json
{
  "success": true,
  "license_key": "CFPRO-A1B2-C3D4-E5F6-G7H8",
  "email": "test@example.com",
  "plan_type": "trial",
  "expiry_date": "2024-10-30T14:30:00",
  "message": "License generated successfully"
}
```

Copy the `license_key` value.

### Step 6.2: Generate Different Plans

**Monthly Plan** (30 days):
```bash
curl -X POST http://localhost:5000/api/admin/generate \
  -H "Content-Type: application/json" \
  -d '{
    "email": "customer@example.com",
    "plan_type": "monthly",
    "admin_key": "YOUR_ADMIN_KEY"
  }'
```

**Yearly Plan** (365 days):
```bash
curl -X POST http://localhost:5000/api/admin/generate \
  -H "Content-Type: application/json" \
  -d '{
    "email": "customer@example.com",
    "plan_type": "yearly",
    "admin_key": "YOUR_ADMIN_KEY"
  }'
```

### Step 6.3: Activate Generated License

1. Copy the license key from the response
2. Go back to the activation dialog in the app
3. Paste the license key
4. Click **"Activate License"**
5. Done! ✅

---

## 7. Testing the System

### Test 7.1: Test Activation

1. Launch app: `python main.py`
2. Enter a test license key
3. Click "Activate License"
4. Verify: You should see "✅ Active (X days remaining)" in status bar

### Test 7.2: Test Validation

```bash
# Get hardware ID
python -c "from modules.license.hardware_id import generate_hardware_id; print(generate_hardware_id())"

# Test validation
curl -X POST http://localhost:5000/api/license/validate \
  -H "Content-Type: application/json" \
  -d '{
    "license_key": "YOUR_LICENSE_KEY",
    "hardware_id": "YOUR_HARDWARE_ID"
  }'
```

### Test 7.3: Test Deactivation

1. In app, click on license status in status bar
2. Click "Deactivate License"
3. Confirm deactivation
4. License should be removed

### Test 7.4: Test Offline Mode

1. Activate a license (with server running)
2. Stop the license server
3. Restart the app
4. Should work offline (grace period)
5. Check logs at `~/.contentflow/logs/`

### Test 7.5: Test License Expiry

1. Generate a trial license
2. Activate it
3. Wait 7 days or manually change expiry in database
4. App should show expiry warning

---

## 8. Production Deployment

### For License Server

#### Option A: Deploy to Heroku

```bash
cd server

# Login to Heroku
heroku login

# Create app
heroku create your-app-name

# Set environment variables
heroku config:set SECRET_KEY=your_secret_key
heroku config:set ADMIN_KEY=your_admin_key
heroku config:set DEBUG=False

# Add PostgreSQL
heroku addons:create heroku-postgresql:mini

# Deploy
git push heroku main
```

#### Option B: Deploy to VPS

See `server/README.md` for detailed VPS deployment instructions.

### For Client Application

#### Option A: Distribute Python Script

1. Share repository with customers
2. Provide setup instructions
3. Customers run `python main.py`

#### Option B: Create Executable (PyInstaller)

```bash
# Install PyInstaller
pip install pyinstaller

# Create executable
pyinstaller --onefile --windowed \
  --name ContentFlowPro \
  --icon icon.ico \
  main.py

# Executable in dist/ folder
```

#### Option C: Create Installer (Inno Setup for Windows)

See documentation for creating installers.

---

## 🔧 Configuration Options

### Client Configuration

File: `~/.contentflow/config.json`

```json
{
  "app": {
    "theme": "dark",
    "language": "en"
  },
  "license": {
    "server_url": "http://localhost:5000",
    "grace_period_days": 3
  },
  "paths": {
    "downloads": "~/Downloads/ContentFlow",
    "edited_videos": "~/Videos/ContentFlow",
    "temp": "~/.contentflow/temp",
    "cache": "~/.contentflow/cache"
  },
  "rate_limiting": {
    "enabled": true,
    "preset": "balanced",
    "batch_size": 20,
    "delay_seconds": 2.0
  },
  "downloader": {
    "default_quality": "1080p",
    "concurrent_downloads": 3,
    "auto_retry": true,
    "max_retries": 3
  },
  "editor": {
    "default_format": "mp4",
    "default_codec": "h264",
    "default_quality": "high",
    "hardware_acceleration": true
  },
  "logging": {
    "enabled": true,
    "level": "INFO",
    "keep_days": 30
  }
}
```

### Server Configuration

File: `server/.env`

```env
SECRET_KEY=your-super-secret-key
DEBUG=False
PORT=5000
DATABASE_URL=sqlite:///licenses.db
ADMIN_KEY=your-admin-secret-key
```

---

## 📝 Database Management

### View All Licenses (SQLite)

```bash
cd server
sqlite3 licenses.db

# List all licenses
SELECT license_key, email, plan_type, expiry_date, is_active FROM licenses;

# Exit
.quit
```

### Backup Database

```bash
# Backup SQLite database
cp server/licenses.db server/licenses.db.backup

# Restore
cp server/licenses.db.backup server/licenses.db
```

---

## 🐛 Common Issues

### Issue: "Unable to connect to license server"

**Solution**: Check if license server is running at the correct URL.

```bash
# Check server status
curl http://localhost:5000/api/health
```

### Issue: "Module not found" errors

**Solution**: Install missing dependencies.

```bash
pip install -r requirements.txt
```

### Issue: FFmpeg not found

**Solution**: Install FFmpeg and add to PATH.

**Verify**:
```bash
ffmpeg -version
```

### Issue: Database locked

**Solution**: Close all connections to database, restart server.

---

## ✅ Checklist

- [ ] Python 3.8+ installed
- [ ] FFmpeg installed and in PATH
- [ ] Repository cloned
- [ ] Virtual environment created and activated
- [ ] Client dependencies installed
- [ ] Server dependencies installed
- [ ] Server `.env` configured
- [ ] License server running
- [ ] Test license generated
- [ ] Application launched successfully
- [ ] License activated
- [ ] All features accessible

---

## 🆘 Getting Help

If you encounter issues:

1. Check logs at `~/.contentflow/logs/`
2. Review this setup guide
3. Check server logs (terminal output)
4. Contact support: 0307-7361139

---

**Setup complete! Enjoy ContentFlow Pro! 🎉**
