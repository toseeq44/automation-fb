# OneSoul Flow - Technical Architecture

## 📐 System Design

### Design Principles

1. **Modularity** - Components are independent and reusable
2. **Responsiveness** - UI adapts to all screen sizes
3. **Maintainability** - Clean code with clear separation of concerns
4. **Extensibility** - Easy to add new modules and features
5. **Performance** - Smooth animations and fast rendering

---

## 🏛️ Component Architecture

### 1. Main Window (`main_window.py`)

**Purpose:** Root container managing the entire application

**Responsibilities:**
- Window management (size, position, responsive behavior)
- Component composition (assembling top bar, sidebar, content area)
- Signal routing between components
- Global state management

**Key Methods:**
- `init_ui()` - Builds the window structure
- `connect_signals()` - Wires up component communication
- `resize_for_screen()` - Handles responsive sizing
- `resizeEvent()` - Responds to window resize events

**Signals:**
- None (receives signals from child components)

**Public API:**
```python
window = OneSoulFlowWindow()
window.set_user_info(name, license_active, license_text)
window.select_module(module_id)
window.get_active_module()
window.add_custom_page(page_id, widget)
window.replace_module_page(module_id, widget)
```

---

### 2. Top Bar (`topbar.py`)

**Purpose:** Application header with branding and user controls

**Responsibilities:**
- Display logo and app title
- Show user information and license status
- Provide access to settings and license management
- Responsive logo sizing

**Signals:**
- `settings_clicked` - Emitted when settings button clicked
- `license_clicked` - Emitted when license button clicked
- `user_info_clicked` - Emitted when user info area clicked

**Key Components:**
- `QSvgWidget` for logo rendering
- User info container with avatar and status
- Action buttons (settings, license)

**Responsive Behavior:**
- Logo size adjusts based on screen width
- Font sizes scale with screen size
- Layout maintains proper spacing

---

### 3. Sidebar (`sidebar.py`)

**Purpose:** Navigation menu with collapsible functionality

**Responsibilities:**
- Display module navigation buttons
- Handle module selection
- Animate collapse/expand transitions
- Maintain active module state

**Signals:**
- `module_selected(str)` - Emitted when module is clicked
- `toggled(bool)` - Emitted when sidebar is collapsed/expanded

**Key Components:**
- `ModuleButton` - Custom button class for modules
- Toggle button for collapse/expand
- Scroll area for overflow handling

**Animation:**
```python
# Width animation on toggle
QPropertyAnimation(self, b"minimumWidth")
Duration: 300ms
Easing: InOutCubic
```

**States:**
- **Expanded:** 250px width, shows icon + text
- **Collapsed:** 60px width, shows icon only with tooltips

---

### 4. Content Area (`content_area.py`)

**Purpose:** Dynamic content display area for modules

**Responsibilities:**
- Switch between module pages
- Manage page lifecycle
- Provide base page templates
- Handle scrolling for long content

**Key Components:**
- `QStackedWidget` - Page switching container
- `ModuleContentPage` - Base class for module pages
- `ContentCard` - Reusable card widget
- `WelcomePage` - Default landing page
- `PlaceholderModulePage` - Template for modules

**Page Structure:**
```
ModuleContentPage
├── Scroll Area
│   └── Content Container
│       ├── Title Label
│       ├── Subtitle Label (optional)
│       └── [Custom content widgets/cards]
```

**Public API:**
```python
content_area.add_page(page_id, widget)
content_area.show_page(page_id)
content_area.replace_page(page_id, new_widget)
```

---

## 🎨 Style System

### Design Token Architecture

**Three-Layer System:**

1. **Base Tokens** (`colors.py`)
   - Atomic values (colors, sizes, fonts)
   - Platform-independent
   - Single source of truth

2. **Semantic Tokens** (`colors.py` classes)
   - Purpose-driven naming
   - References to base tokens
   - Organized by category (Colors, Sizes, Fonts, etc.)

3. **Component Styles** (`stylesheet.py`)
   - PyQt5-specific stylesheets
   - Uses semantic tokens
   - Modular per-component styles

### Example Flow:

```
Base Token → Semantic Token → Component Style
"#00d4ff" → Colors.CYAN → QPushButton#primaryButton { background: #00d4ff }
```

### Stylesheet Generation

```python
class StyleSheet:
    @staticmethod
    def get_buttons():
        return f"""
            QPushButton#primaryButton {{
                background: {Colors.BTN_PRIMARY_BG};
                color: {Colors.BG_PRIMARY};
                ...
            }}
        """
```

**Benefits:**
- Easy to change entire theme
- Consistent styling across app
- Type-safe with Python
- Dynamic stylesheet generation

---

## 📡 Signal/Slot Architecture

### Communication Flow

```
User Action → Component Signal → Main Window Handler → Other Components

Example:
[Sidebar Button Click]
    ↓
sidebar.module_selected("link_grabber")
    ↓
main_window.on_module_selected("link_grabber")
    ↓
content_area.show_page("link_grabber")
```

### Signal Patterns

1. **User Actions**
   - Button clicks
   - Menu selections
   - Keyboard shortcuts

2. **State Changes**
   - Module selection
   - Sidebar toggle
   - Window resize

3. **Data Updates**
   - License status change
   - User info update
   - Progress updates

### Best Practices

- **Loose Coupling:** Components don't directly call each other
- **Central Coordination:** Main window routes signals
- **Type Safety:** Use typed signals (pyqtSignal with types)
- **Descriptive Names:** Signal names describe the event

---

## 📱 Responsive System

### Breakpoint Strategy

```python
class Breakpoints:
    EXTRA_LARGE = 1920  # 4K and above
    LARGE = 1280        # Full HD
    MEDIUM = 960        # HD
    SMALL = 640         # Minimum
```

### Responsive Components

1. **Main Window**
   - Initial size: 60-90% of screen
   - Minimum size: SMALL + sidebar width
   - Auto-center on startup

2. **Sidebar**
   - Auto-collapse on MEDIUM breakpoint
   - Smooth width animation
   - Icon-only mode with tooltips

3. **Top Bar**
   - Logo scales with screen size
   - Font sizes adjust dynamically
   - Maintains proper spacing

4. **Content Area**
   - Fluid width (takes remaining space)
   - Vertical scrolling
   - Card-based responsive layout

### Implementation Pattern

```python
def resizeEvent(self, event):
    """Handle responsive behavior on resize"""
    new_width = event.size().width()

    # Get appropriate values for screen size
    logo_size = Breakpoints.get_logo_size(new_width)
    font_size = Breakpoints.get_font_base(new_width)

    # Apply changes
    self.update_component_sizes(logo_size, font_size)

    # Auto-collapse sidebar if needed
    if new_width < Breakpoints.MEDIUM:
        self.sidebar.set_collapsed(True)
```

---

## 🔄 State Management

### State Locations

1. **Main Window State**
   - Window size and position
   - Current active module
   - User session data

2. **Sidebar State**
   - Collapsed/expanded
   - Active module button
   - Scroll position

3. **Content Area State**
   - Current page
   - Page-specific data
   - Scroll positions

### State Flow

```
User Input → Update UI → Emit Signal → Update Related Components → Persist State (if needed)
```

### Persistence (Future)

```python
# Save state
settings = {
    'sidebar_collapsed': self.sidebar.is_collapsed,
    'active_module': self.sidebar.get_active_module(),
    'window_size': (self.width(), self.height())
}
save_settings(settings)

# Restore state
settings = load_settings()
self.sidebar.set_collapsed(settings['sidebar_collapsed'])
self.select_module(settings['active_module'])
```

---

## 🎭 Animation System

### QPropertyAnimation

Used for smooth transitions:

```python
animation = QPropertyAnimation(widget, b"minimumWidth")
animation.setDuration(300)  # milliseconds
animation.setStartValue(current_width)
animation.setEndValue(target_width)
animation.setEasingCurve(QEasingCurve.InOutCubic)
animation.start()
```

### Easing Curves

- **InOutCubic** - Smooth acceleration and deceleration
- **Linear** - Constant speed
- **OutQuad** - Fast start, slow end

### Animation Timing

```python
class Effects:
    DURATION_FAST = 200      # Quick interactions
    DURATION_NORMAL = 300    # Standard transitions
    DURATION_SLOW = 400      # Emphasis animations
    DURATION_PULSE = 2000    # Continuous effects
```

---

## 🧩 Module Extension Pattern

### Creating a New Module

1. **Define Module in Sidebar**

```python
# In sidebar.py
self.modules = [
    # ... existing modules ...
    ("my_module", "My Module", "🎯"),
]
```

2. **Create Module Page**

```python
# In new file: modules/my_module.py
from gui_redesign.components.content_area import ModuleContentPage, ContentCard

class MyModulePage(ModuleContentPage):
    def __init__(self, parent=None):
        super().__init__(
            module_id="my_module",
            title="My Module",
            subtitle="Module description",
            parent=parent
        )
        self.build_ui()

    def build_ui(self):
        # Create cards and widgets
        card = ContentCard()
        # Add widgets to card
        self.add_card(card)
```

3. **Register Module**

```python
# In main application
from modules.my_module import MyModulePage

window = OneSoulFlowWindow()
window.replace_module_page("my_module", MyModulePage())
```

### Module Communication

**Parent to Module:**
```python
# Get module page reference
page = window.content_area.pages["my_module"]
page.update_data(new_data)
```

**Module to Parent:**
```python
# Emit custom signals
class MyModulePage(ModuleContentPage):
    data_updated = pyqtSignal(dict)

    def on_action(self):
        self.data_updated.emit({"key": "value"})
```

---

## 🔒 Security Considerations

1. **Input Validation**
   - Sanitize all user inputs
   - Validate file paths
   - Check data types

2. **License Management**
   - Secure license validation
   - Encrypted storage
   - Regular verification

3. **API Credentials**
   - Never hardcode credentials
   - Use secure storage
   - Encrypt sensitive data

---

## ⚡ Performance Optimization

### Best Practices

1. **Lazy Loading**
   - Load module pages only when needed
   - Defer heavy operations

2. **Efficient Rendering**
   - Use stylesheets instead of individual styling
   - Minimize repaints
   - Batch UI updates

3. **Memory Management**
   - Clean up widgets with `deleteLater()`
   - Avoid circular references
   - Use weak references where appropriate

4. **Threading**
   - Keep UI thread responsive
   - Use QThread for long operations
   - Emit signals for UI updates

---

## 🧪 Testing Strategy

### Unit Tests

```python
def test_sidebar_toggle():
    sidebar = Sidebar()
    initial_state = sidebar.is_collapsed

    sidebar.toggle_sidebar()
    assert sidebar.is_collapsed != initial_state
```

### Integration Tests

```python
def test_module_selection():
    window = OneSoulFlowWindow()
    window.select_module("link_grabber")

    assert window.get_active_module() == "link_grabber"
    assert window.content_area.current_module == "link_grabber"
```

### UI Tests

- Manual testing on different screen sizes
- Visual regression testing
- Accessibility testing

---

## 📈 Future Enhancements

1. **Plugin System**
   - Dynamic module loading
   - Third-party extensions
   - Marketplace integration

2. **Theming**
   - Multiple color schemes
   - Custom theme creation
   - Light/dark mode toggle

3. **Advanced Animations**
   - Page transitions
   - Loading animations
   - Micro-interactions

4. **Accessibility**
   - Screen reader support
   - Keyboard navigation
   - High contrast mode

5. **Internationalization**
   - Multi-language support
   - RTL layout support
   - Locale-specific formatting

---

## 📚 References

- [PyQt5 Documentation](https://doc.qt.io/qtforpython/)
- [Qt Style Sheets](https://doc.qt.io/qt-5/stylesheet.html)
- [Material Design Guidelines](https://material.io/design)
- [Design Tokens](https://www.designtokens.org/)

---

**Maintained by:** Toseeq Ur Rehman
**Last Updated:** November 2024
