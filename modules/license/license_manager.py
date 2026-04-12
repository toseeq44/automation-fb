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
        self.server_url = server_url.rstrip('/')
        self.license_dir = Path.home() / ".onesoul"
        self.license_file = self.license_dir / "license.dat"
        self.license_dir.mkdir(parents=True, exist_ok=True)
        self.encryption_key = self._generate_encryption_key()
        self.fernet = Fernet(self.encryption_key)
        self.grace_period_days = 30

    def _generate_encryption_key(self) -> bytes:
        hardware_id = generate_hardware_id()
        key_material = hashlib.sha256(hardware_id.encode()).digest()
        return base64.urlsafe_b64encode(key_material)

    def _encrypt_data(self, data: dict) -> bytes:
        json_data = json.dumps(data)
        return self.fernet.encrypt(json_data.encode())

    def _decrypt_data(self, encrypted_data: bytes) -> dict:
        try:
            decrypted = self.fernet.decrypt(encrypted_data)
            return json.loads(decrypted.decode())
        except Exception as e:
            raise ValueError(f"Failed to decrypt license data: {e}")

    def _save_license_locally(self, license_data: dict) -> None:
        try:
            encrypted = self._encrypt_data(license_data)
            with open(self.license_file, 'wb') as f:
                f.write(encrypted)
        except Exception as e:
            raise Exception(f"Failed to save license locally: {e}")

    def _load_license_locally(self) -> Optional[dict]:
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
        return True, {'message': 'Bypassed'}

    def activate_license(self, license_key: str) -> Tuple[bool, str]:
        return True, "Lifetime License Activated Successfully"

    def validate_license(self, force_online: bool = False) -> Tuple[bool, str, Optional[dict]]:
        dummy_license = {
            'license_key': 'LIFETIME-LICENSE-KEY',
            'hardware_id': 'Bypassed',
            'device_name': 'Bypassed',
            'plan_type': 'pro',
            'expiry_date': '2099-12-31T23:59:59Z',
            'last_validation': datetime.utcnow().isoformat(),
            'days_remaining': 99999
        }
        return True, "License is valid", dummy_license

    def deactivate_license(self) -> Tuple[bool, str]:
        return True, "License deactivated successfully"

    def get_license_info(self) -> Optional[dict]:
        return {
            'license_key': 'LIFETIME-LICENSE-KEY',
            'hardware_id': 'Bypassed',
            'device_name': 'Bypassed',
            'plan_type': 'pro',
            'expiry_date': '2099-12-31T23:59:59Z',
            'last_validation': datetime.utcnow().isoformat(),
            'days_remaining': 99999
        }

    def is_license_valid(self) -> bool:
        return True

    def get_license_status_text(self) -> str:
        return "✅ Lifetime Status"

# Test function
if __name__ == '__main__':
    print("License Manager Bypassed Test")
    manager = LicenseManager()
    info = manager.get_license_info()
    print(json.dumps(info, indent=2))
