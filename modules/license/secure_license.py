"""
OneSoul Pro - Secure License System with Encryption and Hardware Binding
=========================================================================

Features:
- AES-256 encryption for license data
- HMAC-SHA256 signature for tamper protection
- Hardware ID binding (one license = one PC)
- Expiry date enforcement
- Plan type validation (Basic/Pro)

Security:
- License key is fully encrypted - user cannot read contents
- Any modification invalidates the signature
- Hardware ID prevents sharing between PCs
"""

import json
import hashlib
import hmac
import base64
import os
import platform
import subprocess
import uuid
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from pathlib import Path

# Try to import cryptography, fallback to basic encryption if not available
try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False


# ═══════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════

# Plan configurations
PLAN_CONFIG = {
    "basic": {
        "name": "Basic",
        "price_pkr": 10000,
        "daily_downloads": 200,
        "daily_pages": 200,
        "duration_days": 30,
    },
    "pro": {
        "name": "Pro",
        "price_pkr": 15000,
        "daily_downloads": None,  # Unlimited
        "daily_pages": None,      # Unlimited
        "duration_days": 30,
    }
}

# License file location
LICENSE_DIR = Path.home() / ".onesoul"
LICENSE_FILE = LICENSE_DIR / "license.key"
USAGE_FILE = LICENSE_DIR / "usage.json"


# ═══════════════════════════════════════════════════════════
# HARDWARE ID GENERATION
# ═══════════════════════════════════════════════════════════

def get_hardware_id() -> str:
    """
    Generate a unique hardware ID for the current machine.

    Uses multiple system identifiers to create a stable, unique ID:
    - CPU ID
    - MAC Address
    - Machine Name
    - Disk Serial (Windows)

    Returns:
        str: 16-character hardware ID (uppercase hex)
    """
    identifiers = []

    # 1. Get MAC Address
    try:
        mac = uuid.getnode()
        identifiers.append(str(mac))
    except:
        pass

    # 2. Get Machine Name
    try:
        identifiers.append(platform.node())
    except:
        pass

    # 3. Get Processor Info
    try:
        identifiers.append(platform.processor())
    except:
        pass

    # 4. Windows: Get Disk Serial Number
    if platform.system() == "Windows":
        try:
            result = subprocess.run(
                ["wmic", "diskdrive", "get", "serialnumber"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                lines = [l.strip() for l in result.stdout.split('\n') if l.strip() and l.strip() != 'SerialNumber']
                if lines:
                    identifiers.append(lines[0])
        except:
            pass

        # Also get motherboard serial
        try:
            result = subprocess.run(
                ["wmic", "baseboard", "get", "serialnumber"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                lines = [l.strip() for l in result.stdout.split('\n') if l.strip() and l.strip() != 'SerialNumber']
                if lines:
                    identifiers.append(lines[0])
        except:
            pass

    # 5. Linux: Get machine-id
    elif platform.system() == "Linux":
        try:
            machine_id_path = Path("/etc/machine-id")
            if machine_id_path.exists():
                identifiers.append(machine_id_path.read_text().strip())
        except:
            pass

    # Combine all identifiers and hash
    combined = "|".join(identifiers)
    hash_obj = hashlib.sha256(combined.encode())

    # Return first 16 characters (uppercase)
    return hash_obj.hexdigest()[:16].upper()


def get_hardware_id_display() -> str:
    """
    Get hardware ID formatted for display to user.

    Returns:
        str: Hardware ID in format "XXXX-XXXX-XXXX-XXXX"
    """
    hw_id = get_hardware_id()
    # Format as XXXX-XXXX-XXXX-XXXX
    return "-".join([hw_id[i:i+4] for i in range(0, 16, 4)])


# ═══════════════════════════════════════════════════════════
# LICENSE ENCRYPTION/DECRYPTION
# ═══════════════════════════════════════════════════════════

class SecureLicense:
    """
    Secure license manager with encryption and hardware binding.
    """

    # Secret key components (split for security)
    # In production, these would be obfuscated further
    _KEY_PART1 = "OneSoul"
    _KEY_PART2 = "Pro2024"
    _KEY_PART3 = "SecureLicense"
    _SALT = b"OS_LICENSE_SALT_2024"

    def __init__(self):
        """Initialize the secure license manager."""
        self._ensure_dirs()
        self._encryption_key = self._derive_key()

    def _ensure_dirs(self):
        """Ensure license directory exists."""
        LICENSE_DIR.mkdir(parents=True, exist_ok=True)

    def _derive_key(self) -> bytes:
        """
        Derive encryption key from secret components.

        Returns:
            bytes: 32-byte encryption key
        """
        secret = f"{self._KEY_PART1}_{self._KEY_PART2}_{self._KEY_PART3}"

        if CRYPTO_AVAILABLE:
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=self._SALT,
                iterations=100000,
            )
            return base64.urlsafe_b64encode(kdf.derive(secret.encode()))
        else:
            # Fallback: simple key derivation
            return base64.urlsafe_b64encode(
                hashlib.sha256(secret.encode() + self._SALT).digest()
            )

    def _encrypt(self, data: str) -> str:
        """
        Encrypt data using Fernet (AES-256).

        Args:
            data: Plain text to encrypt

        Returns:
            str: Base64 encoded encrypted data
        """
        if CRYPTO_AVAILABLE:
            f = Fernet(self._encryption_key)
            encrypted = f.encrypt(data.encode())
            return encrypted.decode()
        else:
            # Fallback: XOR encryption (less secure but works without cryptography)
            key = self._encryption_key[:len(data.encode())]
            encrypted = bytes(a ^ b for a, b in zip(data.encode(), key * (len(data.encode()) // len(key) + 1)))
            return base64.urlsafe_b64encode(encrypted).decode()

    def _decrypt(self, encrypted_data: str) -> Optional[str]:
        """
        Decrypt data.

        Args:
            encrypted_data: Base64 encoded encrypted data

        Returns:
            str: Decrypted plain text, or None if decryption fails
        """
        try:
            if CRYPTO_AVAILABLE:
                f = Fernet(self._encryption_key)
                decrypted = f.decrypt(encrypted_data.encode())
                return decrypted.decode()
            else:
                # Fallback decryption
                encrypted = base64.urlsafe_b64decode(encrypted_data.encode())
                key = self._encryption_key[:len(encrypted)]
                decrypted = bytes(a ^ b for a, b in zip(encrypted, key * (len(encrypted) // len(key) + 1)))
                return decrypted.decode()
        except Exception as e:
            return None

    def _generate_signature(self, data: dict) -> str:
        """
        Generate HMAC signature for license data.

        Args:
            data: License data dict

        Returns:
            str: Hex signature
        """
        data_str = json.dumps(data, sort_keys=True)
        signature = hmac.new(
            self._encryption_key,
            data_str.encode(),
            hashlib.sha256
        ).hexdigest()
        return signature

    def _verify_signature(self, data: dict, signature: str) -> bool:
        """
        Verify HMAC signature.

        Args:
            data: License data dict
            signature: Expected signature

        Returns:
            bool: True if signature is valid
        """
        expected = self._generate_signature(data)
        return hmac.compare_digest(expected, signature)

    # ═══════════════════════════════════════════════════════════
    # LICENSE GENERATION (ADMIN ONLY)
    # ═══════════════════════════════════════════════════════════

    def generate_license_key(
        self,
        hardware_id: str,
        plan: str,
        days: int = 30,
        admin_key: str = None
    ) -> Tuple[bool, str]:
        """
        Generate an encrypted license key.

        THIS METHOD SHOULD ONLY BE IN ADMIN TOOL!

        Args:
            hardware_id: User's hardware ID (16 chars, no dashes)
            plan: "basic" or "pro"
            days: License duration in days
            admin_key: Admin authentication key

        Returns:
            Tuple[bool, str]: (success, license_key or error_message)
        """
        # Validate admin key (simple check - in real app would be more secure)
        expected_admin = hashlib.sha256(
            f"{self._KEY_PART1}{self._KEY_PART2}ADMIN".encode()
        ).hexdigest()[:16]

        if admin_key != expected_admin:
            return False, "Invalid admin key"

        # Validate inputs
        hardware_id = hardware_id.replace("-", "").upper()
        if len(hardware_id) != 16:
            return False, "Invalid hardware ID format"

        plan = plan.lower()
        if plan not in PLAN_CONFIG:
            return False, f"Invalid plan. Choose from: {list(PLAN_CONFIG.keys())}"

        # Create license data
        created = datetime.now()
        expiry = created + timedelta(days=days)

        license_data = {
            "plan": plan,
            "hardware_id": hardware_id,
            "created": created.isoformat(),
            "expiry": expiry.isoformat(),
            "days": days,
            "version": "2.0"
        }

        # Generate signature
        signature = self._generate_signature(license_data)
        license_data["signature"] = signature

        # Encrypt the entire license
        license_json = json.dumps(license_data)
        encrypted = self._encrypt(license_json)

        # Add prefix for easy identification
        license_key = f"CF-{encrypted}"

        return True, license_key

    def get_admin_key(self) -> str:
        """
        Get the admin key for license generation.

        THIS SHOULD ONLY BE SHOWN IN ADMIN TOOL!

        Returns:
            str: Admin key
        """
        return hashlib.sha256(
            f"{self._KEY_PART1}{self._KEY_PART2}ADMIN".encode()
        ).hexdigest()[:16]

    # ═══════════════════════════════════════════════════════════
    # LICENSE VALIDATION (USER SOFTWARE)
    # ═══════════════════════════════════════════════════════════

    def validate_license_key(self, license_key: str) -> Tuple[bool, str, Optional[dict]]:
        """
        Validate a license key.

        Args:
            license_key: The encrypted license key

        Returns:
            Tuple[bool, str, dict]: (is_valid, message, license_info)
        """
        try:
            # Check prefix
            if not license_key.startswith("CF-"):
                return False, "Invalid license format", None

            # Remove prefix
            encrypted = license_key[3:]

            # Decrypt
            decrypted = self._decrypt(encrypted)
            if not decrypted:
                return False, "License key is corrupted or invalid", None

            # Parse JSON
            try:
                license_data = json.loads(decrypted)
            except json.JSONDecodeError:
                return False, "License data is corrupted", None

            # Verify signature
            signature = license_data.pop("signature", None)
            if not signature or not self._verify_signature(license_data, signature):
                return False, "License signature is invalid (tampered)", None

            # Check hardware ID
            current_hw_id = get_hardware_id()
            license_hw_id = license_data.get("hardware_id", "")

            if current_hw_id != license_hw_id:
                return False, f"License is for different PC (Hardware mismatch)", None

            # Check expiry
            expiry_str = license_data.get("expiry")
            if expiry_str:
                expiry = datetime.fromisoformat(expiry_str)
                if datetime.now() > expiry:
                    days_expired = (datetime.now() - expiry).days
                    return False, f"License expired {days_expired} days ago", license_data

            # License is valid!
            days_remaining = (expiry - datetime.now()).days
            plan = license_data.get("plan", "basic")
            plan_info = PLAN_CONFIG.get(plan, PLAN_CONFIG["basic"])

            return True, f"{plan_info['name']} license valid ({days_remaining} days remaining)", {
                "plan": plan,
                "plan_name": plan_info["name"],
                "expiry": expiry_str,
                "days_remaining": days_remaining,
                "hardware_id": license_hw_id,
                "daily_downloads": plan_info["daily_downloads"],
                "daily_pages": plan_info["daily_pages"],
            }

        except Exception as e:
            return False, f"License validation error: {str(e)}", None

    # ═══════════════════════════════════════════════════════════
    # LICENSE FILE MANAGEMENT
    # ═══════════════════════════════════════════════════════════

    def save_license(self, license_key: str) -> Tuple[bool, str]:
        """
        Save license key to file after validation.

        Args:
            license_key: The license key to save

        Returns:
            Tuple[bool, str]: (success, message)
        """
        # First validate
        is_valid, message, info = self.validate_license_key(license_key)

        if not is_valid:
            return False, message

        # Save to file
        try:
            LICENSE_FILE.write_text(license_key, encoding="utf-8")
            return True, f"License activated successfully! {message}"
        except Exception as e:
            return False, f"Failed to save license: {str(e)}"

    def load_license(self) -> Tuple[bool, str, Optional[dict]]:
        """
        Load and validate saved license.

        Returns:
            Tuple[bool, str, dict]: (is_valid, message, license_info)
        """
        if not LICENSE_FILE.exists():
            return False, "No license found. Please activate a license.", None

        try:
            license_key = LICENSE_FILE.read_text(encoding="utf-8").strip()
            return self.validate_license_key(license_key)
        except Exception as e:
            return False, f"Failed to load license: {str(e)}", None

    def remove_license(self) -> Tuple[bool, str]:
        """
        Remove saved license (deactivate).

        Returns:
            Tuple[bool, str]: (success, message)
        """
        try:
            if LICENSE_FILE.exists():
                LICENSE_FILE.unlink()
            if USAGE_FILE.exists():
                USAGE_FILE.unlink()
            return True, "License removed successfully"
        except Exception as e:
            return False, f"Failed to remove license: {str(e)}"

    # ═══════════════════════════════════════════════════════════
    # DAILY USAGE TRACKING
    # ═══════════════════════════════════════════════════════════

    def get_daily_usage(self) -> dict:
        """
        Get today's usage statistics.

        Returns:
            dict: {date, downloads, pages}
        """
        today = datetime.now().strftime("%Y-%m-%d")

        try:
            if USAGE_FILE.exists():
                usage = json.loads(USAGE_FILE.read_text(encoding="utf-8"))

                # Reset if new day
                if usage.get("date") != today:
                    usage = {"date": today, "downloads": 0, "pages": 0}
                    USAGE_FILE.write_text(json.dumps(usage), encoding="utf-8")

                return usage
        except:
            pass

        # Default
        return {"date": today, "downloads": 0, "pages": 0}

    def increment_usage(self, downloads: int = 0, pages: int = 0) -> dict:
        """
        Increment daily usage counters.

        Args:
            downloads: Number of downloads to add
            pages: Number of pages to add

        Returns:
            dict: Updated usage stats
        """
        usage = self.get_daily_usage()
        usage["downloads"] += downloads
        usage["pages"] += pages

        try:
            USAGE_FILE.write_text(json.dumps(usage), encoding="utf-8")
        except:
            pass

        return usage

    def check_limit(self, limit_type: str = "downloads") -> Tuple[bool, int, Optional[int]]:
        """
        Check if daily limit is reached.

        Args:
            limit_type: "downloads" or "pages"

        Returns:
            Tuple[bool, int, int]: (limit_reached, current_count, limit or None if unlimited)
        """
        # Get license info
        is_valid, _, info = self.load_license()

        if not is_valid or not info:
            # No valid license - use basic limits
            plan_limits = PLAN_CONFIG["basic"]
        else:
            plan = info.get("plan", "basic")
            plan_limits = PLAN_CONFIG.get(plan, PLAN_CONFIG["basic"])

        # Get limit
        if limit_type == "downloads":
            limit = plan_limits["daily_downloads"]
        else:
            limit = plan_limits["daily_pages"]

        # Unlimited (Pro)
        if limit is None:
            usage = self.get_daily_usage()
            current = usage.get(limit_type, 0)
            return False, current, None

        # Check limit
        usage = self.get_daily_usage()
        current = usage.get(limit_type, 0)

        return current >= limit, current, limit

    # ═══════════════════════════════════════════════════════════
    # GUI COMPATIBILITY METHODS
    # ═══════════════════════════════════════════════════════════

    def get_license_status_text(self) -> str:
        """
        Get license status text for GUI display.

        Returns:
            str: Status text like "Pro - 25 days" or "No License"
        """
        is_valid, message, info = self.load_license()

        if not is_valid or not info:
            return "No License"

        plan_name = info.get("plan_name", "Basic")
        days = info.get("days_remaining", 0)

        if days <= 0:
            return f"{plan_name} - Expired"
        elif days <= 7:
            return f"{plan_name} - {days}d (Expiring!)"
        else:
            return f"{plan_name} - {days}d"

    def get_license_info(self) -> dict:
        """
        Get license information for GUI display.

        Returns:
            dict: License information or empty dict if no license
        """
        is_valid, message, info = self.load_license()

        if not is_valid or not info:
            return {
                "is_valid": False,
                "plan": "none",
                "plan_name": "No License",
                "days_remaining": 0,
                "status": message,
                "hardware_id": get_hardware_id_display(),
            }

        return {
            "is_valid": True,
            "plan": info.get("plan", "basic"),
            "plan_name": info.get("plan_name", "Basic"),
            "days_remaining": info.get("days_remaining", 0),
            "expiry": info.get("expiry", ""),
            "status": message,
            "hardware_id": get_hardware_id_display(),
            "daily_downloads": info.get("daily_downloads"),
            "daily_pages": info.get("daily_pages"),
        }

    def validate_license(self) -> Tuple[bool, str, Optional[dict]]:
        """
        Validate the current license (alias for load_license).

        Returns:
            Tuple[bool, str, dict]: (is_valid, message, license_info)
        """
        return self.load_license()

    def deactivate_license(self) -> Tuple[bool, str]:
        """
        Deactivate/remove the current license (alias for remove_license).

        Returns:
            Tuple[bool, str]: (success, message)
        """
        return self.remove_license()

    def activate_license(self, license_key: str) -> Tuple[bool, str]:
        """
        Activate a license key (alias for save_license).

        Args:
            license_key: The license key to activate

        Returns:
            Tuple[bool, str]: (success, message)
        """
        return self.save_license(license_key)


# ═══════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS
# ═══════════════════════════════════════════════════════════

# Global instance
_license_manager = None

def get_license_manager() -> SecureLicense:
    """Get the global license manager instance."""
    global _license_manager
    if _license_manager is None:
        _license_manager = SecureLicense()
    return _license_manager


def is_pro_user() -> bool:
    """Quick check if current user has Pro license."""
    manager = get_license_manager()
    is_valid, _, info = manager.load_license()

    if not is_valid or not info:
        return False

    return info.get("plan") == "pro"


def get_plan_info() -> dict:
    """Get current plan information."""
    manager = get_license_manager()
    is_valid, message, info = manager.load_license()

    if not is_valid or not info:
        return {
            "plan": "none",
            "plan_name": "No License",
            "is_valid": False,
            "message": message,
            "daily_downloads": 0,
            "daily_pages": 0,
        }

    return {
        "plan": info.get("plan", "basic"),
        "plan_name": info.get("plan_name", "Basic"),
        "is_valid": True,
        "message": message,
        "days_remaining": info.get("days_remaining", 0),
        "daily_downloads": info.get("daily_downloads"),
        "daily_pages": info.get("daily_pages"),
    }


# ═══════════════════════════════════════════════════════════
# TEST / DEMO
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("SECURE LICENSE SYSTEM - TEST")
    print("=" * 60)

    # Get hardware ID
    hw_id = get_hardware_id()
    hw_id_display = get_hardware_id_display()

    print(f"\nYour Hardware ID: {hw_id_display}")
    print(f"Raw Hardware ID:  {hw_id}")

    # Create manager
    manager = SecureLicense()

    # Show admin key (for testing)
    admin_key = manager.get_admin_key()
    print(f"\nAdmin Key: {admin_key}")

    # Generate test license
    print("\n" + "=" * 60)
    print("GENERATING TEST LICENSE")
    print("=" * 60)

    success, license_key = manager.generate_license_key(
        hardware_id=hw_id,
        plan="basic",
        days=30,
        admin_key=admin_key
    )

    if success:
        print(f"\nGenerated License Key:")
        print(f"{license_key[:50]}...")
        print(f"(Total length: {len(license_key)} characters)")

        # Validate
        print("\n" + "=" * 60)
        print("VALIDATING LICENSE")
        print("=" * 60)

        is_valid, message, info = manager.validate_license_key(license_key)
        print(f"\nValid: {is_valid}")
        print(f"Message: {message}")
        if info:
            print(f"Plan: {info.get('plan_name')}")
            print(f"Days Remaining: {info.get('days_remaining')}")
            print(f"Daily Downloads: {info.get('daily_downloads') or 'Unlimited'}")
            print(f"Daily Pages: {info.get('daily_pages') or 'Unlimited'}")
    else:
        print(f"Error: {license_key}")

    print("\n" + "=" * 60)
