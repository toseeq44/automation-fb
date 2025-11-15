# Integration Guide - OneSoul Flow GUI

Complete guide to integrate the new modern UI with existing application.

---

## 🎯 Integration Strategy

### Phase 1: Parallel Development ✅ (Current)

- New UI in separate `gui-redesign/` folder
- Old UI continues working
- Can test and develop independently

### Phase 2: Module Migration (Next)

- Migrate one module at a time
- Start with simplest module
- Test thoroughly before next module

### Phase 3: Full Replacement (Final)

- Replace old `gui.py` with new components
- Update `main.py` to use new window
- Keep old UI as backup

---

## 📝 Step-by-Step Integration

### Step 1: Test New UI Independently

```bash
# Navigate to gui-redesign folder
cd gui-redesign

# Run demo application
python demo_app.py
```

**Expected Result:** Modern UI opens with all modules as placeholders

---

### Step 2: Update Import Paths

**Option A: Add to Python Path**

```python
# In main.py, add at top
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'gui-redesign'))

# Now you can import
from components.main_window import OneSoulFlowWindow
```

**Option B: Use Absolute Imports**

```python
# In main.py
from gui_redesign.components.main_window import OneSoulFlowWindow
from gui_redesign.components.content_area import ModuleContentPage, ContentCard
```

---

### Step 3: Replace Main Window

**Current Code (main.py):**

```python
from gui import VideoToolSuiteGUI

def main():
    app = QApplication(sys.argv)
    window = VideoToolSuiteGUI()
    window.show()
    sys.exit(app.exec_())
```

**New Code (main.py):**

```python
from gui_redesign.components.main_window import OneSoulFlowWindow

def main():
    # Enable high DPI
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)

    app = QApplication(sys.argv)

    # Create new window
    window = OneSoulFlowWindow()

    # Set user info (integrate with license system)
    from modules.ui.activation_dialog import get_license_info
    license_info = get_license_info()

    window.set_user_info(
        name="Toseeq Ur Rehman",
        license_active=license_info.get('is_valid', False),
        license_text=license_info.get('status_text', 'No License')
    )

    window.show()
    sys.exit(app.exec_())
```

---

### Step 4: Migrate First Module (Link Grabber)

**Create New Module Page:**

```python
# In gui-redesign/modules/link_grabber_page.py

from components.content_area import ModuleContentPage, ContentCard
from PyQt5.QtWidgets import (
    QLabel, QPushButton, QTextEdit, QVBoxLayout,
    QHBoxLayout, QLineEdit, QProgressBar
)
from PyQt5.QtCore import Qt
from styles.colors import Colors, Sizes
from styles.stylesheet import StyleSheet

# Import existing functionality
import sys
sys.path.insert(0, '..')
from modules.link_grabber.link_grabber import LinkGrabber as OldLinkGrabber


class LinkGrabberPage(ModuleContentPage):
    """Modern UI for Link Grabber module"""

    def __init__(self, parent=None):
        super().__init__(
            module_id="link_grabber",
            title="🔗 Link Grabber",
            subtitle="Extract video links from Facebook groups",
            parent=parent
        )

        # Initialize backend
        self.link_grabber = OldLinkGrabber()

        self.build_ui()
        self.connect_signals()

    def build_ui(self):
        """Build the UI"""
        # Configuration Card
        config_card = ContentCard()

        # Group URL input
        url_label = QLabel("Facebook Group URL:")
        url_label.setStyleSheet(f"color: {Colors.TEXT_CYAN};")

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://www.facebook.com/groups/...")

        config_card.layout.addWidget(url_label)
        config_card.layout.addWidget(self.url_input)

        # Buttons
        button_layout = QHBoxLayout()

        self.start_button = QPushButton("START GRABBING")
        self.start_button.setObjectName("primaryButton")

        self.stop_button = QPushButton("STOP")
        self.stop_button.setObjectName("dangerButton")
        self.stop_button.setEnabled(False)

        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)

        config_card.layout.addLayout(button_layout)

        self.add_card(config_card)

        # Progress Card
        progress_card = ContentCard()

        self.progress_bar = QProgressBar()
        progress_card.layout.addWidget(self.progress_bar)

        self.add_card(progress_card)

        # Output Card
        output_card = ContentCard()

        output_label = QLabel("Extracted Links:")
        output_label.setStyleSheet(f"color: {Colors.TEXT_CYAN};")

        self.output_area = QTextEdit()
        self.output_area.setReadOnly(True)
        self.output_area.setObjectName("logOutput")

        output_card.layout.addWidget(output_label)
        output_card.layout.addWidget(self.output_area)

        self.add_card(output_card)

    def connect_signals(self):
        """Connect button signals"""
        self.start_button.clicked.connect(self.start_grabbing)
        self.stop_button.clicked.connect(self.stop_grabbing)

    def start_grabbing(self):
        """Start link grabbing process"""
        url = self.url_input.text().strip()

        if not url:
            self.output_area.append("❌ Please enter a group URL")
            return

        self.output_area.append(f"🔄 Starting to grab links from: {url}")
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)

        # TODO: Connect to actual link grabber backend
        # self.link_grabber.start(url)

    def stop_grabbing(self):
        """Stop link grabbing process"""
        self.output_area.append("⏹️ Stopping...")
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

        # TODO: Stop backend
        # self.link_grabber.stop()
```

**Register in Main Window:**

```python
# In main.py after creating window
from gui_redesign.modules.link_grabber_page import LinkGrabberPage

window = OneSoulFlowWindow()
window.replace_module_page("link_grabber", LinkGrabberPage())
```

---

### Step 5: Connect Existing Backend

**Pattern for Connecting Old Logic:**

```python
# Import old module backend
from modules.link_grabber.link_grabber import LinkGrabber

class LinkGrabberPage(ModuleContentPage):
    def __init__(self, parent=None):
        super().__init__(...)

        # Create backend instance
        self.backend = LinkGrabber()

        # Connect backend signals (if any)
        if hasattr(self.backend, 'progress_updated'):
            self.backend.progress_updated.connect(self.on_progress)

        if hasattr(self.backend, 'link_found'):
            self.backend.link_found.connect(self.on_link_found)

    def on_progress(self, value):
        """Update progress bar"""
        self.progress_bar.setValue(value)

    def on_link_found(self, link):
        """Display found link"""
        self.output_area.append(f"✓ {link}")
```

---

### Step 6: Migrate Settings & Dialogs

**Settings Button Handler:**

```python
# In main_window.py

def on_settings_clicked(self):
    """Show settings dialog"""
    from modules.ui.settings_dialog import SettingsDialog

    dialog = SettingsDialog(self)

    # Apply modern styling to dialog
    dialog.setStyleSheet(StyleSheet.get_complete_stylesheet())

    dialog.exec_()
```

**License Button Handler:**

```python
def on_license_clicked(self):
    """Show license info dialog"""
    from modules.ui.license_info_dialog import LicenseInfoDialog

    dialog = LicenseInfoDialog(self)
    dialog.setStyleSheet(StyleSheet.get_complete_stylesheet())
    dialog.exec_()
```

---

### Step 7: Testing Checklist

After each module migration:

- [ ] UI displays correctly
- [ ] All buttons work
- [ ] Backend functionality works
- [ ] Signals/slots connected properly
- [ ] No console errors
- [ ] Responsive on different screens
- [ ] Styling matches design
- [ ] Old functionality preserved

---

## 🔄 Migration Order (Recommended)

### Easy Modules First:

1. ✅ **API Config** - Simple form-based UI
2. ✅ **Metadata Remover** - Basic file operations
3. ✅ **Link Grabber** - Input + output display
4. 🔄 **Video Downloader** - Similar to link grabber
5. 🔄 **Video Editor** - More complex UI
6. 🔄 **Auto Uploader** - Most complex, many features
7. 🔄 **Combo Workflow** - Combines other modules

---

## 📦 File Organization

### Recommended Structure:

```
automation-fb/
├── main.py (updated to use new UI)
├── gui.py (kept as backup)
├── gui-redesign/
│   ├── components/
│   │   ├── main_window.py
│   │   ├── topbar.py
│   │   ├── sidebar.py
│   │   └── content_area.py
│   ├── modules/
│   │   ├── __init__.py
│   │   ├── link_grabber_page.py
│   │   ├── video_downloader_page.py
│   │   ├── video_editor_page.py
│   │   ├── metadata_remover_page.py
│   │   ├── auto_uploader_page.py
│   │   └── api_config_page.py
│   ├── styles/
│   ├── assets/
│   └── demo_app.py
└── modules/ (existing backend logic)
    ├── link_grabber/
    ├── video_downloader/
    ├── video_editor/
    ├── metadata_remover/
    ├── auto_uploader/
    └── api_manager/
```

---

## 🛠️ Helper Utilities

### Create Module Template

```python
# utils/create_module.py

def create_module_template(module_name, display_name, icon):
    """Generate boilerplate for new module page"""

    template = f'''"""
{display_name} Module Page
"""

from components.content_area import ModuleContentPage, ContentCard
from PyQt5.QtWidgets import QLabel, QPushButton

class {module_name.title().replace('_', '')}Page(ModuleContentPage):
    """Modern UI for {display_name}"""

    def __init__(self, parent=None):
        super().__init__(
            module_id="{module_name}",
            title="{icon} {display_name}",
            subtitle="{display_name} module description",
            parent=parent
        )

        self.build_ui()

    def build_ui(self):
        """Build the UI"""
        card = ContentCard()

        label = QLabel("Module content here")
        card.layout.addWidget(label)

        button = QPushButton("ACTION")
        button.setObjectName("primaryButton")
        card.layout.addWidget(button)

        self.add_card(card)
'''

    filename = f"modules/{module_name}_page.py"
    with open(filename, 'w') as f:
        f.write(template)

    print(f"Created: {filename}")


# Usage:
create_module_template("link_grabber", "Link Grabber", "🔗")
```

---

## 🐛 Common Issues & Solutions

### Issue 1: Import Errors

**Problem:** `ModuleNotFoundError: No module named 'components'`

**Solution:**
```python
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'gui-redesign'))
```

### Issue 2: Styles Not Applying

**Problem:** Widgets look unstyled

**Solution:**
```python
# Set object name
widget.setObjectName("primaryButton")

# Apply stylesheet
widget.setStyleSheet(StyleSheet.get_buttons())

# Or apply to parent
parent.setStyleSheet(StyleSheet.get_complete_stylesheet())
```

### Issue 3: Logo Not Showing

**Problem:** Logo doesn't render

**Solution:**
```bash
# Install PyQt5 SVG support
pip install PyQt5-svg

# Verify logo file exists
ls gui-redesign/assets/onesoul_logo.svg
```

### Issue 4: Backend Not Connecting

**Problem:** Old module logic doesn't work

**Solution:**
```python
# Import correctly
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from modules.link_grabber.link_grabber import LinkGrabber

# Check for signals
if hasattr(backend, 'signal_name'):
    backend.signal_name.connect(handler)
```

---

## ✅ Final Checklist

Before deploying new UI:

- [ ] All modules migrated and tested
- [ ] License system integrated
- [ ] Settings dialog styled
- [ ] All dialogs styled
- [ ] Responsive behavior verified
- [ ] Performance tested
- [ ] No memory leaks
- [ ] Documentation updated
- [ ] User training materials prepared
- [ ] Backup of old UI created

---

## 📞 Support

For integration help:

**Developer:** Toseeq Ur Rehman
**Contact:** 0307-7361139

---

**Last Updated:** November 2024
