"""
OneSoul Flow - Color Scheme & Design Tokens
Modern neon-themed color palette matching the infinity logo
"""

class Colors:
    """Main color palette for OneSoul Flow application"""

    # Background Colors
    BG_PRIMARY = "#050712"          # Deep space blue-black (main background)
    BG_SIDEBAR = "#0a0e1a"          # Slightly lighter (sidebar background)
    BG_ELEVATED = "#161b22"         # Elevated elements (cards, panels)
    BG_HOVER = "rgba(0, 212, 255, 0.05)"  # Hover state background
    BG_ACTIVE = "rgba(0, 212, 255, 0.1)"  # Active/selected state background

    # Accent Colors (from logo)
    CYAN = "#00d4ff"                # Neon cyan (primary accent, top arcs)
    MAGENTA = "#ff00ff"             # Neon magenta (secondary accent, bottom arcs)
    GOLD = "#ffd700"                # Gold (highlights, important text)

    # Text Colors
    TEXT_PRIMARY = "#ffffff"        # White (main text)
    TEXT_GOLD = "#ffd700"           # Gold (headings, important)
    TEXT_CYAN = "#00d4ff"           # Cyan (links, secondary headings)
    TEXT_SECONDARY = "rgba(255, 255, 255, 0.7)"   # Semi-transparent white
    TEXT_MUTED = "rgba(255, 255, 255, 0.5)"       # Muted text

    # Border Colors
    BORDER_PRIMARY = "rgba(0, 212, 255, 0.2)"     # Subtle cyan border
    BORDER_ACTIVE = "rgba(0, 212, 255, 0.6)"      # Active cyan border
    BORDER_GLOW = "rgba(0, 212, 255, 0.3)"        # Glowing border

    # Status Colors
    SUCCESS = "#43B581"             # Green (success states)
    WARNING = "#F39C12"             # Orange (warnings)
    ERROR = "#ff3860"               # Red (errors, danger)
    INFO = "#00d4ff"                # Cyan (info)

    # Button Colors
    BTN_PRIMARY_BG = "#00d4ff"      # Cyan button
    BTN_PRIMARY_HOVER = "#00b8e6"   # Darker cyan on hover
    BTN_SECONDARY_BG = "#ff00ff"    # Magenta button
    BTN_SECONDARY_HOVER = "#e600e6" # Darker magenta on hover
    BTN_SUCCESS_BG = "#ffd700"      # Gold button
    BTN_DANGER_BG = "#ff3860"       # Red button

    # Glow/Shadow Colors (with opacity)
    GLOW_CYAN = "rgba(0, 212, 255, 0.45)"
    GLOW_MAGENTA = "rgba(255, 0, 255, 0.45)"
    GLOW_GOLD = "rgba(255, 215, 0, 0.45)"
    GLOW_CYAN_STRONG = "rgba(0, 212, 255, 0.7)"

    # Gradients
    GRADIENT_CYAN = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00d4ff, stop:1 #00b8e6)"
    GRADIENT_MAGENTA = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ff00ff, stop:1 #e600e6)"
    GRADIENT_GOLD = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ffd700, stop:1 #ffcc00)"
    GRADIENT_BG = "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #050712, stop:1 #0d1117)"


class Sizes:
    """Size constants for consistent spacing and dimensions"""

    # Layout Dimensions
    SIDEBAR_EXPANDED = 250          # Sidebar width when expanded (px)
    SIDEBAR_COLLAPSED = 60          # Sidebar width when collapsed (px)
    TOPBAR_HEIGHT = 60              # Top bar height (px)

    # Logo Sizes
    LOGO_HEIGHT_LARGE = 50          # Logo height for >1920px screens
    LOGO_HEIGHT_NORMAL = 40         # Logo height for normal screens
    LOGO_HEIGHT_MEDIUM = 35         # Logo height for 960-1280px screens
    LOGO_HEIGHT_SMALL = 30          # Logo height for <960px screens

    # Spacing
    PADDING_SMALL = 10
    PADDING_MEDIUM = 20
    PADDING_LARGE = 30
    MARGIN_SMALL = 5
    MARGIN_MEDIUM = 10
    MARGIN_LARGE = 20

    # Border Radius
    RADIUS_SMALL = 4
    RADIUS_MEDIUM = 8
    RADIUS_LARGE = 12

    # Font Sizes
    FONT_HEADING_1 = 28             # Main headings
    FONT_HEADING_2 = 22             # Sub headings
    FONT_HEADING_3 = 18             # Section headings
    FONT_BODY = 14                  # Body text
    FONT_SMALL = 12                 # Small text
    FONT_BUTTON = 16                # Button text

    # Icon Sizes
    ICON_SMALL = 16
    ICON_MEDIUM = 24
    ICON_LARGE = 32
    ICON_XLARGE = 48

    # Avatar Sizes
    AVATAR_SMALL = 24
    AVATAR_MEDIUM = 32
    AVATAR_LARGE = 48


class Fonts:
    """Font family and weight constants"""

    FAMILY_PRIMARY = "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif"
    FAMILY_MONO = "'Courier New', Courier, monospace"

    WEIGHT_LIGHT = 300
    WEIGHT_NORMAL = 400
    WEIGHT_SEMIBOLD = 600
    WEIGHT_BOLD = 700
    WEIGHT_BLACK = 900


class Effects:
    """Visual effects constants"""

    # Drop shadows (for glow effects)
    SHADOW_CYAN = "0px 0px 18px rgba(0, 212, 255, 0.45)"
    SHADOW_MAGENTA = "0px 0px 18px rgba(255, 0, 255, 0.45)"
    SHADOW_GOLD = "0px 0px 18px rgba(255, 215, 0, 0.45)"
    SHADOW_CYAN_STRONG = "0px 0px 25px rgba(0, 212, 255, 0.7)"

    # Animation durations (ms)
    DURATION_FAST = 200
    DURATION_NORMAL = 300
    DURATION_SLOW = 400
    DURATION_PULSE = 2000

    # Transition easing
    EASING_DEFAULT = "ease-in-out"
    EASING_SMOOTH = "ease"
    EASING_BOUNCE = "cubic-bezier(0.68, -0.55, 0.265, 1.55)"


class Breakpoints:
    """Responsive breakpoints for different screen sizes"""

    EXTRA_LARGE = 1920      # 4K and above
    LARGE = 1280            # Full HD
    MEDIUM = 960            # HD
    SMALL = 640             # Half screen minimum

    @staticmethod
    def get_logo_size(width):
        """Get appropriate logo size based on screen width"""
        if width >= Breakpoints.EXTRA_LARGE:
            return Sizes.LOGO_HEIGHT_LARGE
        elif width >= Breakpoints.LARGE:
            return Sizes.LOGO_HEIGHT_NORMAL
        elif width >= Breakpoints.MEDIUM:
            return Sizes.LOGO_HEIGHT_MEDIUM
        else:
            return Sizes.LOGO_HEIGHT_SMALL

    @staticmethod
    def get_sidebar_width(width):
        """Get sidebar width based on screen size"""
        if width >= Breakpoints.MEDIUM:
            return Sizes.SIDEBAR_EXPANDED
        else:
            return Sizes.SIDEBAR_COLLAPSED

    @staticmethod
    def get_font_base(width):
        """Get base font size based on screen width"""
        if width >= Breakpoints.EXTRA_LARGE:
            return 16
        elif width >= Breakpoints.LARGE:
            return 14
        elif width >= Breakpoints.MEDIUM:
            return 13
        else:
            return 12
