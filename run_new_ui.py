#!/usr/bin/env python3
"""
OneSoul Flow - Demo Launcher
Run this from automation-fb directory to see the new modern UI
"""

import sys
import os

# Add gui-redesign to path
gui_redesign_path = os.path.join(os.path.dirname(__file__), 'gui-redesign')
if gui_redesign_path not in sys.path:
    sys.path.insert(0, gui_redesign_path)

# Now run the demo
if __name__ == "__main__":
    os.chdir(gui_redesign_path)
    from demo_app import main
    main()
