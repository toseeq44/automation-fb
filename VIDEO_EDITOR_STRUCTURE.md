# 📹 Video Editor - Complete Structure Guide

## 🎯 Main Entry Point

### **integrated_editor.py** (17KB) - MAIN FILE ⭐
**Yeh main file hai jahan se sab kuch start hota hai!**

**Purpose:** Complete video editor interface jo sab components ko combine karta hai

**Key Class:** `IntegratedVideoEditor(QWidget)`

**What It Does:**
```python
# 3-Panel Layout banata hai:
1. LEFT PANEL   → Media Library (import, filters, cards)
2. CENTER PANEL → Dual Preview (Before/After) + Control Panel
3. RIGHT PANEL  → Properties (currently placeholder)

# Top Bar → Feature buttons (Audio, Text, Filters, Presets, Bulk, etc.)
```

**Important Methods:**
- `__init__()` - Initialize karta hai, PresetManager setup
- `init_ui()` - Complete UI banata hai, sab panels add karta hai
- `import_media()` - Media files import karta hai, auto-load first video
- `create_media_item()` - File se MediaItem object banata hai
- `load_video()` - Video ko preview windows me load karta hai
- `open_preset_manager()` - Preset dialog kholta hai
- `open_bulk_processing()` - Bulk processing dialog
- `open_title_generator()` - Title generator dialog
- `export_video()` - Video export karta hai

**Usage in Main App:**
```python
# gui.py me:
from modules.video_editor.integrated_editor import IntegratedVideoEditor
self.video_editor = IntegratedVideoEditor(self.go_to_main_menu)
```

---

## 📦 Component Files (UI Widgets)

### **media_library_enhanced.py** (28KB)
**Purpose:** Left panel - Media library with filters and card grid

**Key Classes:**
- `MediaItem` - Dataclass for media file info
  - file_path, file_name, file_type, file_size
  - duration, width, height, fps, thumbnail
  - is_zoomed, is_blurred, is_ai_enhanced, speed_factor
  - is_processing, is_new

- `FilterDropdown` - Custom styled dropdown widget
- `MediaCard` - Professional card for each media item (170x240px)
  - Thumbnail area
  - Duration badge
  - NEW/Processing badges
  - File info (name, type, size)
  - Filter badges (zoom, blur, AI, speed icons)

- `EnhancedMediaLibrary` - Main library widget
  - Import button
  - Search box
  - 4 Filter dropdowns (Zoom, Blur, AI, Speed)
  - Grid layout (2 cards per row)
  - Real-time filtering

**Signals:**
- `media_selected` - Single click on card
- `media_double_clicked` - Double click to load video
- `import_requested` - Import button clicked

**Key Methods:**
- `add_media_item(item)` - Add one item
- `refresh_display()` - Update card grid
- `apply_filters()` - Filter based on dropdowns + search

---

### **dual_preview_widget.py** (20KB)
**Purpose:** Center panel - Before/After video comparison

**Key Classes:**
- `PreviewWindow` - Single preview window (Before OR After)
  - Header bar (title + status badge)
  - Canvas (black background)
  - Placeholder text
  - Overlay elements (timecode, frame #, resolution)
  - Effect badges (for After window)

- `DualPreviewWidget` - Main dual preview container
  - 2 PreviewWindows side-by-side
  - Comparison mode controls (Split/Slider/Toggle)
  - Zoom controls
  - Quality selector (Draft/Standard/Full)
  - Sync indicator

**Signals:**
- `playback_state_changed(bool)` - Play/pause state
- `position_changed(float)` - Current time position
- `comparison_mode_changed(str)` - Mode change

**Key Methods:**
- `set_comparison_mode(mode)` - "split", "slider", "toggle"
- `load_video(video_path)` - Load video in both windows
- `update_time(current, total)` - Update timecodes
- `add_effect_to_preview(name)` - Add effect badge

---

### **unified_control_panel.py** (12KB)
**Purpose:** Control panel below preview windows

**Key Class:** `UnifiedControlPanel`

**Controls:**
- Skip Backward (⏮) - Pink color
- Play/Pause (▶⏸) - Cyan color
- Skip Forward (⏭) - Pink color
- Stop (⏹) - Red color
- Timeline Scrubber - Gradient progress bar
- Time displays (current / total) - Monospace font
- Volume slider
- Fullscreen button

**Signals:**
- `play_clicked`, `pause_clicked`, `stop_clicked`
- `skip_backward_clicked`, `skip_forward_clicked`
- `scrubber_moved(int)` - Position 0-1000
- `volume_changed(int)` - Volume 0-100
- `fullscreen_toggled()`

**Key Methods:**
- `play()`, `pause()`, `stop()` - State management
- `set_position(seconds)` - Update scrubber
- `set_duration(seconds)` - Set total duration
- `reset()` - Reset to initial state

---

### **timeline_widget.py** (34KB) ⚠️ NOT USED ANYMORE
**Purpose:** Timeline widget (currently removed from UI)

**Note:** Timeline bottom se remove kar diya hai as per user request.
Code still exists but not integrated in IntegratedVideoEditor.

---

## 🎬 Video Processing Files

### **core.py** (31KB)
**Purpose:** Core video processing engine using MoviePy

**Key Class:** `VideoEditor`

**Features:**
- Video loading (MoviePy VideoFileClip)
- Apply filters (brightness, contrast, saturation)
- Apply effects (blur, sharpen, vignette)
- Speed control (fast/slow motion)
- Transitions (fade, slide, zoom)
- Audio operations (volume, fade, background music)
- Export video (different formats, quality)

**Key Methods:**
- `load_video(path)` - Load video clip
- `apply_filter(filter_type, params)` - Apply visual filter
- `apply_effect(effect_type, params)` - Apply effect
- `apply_preset(preset)` - Apply full preset
- `export(output_path, quality)` - Export final video

---

### **custom_video_player.py** (22KB)
**Purpose:** Custom video player widget with MoviePy

**Key Class:** `CustomVideoPlayer`

**Features:**
- Video playback using MoviePy
- Frame-by-frame display
- Play/Pause/Stop controls
- Progress slider
- Time display
- Seek functionality
- Video preview

**Key Methods:**
- `load_video(path)` - Load video
- `play()`, `pause()`, `stop()` - Playback control
- `seek(position_ms)` - Jump to position
- `show_frame(frame_number)` - Display specific frame
- `update_frame()` - Timer-based frame update

---

## 🎨 Feature Files

### **filters.py** (14KB)
**Purpose:** Video filter implementations

**Filters:**
- Brightness adjustment
- Contrast adjustment
- Saturation adjustment
- Hue rotation
- Grayscale conversion
- Sepia tone
- Vignette effect
- Color temperature
- Sharpness adjustment

**Functions:**
- `apply_brightness(clip, factor)` - -100 to +100
- `apply_contrast(clip, factor)` - 0.0 to 2.0
- `apply_saturation(clip, factor)` - 0.0 to 2.0
- `apply_vignette(clip, intensity)` - 0.0 to 1.0

---

### **transitions.py** (19KB)
**Purpose:** Video transition effects

**Transitions:**
- Fade In/Out
- Cross Fade
- Slide (left, right, up, down)
- Zoom In/Out
- Wipe transitions
- Dissolve

**Functions:**
- `fade_in(clip, duration)` - Fade from black
- `fade_out(clip, duration)` - Fade to black
- `crossfade(clip1, clip2, duration)` - Smooth transition
- `slide_transition(clip1, clip2, direction, duration)`

---

### **presets.py** (19KB)
**Purpose:** Preset definitions and defaults

**Preset Types:**
- Cinematic presets (Film Look, Vintage, etc.)
- Social media presets (Instagram, TikTok, YouTube)
- Color grading presets
- Effect combinations

**Data Structure:**
```python
{
    "name": "Cinematic Film Look",
    "description": "Professional film aesthetic",
    "settings": {
        "filters": {...},
        "effects": {...},
        "color": {...}
    }
}
```

---

### **preset_manager.py** (19KB)
**Purpose:** Preset management system

**Key Class:** `PresetManager`

**Features:**
- Load/save presets (JSON files)
- Apply presets to videos
- Create custom presets
- Preset categories
- Default presets

**Key Methods:**
- `load_presets()` - Load from presets.json
- `save_preset(preset)` - Save to file
- `apply_preset(preset, video)` - Apply to video
- `get_preset_by_name(name)` - Find preset
- `delete_preset(name)` - Remove preset

---

### **preset_dialog.py** (11KB)
**Purpose:** Preset manager UI dialog

**Key Class:** `PresetManagerDialog`

**UI Components:**
- Preset list (categories)
- Preview area
- Apply button
- Save button
- Delete button
- Settings editor

**Features:**
- Browse presets by category
- Preview preset effect
- Apply to current video
- Create/edit/delete presets

---

## 🛠️ Utility Files

### **utils.py** (20KB)
**Purpose:** General utility functions

**Functions:**
- Video info extraction (duration, fps, resolution)
- Thumbnail generation
- Format conversion helpers
- File size calculation
- Time formatting
- Progress tracking

**Examples:**
```python
get_video_info(path) → dict with duration, fps, size, etc.
generate_thumbnail(path, time=0) → QPixmap
format_time(seconds) → "MM:SS" or "HH:MM:SS"
calculate_file_size(path) → formatted string
```

---

### **video_utils.py** (2KB)
**Purpose:** Video-specific utility functions

**Functions:**
- Video validation
- Format checking
- Quick video operations

---

### **crop_dialog.py** (12KB)
**Purpose:** Video crop/resize dialog

**Key Class:** `CropDialog`

**Features:**
- Visual crop selector
- Aspect ratio presets (16:9, 4:3, 1:1, 9:16)
- Custom dimensions
- Preview area
- Apply/Cancel buttons

---

## 🔄 Data Flow

```
User Import Media
    ↓
integrated_editor.import_media()
    ↓
create_media_item() → MediaItem object
    ↓
media_library.add_media_item()
    ↓
Media card created and displayed
    ↓
User double-clicks card
    ↓
integrated_editor.load_video()
    ↓
dual_preview.load_video()
    ↓
Preview windows show video name
    ↓
Control panel ready for playback
```

---

## 🎨 File Relationships

```
integrated_editor.py (MAIN)
    ├── media_library_enhanced.py (Left Panel)
    │   └── MediaItem, MediaCard, EnhancedMediaLibrary
    │
    ├── dual_preview_widget.py (Center Top)
    │   └── PreviewWindow, DualPreviewWidget
    │
    ├── unified_control_panel.py (Center Bottom)
    │   └── UnifiedControlPanel
    │
    ├── preset_manager.py (Top Bar - Presets)
    │   ├── preset_dialog.py (Dialog UI)
    │   └── presets.py (Preset data)
    │
    └── core.py (Video Processing)
        ├── custom_video_player.py (Playback)
        ├── filters.py (Visual filters)
        ├── transitions.py (Transitions)
        └── utils.py (Utilities)
```

---

## 🚀 How to Extend

### Add New Filter:

1. **filters.py** me function add karo:
```python
def apply_my_filter(clip, param1, param2):
    def filter_frame(frame):
        # Your processing here
        return modified_frame
    return clip.fl_image(filter_frame)
```

2. **core.py** me integrate karo:
```python
if filter_type == "my_filter":
    self.clip = apply_my_filter(self.clip, params['param1'], params['param2'])
```

3. **integrated_editor.py** me button add karo (optional)

---

### Add New Feature Button:

**integrated_editor.py** me `create_top_bar()` method me:
```python
my_feature_btn = QPushButton("🎯 My Feature")
my_feature_btn.setStyleSheet(button_style)
my_feature_btn.clicked.connect(self.open_my_feature)
layout.addWidget(my_feature_btn)
```

Then add method:
```python
def open_my_feature(self):
    """Open my feature dialog"""
    # Your code here
    logger.info("My feature clicked")
```

---

### Add New Media Filter:

**media_library_enhanced.py** me:

1. `FilterDropdown` add karo in `init_ui()`:
```python
self.my_combo = FilterDropdown("🎯 My Filter")
self.my_combo.addItems(["All", "Option 1", "Option 2"])
self.my_combo.currentTextChanged.connect(self.on_my_filter_changed)
```

2. Filter handler add karo:
```python
def on_my_filter_changed(self, value):
    self.my_filter = value
    self.refresh_display()
```

3. `apply_filters()` me logic add karo:
```python
if self.my_filter == "Option 1":
    self.filtered_items = [item for item in self.filtered_items if condition]
```

---

## 📝 Important Notes

### Color Scheme:
- Background: `#1a1a1a` (dark)
- Panels: `#0f0f0f`, `#1e1e1e`, `#2a2a2a`
- Accent (Cyan): `#00bcd4`
- Text: `#e0e0e0`, `#ffffff`
- Buttons:
  - Pink: `#e91e63` (skip)
  - Cyan: `#00bcd4` (play)
  - Red: `#f44336` (stop)

### Signals & Slots:
All components use PyQt5 signals for communication:
```python
# Connect signal to slot
self.media_library.media_double_clicked.connect(self.load_video)

# Emit signal
self.media_selected.emit(media_item)
```

### File Formats Supported:
- Video: `.mp4, .mov, .avi, .mkv, .webm, .flv, .wmv, .m4v`
- Audio: `.mp3, .wav, .aac, .m4a, .ogg, .wma, .flac`
- Image: `.jpg, .jpeg, .png, .gif, .webp, .bmp`

---

## 🐛 Common Issues & Solutions

### Issue: Media not showing after import
**Solution:** Check MediaItem fields are all set properly (especially boolean fields)

### Issue: Preview not loading video
**Solution:** Ensure dual_preview.load_video() is called with correct path

### Issue: Filters not working
**Solution:** Verify filter_type matches exactly in core.py

### Issue: UI not updating
**Solution:** Call refresh_display() or update() after changes

---

## 📚 Further Development

### TODO Items:
- [ ] Integrate CustomVideoPlayer for real playback
- [ ] Add actual video duration extraction
- [ ] Generate thumbnails from videos
- [ ] Implement FFmpeg export
- [ ] Add effect rendering in After window
- [ ] Timeline re-integration (optional)
- [ ] Undo/Redo system
- [ ] Keyframe animation
- [ ] Audio waveform display
- [ ] Batch processing implementation

---

## 🎓 Learning Path

**Beginner Level:**
1. Start with `integrated_editor.py` - understand main structure
2. Read `media_library_enhanced.py` - understand UI components
3. Study `dual_preview_widget.py` - learn signal/slot system

**Intermediate Level:**
4. Explore `core.py` - understand video processing
5. Study `filters.py` and `transitions.py` - MoviePy operations
6. Read `preset_manager.py` - data management

**Advanced Level:**
7. Modify `custom_video_player.py` - custom playback
8. Extend `utils.py` - optimization and helpers
9. Create new features - integrate everything

---

## 📞 Key Takeaways

### Main File: `integrated_editor.py`
- Entry point for entire video editor
- Combines all UI components
- Handles media import and video loading

### UI Components:
- `media_library_enhanced.py` - Left panel (import, filters, cards)
- `dual_preview_widget.py` - Center panel (Before/After preview)
- `unified_control_panel.py` - Playback controls

### Processing:
- `core.py` - Main video processing engine
- `filters.py`, `transitions.py` - Effects
- `preset_manager.py` - Preset system

### Data Flow:
Import → MediaItem → MediaCard → Load Video → Preview → Process → Export

---

**Yeh complete structure hai! Ab tum easily code kar sakte ho! 🚀**
