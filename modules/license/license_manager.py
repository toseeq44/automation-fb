"""
License Manager Module
Handles license activation, validation, and deactivation
"""
import json
import requests
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from cryptography.fernet import Fernet
import base64
import hashlib
from .hardware_id import generate_hardware_id, get_device_name


class LicenseManager:
    """
    Manages license operations for the OneSoul application
    """

    def __init__(self, server_url: str = "http://localhost:5000"):
        """
        Initialize License Manager

        Args:
            server_url: URL of the license server
        """
        self.server_url = server_url.rstrip('/')
        self.license_dir = Path.home() / ".onesoul"
        self.license_file = self.license_dir / "license.dat"
        self.license_dir.mkdir(parents=True, exist_ok=True)

        # Generate encryption key from machine-specific data
        self.encryption_key = self._generate_encryption_key()
        self.fernet = Fernet(self.encryption_key)

        # Grace period for offline validation (3 days to allow offline usage after activation)
        self.grace_period_days = 3

    def _generate_encryption_key(self) -> bytes:
        """Generate encryption key based on machine-specific data"""
        # Use hardware ID as basis for encryption key
        hardware_id = generate_hardware_id()
        key_material = hashlib.sha256(hardware_id.encode()).digest()
        # Fernet requires base64-encoded 32-byte key
        return base64.urlsafe_b64encode(key_material)

    def _encrypt_data(self, data: dict) -> bytes:
        """Encrypt license data"""
        json_data = json.dumps(data)
        return self.fernet.encrypt(json_data.encode())

    def _decrypt_data(self, encrypted_data: bytes) -> dict:
        """Decrypt license data"""
        try:
            decrypted = self.fernet.decrypt(encrypted_data)
            return json.loads(decrypted.decode())
        except Exception as e:
            raise ValueError(f"Failed to decrypt license data: {e}")

    def _save_license_locally(self, license_data: dict) -> None:
        """Save encrypted license data to local file"""
        try:
            encrypted = self._encrypt_data(license_data)
            with open(self.license_file, 'wb') as f:
                f.write(encrypted)
        except Exception as e:
            raise Exception(f"Failed to save license locally: {e}")

    def _load_license_locally(self) -> Optional[dict]:
        """Load encrypted license data from local file"""
        try:
            if not self.license_file.exists():
                return None

            with open(self.license_file, 'rb') as f:
                encrypted = f.read()

            return self._decrypt_data(encrypted)
        except Exception as e:
            print(f"Failed to load license: {e}")
            return None

    def _make_api_request(self, endpoint: str, data: dict, timeout: int = 10) -> Tuple[bool, dict]:
        """
        Make API request to license server

        Returns:
            Tuple of (success: bool, response_data: dict)
        """
        try:
            url = f"{self.server_url}/api/{endpoint}"
            response = requests.post(url, json=data, timeout=timeout)

            if response.status_code in [200, 201]:
                return True, response.json()
            else:
                error_data = response.json() if response.content else {}
                return False, error_data

        except requests.exceptions.ConnectionError:
            return False, {'message': 'Unable to connect to license server. Check your internet connection.'}
        except requests.exceptions.Timeout:
            return False, {'message': 'License server request timed out. Please try again.'}
        except Exception as e:
            return False, {'message': f'Network error: {str(e)}'}

    def activate_license(self, license_key: str) -> Tuple[bool, str]:
        """
        Activate license on this device

        Args:
            license_key: The license key to activate

        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            license_key = license_key.strip()
            hardware_id = generate_hardware_id()
            device_name = get_device_name()

            # Make activation request
            success, response = self._make_api_request(
                'license/activate',
                {
                    'license_key': license_key,
                    'hardware_id': hardware_id,
                    'device_name': device_name
                }
            )

            if success:
                # Save license locally
                license_data = {
                    'license_key': license_key,
                    'hardware_id': hardware_id,
                    'device_name': device_name,
                    'plan_type': response.get('plan_type'),
                    'expiry_date': response.get('expiry_date'),
                    'last_validation': datetime.utcnow().isoformat(),
                    'days_remaining': response.get('days_remaining')
                }
                self._save_license_locally(license_data)

                return True, response.get('message', 'License activated successfully!')

            else:
                return False, response.get('message', 'Failed to activate license')

        except Exception as e:
            return False, f"Activation error: {str(e)}"

    def validate_license(self, force_online: bool = False) -> Tuple[bool, str, Optional[dict]]:
        """
        Validate license (online + offline grace period)

        Args:
            force_online: Force online validation even if offline grace is valid

        Returns:
            Tuple of (is_valid: bool, message: str, license_info: dict or None)
        """
        try:
            # Load local license
            local_license = self._load_license_locally()

            if not local_license:
                return False, "No license found. Please activate a license first.", None

            license_key = local_license.get('license_key')
            hardware_id = local_license.get('hardware_id')
            last_validation = local_license.get('last_validation')

            # Check if hardware ID matches (device changed)
            current_hardware_id = generate_hardware_id()
            if hardware_id != current_hardware_id:
                return False, "Hardware mismatch. License is registered to a different device.", None

            # Try online validation
            success, response = self._make_api_request(
                'license/validate',
                {
                    'license_key': license_key,
                    'hardware_id': hardware_id
                }
            )

            if success:
                # Online validation successful
                is_valid = response.get('valid', False)
                is_expired = response.get('is_expired', True)

                # Update local cache
                local_license['last_validation'] = datetime.utcnow().isoformat()
                local_license['expiry_date'] = response.get('expiry_date')
                local_license['days_remaining'] = response.get('days_remaining')
                local_license['plan_type'] = response.get('plan_type')
                self._save_license_locally(local_license)

                if is_expired:
                    return False, "License has expired. Please renew your subscription.", local_license

                return True, "License is valid", local_license

            else:
                # Online validation failed - check offline grace period
                if last_validation:
                    last_validation_dt = datetime.fromisoformat(last_validation)
                    days_since_validation = (datetime.utcnow() - last_validation_dt).days

                    if days_since_validation <= self.grace_period_days:
                        # Within grace period
                        days_left = self.grace_period_days - days_since_validation
                        message = f"Offline mode: {days_left} day(s) remaining before online validation required"
                        return True, message, local_license
                    else:
                        # Grace period expired
                        return False, f"Could not validate license online. Grace period ({self.grace_period_days} days) expired. Please connect to the internet.", local_license
                else:
                    # No last validation timestamp
                    return False, "Unable to validate license. Please connect to the internet.", local_license

        except Exception as e:
            return False, f"Validation error: {str(e)}", None

    def deactivate_license(self) -> Tuple[bool, str]:
        """
        Deactivate license from current device

        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # Load local license
            local_license = self._load_license_locally()

            if not local_license:
                return False, "No license found to deactivate"

            license_key = local_license.get('license_key')
            hardware_id = local_license.get('hardware_id')

            # Make deactivation request
            success, response = self._make_api_request(
                'license/deactivate',
                {
                    'license_key': license_key,
                    'hardware_id': hardware_id
                }
            )

            if success:
                # Delete local license file
                if self.license_file.exists():
                    self.license_file.unlink()

                return True, response.get('message', 'License deactivated successfully')

            else:
                return False, response.get('message', 'Failed to deactivate license')

        except Exception as e:
            return False, f"Deactivation error: {str(e)}"

    def get_license_info(self) -> Optional[dict]:
        """
        Get current license information

        Returns:
            License info dict or None if no license
        """
        try:
            local_license = self._load_license_locally()

            if not local_license:
                return None

            # Calculate days remaining
            expiry_date_str = local_license.get('expiry_date')
            if expiry_date_str:
                expiry_date = datetime.fromisoformat(expiry_date_str.replace('Z', '+00:00'))
                days_remaining = max(0, (expiry_date - datetime.utcnow()).days)
                local_license['days_remaining'] = days_remaining
            else:
                local_license['days_remaining'] = 0

            return local_license

        except Exception as e:
            print(f"Error getting license info: {e}")
            return None

    def is_license_valid(self) -> bool:
        """
        Quick check if license is valid (uses cached data)

        Returns:
            True if valid, False otherwise
        """
        is_valid, _, _ = self.validate_license()
        return is_valid

    def get_license_status_text(self) -> str:
        """
        Get human-readable license status text for UI display

        Returns:
            Status string
        """
        license_info = self.get_license_info()

        if not license_info:
            return "⚠️ No License"

        is_valid, message, _ = self.validate_license()

        if is_valid:
            days = license_info.get('days_remaining', 0)
            if days > 30:
                return f"✅ Active ({days} days remaining)"
            elif days > 7:
                return f"✅ Active ({days} days remaining)"
            elif days > 0:
                return f"⚠️ Expiring Soon ({days} days remaining)"
            else:
                return "⚠️ Expired"
        else:
            return "⚠️ Invalid License"


# Test function
if __name__ == '__main__':
    print("License Manager Test")
    print("=" * 50)

    # Initialize manager (replace with your server URL)
    manager = LicenseManager(server_url="http://localhost:5000")

    print(f"License file location: {manager.license_file}")
    print(f"Hardware ID: {generate_hardware_id()}")
    print(f"Device Name: {get_device_name()}")
    print("=" * 50)

    # Check current license
    info = manager.get_license_info()
    if info:
        print("Current License:")
        print(json.dumps(info, indent=2))
    else:
        print("No license found")

    print("=" * 50)
