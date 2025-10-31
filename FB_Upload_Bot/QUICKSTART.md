# Quick Start Guide - Facebook Upload Bot

Get up and running in 5 minutes! ⚡

## Prerequisites

✅ Windows 10/11
✅ Python 3.8+
✅ GoLogin or Incogniton browser installed

---

## Step 1: Install Dependencies (2 minutes)

```bash
cd FB_Upload_Bot
pip install -r requirements.txt
```

---

## Step 2: Configure Browser (1 minute)

Edit `config/settings.json`:

- Update browser paths if needed
- Verify debug ports (9222 for GoLogin, 9223 for Incogniton)

---

## Step 3: Set Up Your First Creator (1 minute)

### 3a. Create Creator Folder

```bash
# Create folder for your content
mkdir creators/MyFirstChannel
```

### 3b. Add Videos

Copy your videos to `creators/MyFirstChannel/`:
```
creators/MyFirstChannel/
├── video1.mp4
└── video2.mp4
```

### 3c. Create Metadata File

Create `creators/MyFirstChannel/videos_description.json`:

```json
{
  "video1.mp4": {
    "title": "My First Upload",
    "description": "Testing the Facebook Upload Bot! #test",
    "tags": ["test"],
    "thumbnail": null,
    "schedule": null
  }
}
```

---

## Step 4: Configure Browser Account (1 minute)

### 4a. Create Account Folder

```bash
# Replace 'GoLogin' with 'IX' if using Incogniton
# Replace 'myaccount@' with your account identifier
mkdir -p creator_shortcuts/GoLogin/myaccount@/MyFirstChannel
```

### 4b. Add Login Credentials

Create `creator_shortcuts/GoLogin/myaccount@/login_data.txt`:

```
MyFirstChannel|your_fb_email@gmail.com|your_fb_password|Your Page Name|123456789012345
```

**Format**: `profile_name|facebook_email|facebook_password|page_name|page_id`

---

## Step 5: Run the Bot! (30 seconds)

```bash
python fb_upload_bot.py
```

---

## First Time Setup

If this is your first time, run the setup wizard:

```bash
python setup.py
```

This will:
- Verify your installation
- Check dependencies
- Test browser connectivity
- Show your configuration

---

## Expected Output

```
╔═══════════════════════════════════════════════════════════╗
║          Facebook Video Upload Bot v1.0                  ║
╚═══════════════════════════════════════════════════════════╝

Starting Facebook Upload Bot...
Scanning creator shortcuts...
Found 1 browser account(s)

═══════════════════════════════════════════════════════════
UPLOAD SUMMARY
═══════════════════════════════════════════════════════════

GOLOGIN:
  Account: myaccount@
    MyFirstChannel: 1 video(s) pending

═══════════════════════════════════════════════════════════
Total: 1 creator(s), 1 video(s) to upload
═══════════════════════════════════════════════════════════

Processing GOLOGIN Account: myaccount@
Launching gologin browser...
...
```

---

## What Happens Next

1. **Browser Launches**: GoLogin/Incogniton opens automatically
2. **Profile Opens**: The bot opens your Facebook profile
3. **Upload Starts**: Video is uploaded with metadata
4. **Progress Tracked**: Database records the upload
5. **Completion**: Bot closes and shows summary

---

## Troubleshooting

### Bot won't start?
```bash
# Check dependencies
pip install -r requirements.txt

# Run setup wizard
python setup.py
```

### Can't connect to browser?
- Make sure GoLogin/Incogniton is running
- Check debug port in settings (9222 or 9223)
- Try restarting the browser

### Login fails?
- Double-check credentials in `login_data.txt`
- Try logging in manually first
- Check for 2FA requirements

### Upload fails?
- Check video format (MP4 recommended)
- Verify internet connection
- Check Facebook page permissions

---

## Next Steps

✅ **Read Full Documentation**: See `FB_UPLOAD_BOT_README.md`
✅ **Add More Creators**: Repeat Step 3 for each channel
✅ **Configure Settings**: Customize upload behavior in `settings.json`
✅ **Schedule Uploads**: Use wait settings to space out videos
✅ **Monitor Logs**: Check `logs/` folder for detailed information

---

## Folder Structure at a Glance

```
FB_Upload_Bot/
├── config/
│   └── settings.json           ← Configure here
├── creators/
│   └── MyFirstChannel/         ← Your videos here
│       ├── video1.mp4
│       └── videos_description.json
├── creator_shortcuts/
│   └── GoLogin/
│       └── myaccount@/
│           ├── login_data.txt  ← Credentials here
│           └── MyFirstChannel/
└── fb_upload_bot.py            ← Run this!
```

---

## Important Notes

⚠️ **Security**: Keep `login_data.txt` private!
⚠️ **Rate Limiting**: Don't upload too many videos at once
⚠️ **Backups**: Keep backups of your configuration
⚠️ **Testing**: Test with one video first before batch uploading

---

## Getting Help

1. Check `FB_UPLOAD_BOT_README.md` for detailed documentation
2. Run `python setup.py` for diagnostics
3. Review logs in `logs/` folder
4. Check database: `sqlite3 config/upload_status.db`

---

**You're all set! Happy uploading! 🚀**
