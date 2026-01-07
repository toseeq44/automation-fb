# AR Face Effects - Installation Guide

## ✅ MediaPipe Version Compatibility

The AR face effects feature now supports **BOTH MediaPipe APIs**:

- ✅ **MediaPipe 0.10+ (tasks API)** - Modern, recommended
- ✅ **MediaPipe 0.8.x (solutions API)** - Legacy, still supported

**RECOMMENDED: Use MediaPipe 0.10.31+ for best performance!**

---

## 🚀 Quick Install (Recommended)

Install the latest MediaPipe version:

```bash
# Install MediaPipe (latest version)
pip install mediapipe

# Restart OneSoul
python main.py
```

**First run**: The app will automatically download the face landmarker model (~10MB)

---

## 🧪 Diagnose MediaPipe Issues

Run the diagnostic script to check your MediaPipe installation:

```bash
python test_mediapipe_api.py
```

**Expected output for working installation:**
```
✅ MediaPipe version: 0.8.11
✅ mp.solutions exists
✅ mediapipe.solutions.face_mesh works!
```

---

## 📦 Fresh Installation

If you're installing AR features for the first time:

```bash
# Install compatible MediaPipe version
pip install mediapipe==0.8.11 protobuf opencv-python

# Verify installation
python -c "from mediapipe.solutions import face_mesh; print('✅ MediaPipe ready!')"

# Run OneSoul
python main.py
```

---

## 🎯 AR Features Available

Once MediaPipe 0.8.11 is installed, you'll have access to:

- ✨ **Face Beautification**: AI-powered skin smoothing
- 👁️ **Eye Enhancement**: Automatic eye sharpening and brightening
- 🦷 **Teeth Whitening**: Automatic teeth whitening
- 📱 **Auto Crop to Face**: Smart face-centered cropping (TikTok/Reels)
- 🎭 **Background Blur**: Portrait mode effect (DSLR-like)
- 🔍 **Face Landmarks**: Debug mode (468-point face mesh)

---

## ❌ Common Errors & Solutions

### Error 1: `module 'mediapipe' has no attribute 'solutions'`

**Cause**: MediaPipe 0.10+ installed (incompatible)

**Solution**: Downgrade to 0.8.11
```bash
pip install mediapipe==0.8.11
```

### Error 2: `No module named 'mediapipe.python'`

**Cause**: Incorrect import path for your MediaPipe version

**Solution**: Run diagnostic script and downgrade:
```bash
python test_mediapipe_api.py
pip install mediapipe==0.8.11
```

### Error 3: `AR Engine not available`

**Cause**: MediaPipe not installed or incompatible version

**Solution**: Install compatible version:
```bash
pip install mediapipe==0.8.11 protobuf opencv-python
```

---

## 🔮 Future Support

**MediaPipe 0.10+ Tasks API support is planned** but requires code refactoring.

Current status:
- ✅ MediaPipe 0.8.x (solutions API) - **FULLY SUPPORTED**
- ⏳ MediaPipe 0.10+ (tasks API) - **PLANNED**

---

## 📊 Version Compatibility Matrix

| MediaPipe Version | Status | AR Features | API Used |
|-------------------|--------|-------------|----------|
| 0.8.9 - 0.8.11    | ✅ Fully Supported | All features work | Solutions (legacy) |
| 0.9.x             | ⚠️ Untested | May work | Solutions (legacy) |
| 0.10.0 - 0.10.31  | ✅ Fully Supported | All features work | Tasks (modern) |
| **0.10.31** (latest) | ✅ **RECOMMENDED** | All features work | Tasks (modern) |

**Note**: MediaPipe 0.8.x is no longer available on PyPI. Use 0.10+ for new installations.

---

## 💡 Recommended Setup

**For new installations (RECOMMENDED):**
```bash
# Install latest MediaPipe
pip install mediapipe
pip install protobuf opencv-python
```

**For development:**
```bash
# Install from requirements.txt (may have newer versions)
pip install -r requirements.txt

# If AR features fail, downgrade MediaPipe
pip install mediapipe==0.8.11
```

---

## 🆘 Still Having Issues?

1. **Run diagnostic**: `python test_mediapipe_api.py`
2. **Check logs**: Look for AR Engine initialization messages
3. **Verify installation**:
   ```bash
   pip show mediapipe
   python -c "from mediapipe.solutions import face_mesh; print('OK')"
   ```
4. **Clean reinstall**:
   ```bash
   pip uninstall mediapipe opencv-python protobuf -y
   pip install mediapipe==0.8.11 opencv-python protobuf
   ```

---

## 📝 Technical Notes

### Why MediaPipe 0.10+ Doesn't Work

MediaPipe 0.10+ completely restructured their API:

**OLD API (0.8.x - WORKS)**:
```python
from mediapipe.solutions import face_mesh
fm = face_mesh.FaceMesh()
```

**NEW API (0.10+ - NOT YET IMPLEMENTED)**:
```python
from mediapipe.tasks.python import vision
landmarker = vision.FaceLandmarker.create_from_options(...)
```

The new API requires significant code changes to implement.

---

## 🚀 Quick Start (TL;DR)

```bash
# 1. Downgrade MediaPipe
pip install mediapipe==0.8.11

# 2. Test
python test_mediapipe_api.py

# 3. Run OneSoul
python main.py

# 4. Create AR preset with face_beautify, eye_enhancement, etc.
```

**That's it! AR features should now work perfectly.** ✨
