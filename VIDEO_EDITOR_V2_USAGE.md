# 🎬 Video Editor Pro - Usage Guide

## Overview

Video Editor Pro ab completely redesign ho gaya hai with powerful folder-based batch processing capabilities. Ab aap ek hi preset ko hundreds/thousands of videos pe apply kar sakte ho automatically!

## ✨ New Features

### 1. **Simplified Interface**
- **Topbar**: Main functionality (folder selection, presets, controls)
- **Leftbar**: Function-specific editing controls (5 tabs)
- **Center**: Video preview + Live logs

### 2. **Folder-Based Batch Processing**
Video downloader jaise workflow:
```
Parent Folder/
├── Creator1/
│   ├── video1.mp4
│   ├── video2.mp4
│   └── edited_videos/     <- Auto-created
│       ├── edited_video1.mp4
│       └── edited_video2.mp4
├── Creator2/
│   ├── video1.mp4
│   └── edited_videos/
│       └── edited_video1.mp4
```

### 3. **Smart Tracking System**
- Already processed folders ko skip karta hai
- System off ho jaye to wahi se resume karta hai
- Tracking JSON file mein save hoti hai
- Reset option available for re-processing

### 4. **Video Preview**
- Live video preview during editing
- Play/Pause/Stop controls
- Bulk mode mein hide ho jata hai (logs only)

### 5. **Auto Title Generator** (Placeholder)
- Future feature for automatic title generation
- Coming soon!

---

## 🚀 How to Use

### Step 1: Prepare Your Folder Structure

```
MyVideos/
├── Creator_A/
│   ├── video1.mp4
│   ├── video2.mp4
│   └── video3.mp4
├── Creator_B/
│   ├── video1.mp4
│   └── video2.mp4
└── Creator_C/
    └── video1.mp4
```

### Step 2: Open Video Editor
1. Run `python main.py`
2. Click **✂️ Video Editor**

### Step 3: Configure Your Preset

**Option A: Use Built-in Template**
- Topbar mein "Preset" dropdown se select karo:
  - 📦 TikTok Standard (9:16 format)
  - 📦 Instagram Reels
  - 📦 YouTube Shorts
  - 📦 Cinematic
  - 📦 Vintage

**Option B: Create Custom Preset**
1. Click **➕ New** button
2. Enter preset name (e.g., "My Custom Preset")
3. Leftbar se operations add karo:

#### **Basic Tab**
- TikTok (9:16) - Vertical crop
- Instagram (1:1) - Square crop
- YouTube (16:9) - Widescreen
- Speed adjustment (0.1x to 10x)

#### **Filters Tab**
- Brightness +20%
- Contrast +20%
- Saturation +20%
- Black & White
- Sepia
- Vintage
- Cinematic

#### **Text Tab**
- Add text overlay
- Position: top/center/bottom
- Font size: 10-200

#### **Audio Tab**
- Volume adjustment (0.0 to 2.0)
- Mute audio

4. Click **💾 Save** to save your preset

### Step 4: Select Parent Folder
1. Click **📁 Select Parent Folder**
2. Choose your parent folder (MyVideos/)
3. System automatically preview karega:
   - Creator folders count
   - Videos count per folder
   - Processing status (✅ Processed / ⏳ Pending)

### Step 5: Configure Settings

**Settings Tab (Leftbar)**:
- **Quality**: low/medium/high/ultra
- **Delete originals**: ✅ Enable to delete original videos after editing
- **Bulk mode**: ✅ Hide video preview, show logs only (recommended for large batches)

### Step 6: Start Processing
1. Click **▶️ Start Processing**
2. Confirm dialog mein check karo:
   - Folder name
   - Preset name
   - Operations count
   - Quality
   - Delete originals setting
3. Click **Yes**

### Step 7: Monitor Progress
- **Logs panel**: Real-time processing logs
  - 📁 Folder scanning
  - 🎬 Video count
  - ⚙️ Operations being applied
  - ✅ Success messages
  - ❌ Error messages
- **Progress bar**: Current video progress
- **Stop button**: Click ⏹️ Stop to pause processing

### Step 8: Results
After processing completes:
- **Summary dialog** shows:
  - Total folders processed
  - Total videos processed
  - Successful videos
  - Failed videos
- **Output location**: `Creator_Folder/edited_videos/`
- **Original videos**: Deleted (if enabled) or kept

---

## 📋 Example Workflow

### Scenario: TikTok Videos Bulk Editing

**Goal**: 100 creators ke 500+ videos ko TikTok format (9:16) mein convert karo with cinematic filter

**Steps**:

1. **Prepare folders**:
   ```
   TikTok_Videos/
   ├── Creator001/
   ├── Creator002/
   ├── ...
   └── Creator100/
   ```

2. **Select preset**: TikTok Standard (or create custom)

3. **Add extra operations** (if using custom):
   - Basic Tab → TikTok (9:16)
   - Filters Tab → Cinematic
   - 💾 Save

4. **Select folder**: TikTok_Videos/

5. **Configure settings**:
   - Quality: high
   - Delete originals: ✅
   - Bulk mode: ✅

6. **Start processing**: ▶️ Start

7. **Wait**: System automatically process karega all folders

8. **Result**: Har creator ke folder mein `edited_videos/` subfolder with edited videos

---

## 🔄 Tracking System

### How It Works
- Har folder ka processing status JSON file mein save hota hai
- Already processed folders automatically skip ho jate hain
- System crash/restart ke baad bhi resume ho jata hai

### Tracking File Location
`video_editor_tracking.json`

### Tracking Data Example
```json
{
  "/path/to/Creator_A": {
    "status": "completed",
    "started_at": "2025-10-25T10:30:00",
    "completed_at": "2025-10-25T10:45:00",
    "videos_processed": 5
  },
  "/path/to/Creator_B": {
    "status": "in_progress",
    "started_at": "2025-10-25T10:45:00",
    "videos_processed": 2
  }
}
```

### Reset Tracking
Agar dobara se sab folders process karne hain:
1. Settings Tab → **Reset Tracking** button
2. Confirm
3. Ab sab folders phir se process honge

---

## ⚙️ Advanced Features

### 1. **Bulk Mode**
Large batches ke liye:
- Video preview hide
- Only logs visible
- Faster processing
- Less memory usage

### 2. **Custom Presets**
Multiple presets save kar sakte ho:
- TikTok_Premium
- Instagram_Pro
- YouTube_Standard
- Each preset mein different operations

### 3. **Quality Settings**
- **low**: Fast encoding, smaller file size
- **medium**: Balanced
- **high**: Best quality (recommended)
- **ultra**: Maximum quality, slower

### 4. **Delete Originals**
- ✅ Enabled: Original videos delete ho jayengi (space save)
- ❌ Disabled: Original videos remain (backup)

---

## 🐛 Troubleshooting

### Issue: "No videos found in folder"
**Solution**:
- Check video extensions: .mp4, .avi, .mov, .mkv, .flv, .wmv, .webm
- Make sure videos are directly inside creator folders

### Issue: "Already processed" message
**Solution**:
- Settings Tab → Reset Tracking
- Or manually delete tracking JSON file

### Issue: Processing very slow
**Solution**:
- Enable Bulk mode (hide video preview)
- Lower quality setting
- Check system resources (CPU/RAM)

### Issue: Some videos failed
**Solution**:
- Check logs for specific error messages
- Verify video files are not corrupted
- Try lower quality setting

---

## 📊 Performance Tips

1. **Enable Bulk Mode** for large batches (100+ videos)
2. **Use SSD** for faster file operations
3. **Close other applications** to free up RAM
4. **Use 'high' quality** instead of 'ultra' for faster processing
5. **Process during off-hours** for long batches

---

## 🎯 Best Practices

1. **Always test with 1-2 videos first** before bulk processing
2. **Keep backups** before enabling "Delete originals"
3. **Use descriptive preset names** (e.g., "TikTok_Bright_Fast")
4. **Monitor logs** during processing for errors
5. **Save presets frequently** to avoid losing work

---

## 📝 Keyboard Shortcuts (Coming Soon)
- Ctrl+S: Save preset
- Ctrl+N: New preset
- Space: Start/Stop processing
- Ctrl+L: Clear logs

---

## 🚀 Future Features

- [ ] Auto title generation with AI
- [ ] Thumbnail extraction
- [ ] Multi-language subtitle support
- [ ] Cloud storage integration
- [ ] Advanced color grading
- [ ] Audio normalization
- [ ] Batch preview mode
- [ ] Custom keyboard shortcuts

---

## 📞 Support

Koi issue ho to contact karo:
**Toseeq Ur Rehman**
Phone: 0307-7361139

---

## 🎉 Summary

Video Editor Pro ab complete hai with:
- ✅ Simple interface (topbar + leftbar)
- ✅ Video preview with controls
- ✅ Folder-based batch processing
- ✅ Smart tracking system (resume capability)
- ✅ Bulk mode (logs only)
- ✅ Auto title generator (placeholder)
- ✅ Multiple preset support
- ✅ Built-in templates
- ✅ Delete originals option

**Ab aap ek click mein hundreds of videos edit kar sakte ho!** 🚀
