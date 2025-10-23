"""
Hardware ID Generation Module
Generates a unique, persistent hardware fingerprint for license binding
"""
import hashlib
import platform
import subprocess
import uuid
from pathlib import Path


def get_machine_id() -> str:
    """
    Get unique machine ID based on platform
    Returns a string identifier
    """
    try:
        system = platform.system()

        if system == "Windows":
            # Windows: Use MachineGuid from registry
            try:
                import winreg
                key = winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    r"SOFTWARE\Microsoft\Cryptography",
                    0,
                    winreg.KEY_READ | winreg.KEY_WOW64_64KEY
                )
                machine_guid, _ = winreg.QueryValueEx(key, "MachineGuid")
                winreg.CloseKey(key)
                return machine_guid
            except:
                pass

        elif system == "Linux":
            # Linux: Use machine-id
            machine_id_files = [
                "/etc/machine-id",
                "/var/lib/dbus/machine-id"
            ]
            for file_path in machine_id_files:
                try:
                    with open(file_path, 'r') as f:
                        return f.read().strip()
                except:
                    continue

        elif system == "Darwin":  # macOS
            # macOS: Use IOPlatformUUID
            try:
                result = subprocess.run(
                    ['ioreg', '-rd1', '-c', 'IOPlatformExpertDevice'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                for line in result.stdout.splitlines():
                    if 'IOPlatformUUID' in line:
                        return line.split('"')[3]
            except:
                pass

    except Exception:
        pass

    # Fallback: UUID based on MAC address
    return str(uuid.getnode())


def get_cpu_info() -> str:
    """Get CPU information"""
    try:
        return platform.processor() or "unknown"
    except:
        return "unknown"


def get_disk_serial() -> str:
    """Get disk serial number"""
    try:
        system = platform.system()

        if system == "Windows":
            try:
                result = subprocess.run(
                    ['wmic', 'diskdrive', 'get', 'serialnumber'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                lines = result.stdout.strip().split('\n')
                if len(lines) > 1:
                    return lines[1].strip()
            except:
                pass

        elif system == "Linux":
            try:
                result = subprocess.run(
                    ['lsblk', '-o', 'SERIAL', '-n'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                serial = result.stdout.strip().split('\n')[0]
                if serial:
                    return serial
            except:
                pass

        elif system == "Darwin":  # macOS
            try:
                result = subprocess.run(
                    ['system_profiler', 'SPSerialATADataType'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                for line in result.stdout.splitlines():
                    if 'Serial Number' in line:
                        return line.split(':')[1].strip()
            except:
                pass

    except Exception:
        pass

    return "unknown"


def get_motherboard_info() -> str:
    """Get motherboard information"""
    try:
        system = platform.system()

        if system == "Windows":
            try:
                result = subprocess.run(
                    ['wmic', 'baseboard', 'get', 'serialnumber'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                lines = result.stdout.strip().split('\n')
                if len(lines) > 1:
                    return lines[1].strip()
            except:
                pass

        elif system == "Linux":
            try:
                with open('/sys/class/dmi/id/board_serial', 'r') as f:
                    return f.read().strip()
            except:
                pass

        elif system == "Darwin":  # macOS
            try:
                result = subprocess.run(
                    ['system_profiler', 'SPHardwareDataType'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                for line in result.stdout.splitlines():
                    if 'Serial Number' in line:
                        return line.split(':')[1].strip()
            except:
                pass

    except Exception:
        pass

    return "unknown"


def generate_hardware_id() -> str:
    """
    Generate a unique hardware ID based on multiple hardware components
    Returns a SHA-256 hash string

    This ID will be consistent across app restarts but will change if
    hardware components change
    """
    # Collect hardware identifiers
    components = [
        platform.system(),           # OS
        platform.machine(),          # Machine type
        get_machine_id(),            # Unique machine ID
        get_cpu_info(),              # CPU info
        get_disk_serial(),           # Disk serial
        get_motherboard_info(),      # Motherboard info
    ]

    # Combine all components
    combined = '|'.join(str(c) for c in components)

    # Generate SHA-256 hash
    hardware_id = hashlib.sha256(combined.encode('utf-8')).hexdigest()

    return hardware_id


def get_device_name() -> str:
    """Get a friendly device name"""
    try:
        import socket
        hostname = socket.gethostname()
        system = platform.system()
        return f"{hostname} ({system})"
    except:
        return f"Device ({platform.system()})"


# Test function
if __name__ == '__main__':
    print("Hardware ID Test")
    print("=" * 50)
    print(f"Machine ID: {get_machine_id()}")
    print(f"CPU Info: {get_cpu_info()}")
    print(f"Disk Serial: {get_disk_serial()}")
    print(f"Motherboard: {get_motherboard_info()}")
    print(f"Device Name: {get_device_name()}")
    print("=" * 50)
    print(f"Hardware ID: {generate_hardware_id()}")
    print("=" * 50)
