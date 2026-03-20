# NSTbrowser Approach

Facebook video upload automation using NSTbrowser antidetect browser.

## Features

- ✅ Multi-profile support via NSTbrowser API
- ✅ Automatic desktop app launch
- ✅ Selenium WebDriver integration
- ✅ State persistence for crash recovery
- ✅ Network monitoring for resilience
- ✅ Daily limit enforcement (basic/pro plans)

## Installation

### Prerequisites

1. **NSTbrowser Desktop App**
   - Download and install from: https://www.nstbrowser.io
   - Create desktop shortcut: `Nstbrowser.lnk`
   - Login with your account

2. **Python Dependencies**
   ```bash
   pip install nstbrowser
   pip install selenium
   pip install pywin32  # For Windows window management
   ```

3. **ChromeDriver** (for Selenium)
   - Download from: https://chromedriver.chromium.org/
   - Add to system PATH

## Configuration

### 1. Get NSTbrowser API Key

1. Login to NSTbrowser dashboard
2. Navigate to API settings
3. Generate or copy your API key (UUID format)
   - Example: `d27f90bc-57ce-4bbe-9ab9-a3b7f99d616f`

### 2. Configure Credentials

Create approach configuration with NSTbrowser credentials:

```python
from modules.auto_uploader.approaches import ApproachConfig, ApproachFactory
from pathlib import Path

config = ApproachConfig(
    mode='nstbrowser',  # or 'nst'
    credentials={
        'email': 'your_email@example.com',      # NSTbrowser account email
        'password': 'your_password',            # NSTbrowser account password
        'api_key': 'd27f90bc-xxxx-xxxx',        # Your API key
        'base_url': 'http://127.0.0.1:8848'     # Default API endpoint
    },
    paths={
        'creators_root': Path('/path/to/creator_data')
    },
    browser_type='nstbrowser'
)

# Create approach instance
approach = ApproachFactory.create(config)
```

## Usage

### Basic Example

```python
from modules.auto_uploader.approaches import ApproachConfig, ApproachFactory

# Configure NSTbrowser approach
config = ApproachConfig(
    mode='nstbrowser',
    credentials={
        'email': 'user@example.com',
        'password': 'password123',
        'api_key': 'd27f90bc-57ce-4bbe-9ab9-a3b7f99d616f'
    },
    paths={
        'creators_root': Path('/path/to/data')
    }
)

# Create and initialize approach
approach = ApproachFactory.create(config)

if approach and approach.initialize():
    print("✓ NSTbrowser approach initialized successfully!")

    # Get available profiles
    profiles = approach.get_profiles()
    print(f"Found {len(profiles)} profile(s)")

    # Open first profile
    if profiles:
        profile_id = profiles[0]['id']
        if approach.open_browser(profile_id):
            print("✓ Browser opened!")

            # Navigate to Facebook
            approach.navigate_to('https://www.facebook.com')

            # Close browser
            approach.close_browser()

    # Cleanup
    approach.cleanup()
```

### Testing Components

#### Test Configuration Handler

```bash
cd modules/auto_uploader/approaches/nstbrowser
python config_handler.py
```

#### Test Desktop Launcher

```bash
python desktop_launcher.py
```

#### Test Connection Manager

```bash
python connection_manager.py
# Enter API key when prompted
```

#### Test Browser Launcher

```bash
python browser_launcher.py
# Enter API key when prompted
```

## Architecture

### Component Structure

```
nstbrowser/
├── workflow.py              # Main approach implementation
├── config_handler.py        # Configuration management
├── connection_manager.py    # API connection wrapper
├── browser_launcher.py      # Profile launch + Selenium
├── desktop_launcher.py      # Desktop app auto-launch
└── data/
    └── nst_config.json     # Stored credentials
```

### Reused Components (from ixbrowser)

The NSTbrowser approach reuses these browser-agnostic components:

- **StateManager**: State persistence and crash recovery
- **NetworkMonitor**: Network connectivity monitoring
- **ProfileManager**: Multi-profile queue management
- **FolderQueueManager**: Video folder iteration
- **VideoUploadHelper**: Facebook upload logic

## API Reference

### NSTBrowserApproach

Main approach class implementing the workflow.

```python
approach = NSTBrowserApproach(config)

# Initialize components
approach.initialize() -> bool

# Open browser profile
approach.open_browser(profile_id: str) -> bool

# Get Selenium driver
driver = approach.get_driver()

# Navigate to URL
approach.navigate_to(url: str) -> bool

# Close browser
approach.close_browser() -> bool

# Cleanup resources
approach.cleanup()

# Get available profiles
profiles = approach.get_profiles() -> List[Dict]
```

### NSTConnectionManager

Manages API connection.

```python
manager = NSTConnectionManager(
    api_key='your_api_key',
    base_url='http://127.0.0.1:8848',
    auto_launch=True
)

# Connect to API
manager.connect() -> bool

# Get profile list
profiles = manager.get_profile_list(page_size=100) -> List[Dict]

# Find profile by ID
profile = manager.find_profile_by_id(profile_id) -> Dict

# Test connection
manager.test_connection() -> bool

# Disconnect
manager.disconnect()
```

### NSTBrowserLauncher

Launches profiles and manages Selenium.

```python
launcher = NSTBrowserLauncher(client)

# Launch profile
launcher.launch_profile(profile_id) -> bool

# Attach Selenium
launcher.attach_selenium() -> bool

# Get driver
driver = launcher.get_driver()

# Navigate
launcher.navigate_to(url) -> bool

# Close profile
launcher.close_profile() -> bool
```

### NSTDesktopLauncher

Auto-launches desktop application.

```python
launcher = NSTDesktopLauncher(
    host='127.0.0.1',
    port=8848
)

# Check if API is available
launcher.is_api_available() -> bool

# Find shortcut
shortcut = launcher.find_shortcut() -> Path

# Launch application
launcher.launch_application() -> bool

# Ensure running (launch if needed)
launcher.ensure_running(timeout=60) -> bool
```

## Comparison with ixBrowser

| Feature | ixBrowser | NSTbrowser |
|---------|-----------|------------|
| **Library** | `ixbrowser-local-api` | `nstbrowser` |
| **API Endpoint** | `127.0.0.1:53200` | `127.0.0.1:8848` |
| **Authentication** | None (local) | API key required |
| **Profile ID** | Integer | String |
| **Desktop App** | `ixBrowser.exe` | `Nstbrowser.lnk` |
| **Selenium** | Same method | Same method |

## Troubleshooting

### NSTbrowser not launching

1. Check desktop shortcut exists: `C:\Users\<user>\Desktop\Nstbrowser.lnk`
2. Verify NSTbrowser is installed
3. Check API port 8848 is not blocked

### API connection failed

1. Verify API key is correct
2. Ensure NSTbrowser desktop app is running and logged in
3. Check firewall/antivirus blocking port 8848

### Selenium attachment failed

1. Install ChromeDriver matching your Chrome version
2. Verify debugger address is correct
3. Check profile launched successfully

### Profile not found

1. List all profiles: `approach.get_profiles()`
2. Verify profile ID is correct (string format)
3. Check profile exists in NSTbrowser dashboard

## Development

### Adding New Features

The NSTbrowser approach follows the same architecture as ixBrowser:

1. **Configuration**: Add settings to `config_handler.py`
2. **API Methods**: Extend `connection_manager.py`
3. **Browser Control**: Extend `browser_launcher.py`
4. **Workflow**: Update `workflow.py`

### Testing

Run unit tests for each component:

```bash
# Test each component individually
python config_handler.py
python desktop_launcher.py
python connection_manager.py
python browser_launcher.py
```

## Future Enhancements

- [ ] Auto-login helper (like ixBrowser's `ix_login_helper.py`)
- [ ] Complete video upload workflow
- [ ] Facebook login/logout automation
- [ ] Bookmark creation and management
- [ ] Error recovery and retry logic
- [ ] Multi-threaded profile processing
- [ ] Progress tracking and reporting

## Support

For issues or questions:

1. Check NSTbrowser API docs: https://apidocs.nstbrowser.io
2. Review GitHub examples: https://github.com/nstbrowser
3. Contact NSTbrowser support: https://www.nstbrowser.io/support

## License

Part of the OneSoul automation project.
