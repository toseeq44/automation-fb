"""
Windows Window Management Module
Handles bringing browser windows to foreground on Windows
"""

import logging
import time
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)


def bring_window_to_front_windows(window_title: str, partial_match: bool = True) -> bool:
    """
    Bring window to front on Windows using multiple methods.

    Args:
        window_title: Window title to search for
        partial_match: If True, matches partial title

    Returns:
        True if successful
    """
    try:
        logger.info("[WindowMgr] Bringing window to front on Windows...")
        logger.info("[WindowMgr] Looking for window: '%s'", window_title)

        # Method 1: PowerShell with WScript.Shell (AppActivate)
        try:
            # Clean title for PowerShell (escape quotes)
            clean_title = window_title.replace('"', '`"').replace("'", "''")

            ps_script = f'''
            $wshell = New-Object -ComObject wscript.shell
            $result = $wshell.AppActivate("{clean_title}")
            Write-Output $result
            '''

            logger.info("[WindowMgr] Method 1: PowerShell AppActivate...")
            result = subprocess.run(
                ["powershell", "-Command", ps_script],
                capture_output=True,
                text=True,
                timeout=3
            )

            if result.stdout.strip() == "True":
                logger.info("[WindowMgr] ✓ PowerShell AppActivate successful!")
                time.sleep(0.5)
                return True
            else:
                logger.debug("[WindowMgr] AppActivate returned: %s", result.stdout.strip())

        except Exception as e:
            logger.debug("[WindowMgr] PowerShell method failed: %s", str(e))

        # Method 2: PowerShell with SetForegroundWindow (more forceful)
        try:
            ps_script = f'''
            Add-Type @"
            using System;
            using System.Runtime.InteropServices;
            public class WinAPI {{
                [DllImport("user32.dll")]
                public static extern bool SetForegroundWindow(IntPtr hWnd);
                [DllImport("user32.dll")]
                public static extern IntPtr FindWindow(string lpClassName, string lpWindowName);
                [DllImport("user32.dll")]
                public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
            }}
"@

            $hwnd = [WinAPI]::FindWindow($null, "{clean_title}")
            if ($hwnd -ne [IntPtr]::Zero) {{
                [WinAPI]::ShowWindow($hwnd, 9)  # SW_RESTORE
                [WinAPI]::SetForegroundWindow($hwnd)
                Write-Output "Success"
            }} else {{
                Write-Output "NotFound"
            }}
            '''

            logger.info("[WindowMgr] Method 2: PowerShell SetForegroundWindow...")
            result = subprocess.run(
                ["powershell", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
                capture_output=True,
                text=True,
                timeout=3
            )

            if "Success" in result.stdout:
                logger.info("[WindowMgr] ✓ SetForegroundWindow successful!")
                time.sleep(0.5)
                return True
            elif "NotFound" in result.stdout:
                logger.warning("[WindowMgr] Window not found with exact title")

        except Exception as e:
            logger.debug("[WindowMgr] SetForegroundWindow method failed: %s", str(e))

        # Method 3: VBScript fallback (more reliable for AppActivate)
        try:
            vbs_script = f'''
            Set WshShell = WScript.CreateObject("WScript.Shell")
            result = WshShell.AppActivate("{clean_title}")
            If result Then
                WScript.Echo "Success"
            Else
                WScript.Echo "Failed"
            End If
            '''

            # Write to temp file
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.vbs', delete=False) as f:
                vbs_path = f.name
                f.write(vbs_script)

            logger.info("[WindowMgr] Method 3: VBScript AppActivate...")
            result = subprocess.run(
                ["cscript", "//nologo", vbs_path],
                capture_output=True,
                text=True,
                timeout=3
            )

            # Cleanup
            import os
            try:
                os.unlink(vbs_path)
            except:
                pass

            if "Success" in result.stdout:
                logger.info("[WindowMgr] ✓ VBScript AppActivate successful!")
                time.sleep(0.5)
                return True

        except Exception as e:
            logger.debug("[WindowMgr] VBScript method failed: %s", str(e))

        # Method 4: Try with partial title match using PowerShell
        if partial_match:
            try:
                ps_script = f'''
                Add-Type @"
                using System;
                using System.Runtime.InteropServices;
                using System.Text;
                public class WinAPI {{
                    [DllImport("user32.dll")]
                    public static extern bool SetForegroundWindow(IntPtr hWnd);
                    [DllImport("user32.dll")]
                    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
                    [DllImport("user32.dll")]
                    public static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);
                    [DllImport("user32.dll")]
                    public static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);
                    public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
                }}
"@

                $targetTitle = "{clean_title.split('-')[0].strip() if '-' in clean_title else clean_title[:20]}"
                $foundWindow = $null

                $callback = {{
                    param($hwnd, $lParam)
                    $sb = New-Object System.Text.StringBuilder 256
                    [WinAPI]::GetWindowText($hwnd, $sb, $sb.Capacity) | Out-Null
                    $title = $sb.ToString()
                    if ($title -like "*$targetTitle*") {{
                        $script:foundWindow = $hwnd
                        return $false
                    }}
                    return $true
                }}

                [WinAPI]::EnumWindows($callback, [IntPtr]::Zero)

                if ($foundWindow) {{
                    [WinAPI]::ShowWindow($foundWindow, 9)
                    [WinAPI]::SetForegroundWindow($foundWindow)
                    Write-Output "PartialMatchSuccess"
                }} else {{
                    Write-Output "NoMatch"
                }}
                '''

                logger.info("[WindowMgr] Method 4: Partial title match...")
                result = subprocess.run(
                    ["powershell", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
                    capture_output=True,
                    text=True,
                    timeout=5
                )

                if "PartialMatchSuccess" in result.stdout:
                    logger.info("[WindowMgr] ✓ Partial match successful!")
                    time.sleep(0.5)
                    return True

            except Exception as e:
                logger.debug("[WindowMgr] Partial match method failed: %s", str(e))

        logger.warning("[WindowMgr] All methods failed to bring window to front")
        return False

    except Exception as e:
        logger.error("[WindowMgr] Fatal error: %s", str(e))
        return False


def maximize_window_windows(window_title: str) -> bool:
    """
    Maximize window on Windows.

    Args:
        window_title: Window title

    Returns:
        True if successful
    """
    try:
        clean_title = window_title.replace('"', '`"').replace("'", "''")

        ps_script = f'''
        Add-Type @"
        using System;
        using System.Runtime.InteropServices;
        public class WinAPI {{
            [DllImport("user32.dll")]
            public static extern IntPtr FindWindow(string lpClassName, string lpWindowName);
            [DllImport("user32.dll")]
            public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
        }}
"@

        $hwnd = [WinAPI]::FindWindow($null, "{clean_title}")
        if ($hwnd -ne [IntPtr]::Zero) {{
            [WinAPI]::ShowWindow($hwnd, 3)  # SW_MAXIMIZE
            Write-Output "Maximized"
        }} else {{
            Write-Output "NotFound"
        }}
        '''

        result = subprocess.run(
            ["powershell", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=3
        )

        if "Maximized" in result.stdout:
            logger.info("[WindowMgr] ✓ Window maximized")
            return True

    except Exception as e:
        logger.debug("[WindowMgr] Maximize failed: %s", str(e))

    return False
