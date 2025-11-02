"""
Credential Manager
==================
Secure credential storage and retrieval using keyring or encrypted storage.

This module provides:
- Secure password storage (keyring on supported platforms)
- Encrypted file storage fallback
- Multi-account credential management
- Credential validation
"""

import logging
import json
import hashlib
import base64
import re
from typing import Optional, Dict, Any, List
from pathlib import Path

try:
    import keyring
    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False
    keyring = None
    logging.warning("keyring not available. Install: pip install keyring")

try:
    from cryptography.fernet import Fernet
    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False
    logging.warning("cryptography not available. Install: pip install cryptography")


class CredentialManager:
    """Manages secure credential storage and retrieval."""

    def __init__(self, service_name: str = "facebook_auto_uploader", storage_path: Optional[Path] = None):
        """
        Initialize credential manager.

        Args:
            service_name: Service name for keyring
            storage_path: Path for encrypted file storage (fallback)
        """
        self.service_name = service_name
        self.storage_path = storage_path or Path("data_files/credentials")
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # Generate or load encryption key
        self.encryption_key = self._get_or_create_encryption_key()

        if not KEYRING_AVAILABLE:
            logging.warning("Keyring not available, using encrypted file storage")

        if not CRYPTOGRAPHY_AVAILABLE:
            logging.error("Cryptography library required for credential encryption!")

        logging.debug("CredentialManager initialized (service=%s)", service_name)

    def save_credentials(self, identifier: str, credentials: Dict[str, str]) -> bool:
        """
        Save credentials securely.

        Args:
            identifier: Unique identifier (e.g., "gologin:account1:profile1")
            credentials: Dictionary with credentials (email, password, etc.)

        Returns:
            True if saved successfully

        Example:
            >>> manager = CredentialManager()
            >>> manager.save_credentials("profile1", {
            >>>     "email": "user@example.com",
            >>>     "password": "secret123",
            >>>     "page_id": "123456789"
            >>> })
        """
        logging.info("Saving credentials for: %s", identifier)

        if not self.validate_credentials(credentials):
            logging.error("Invalid credentials format")
            return False

        try:
            # Extract password for separate secure storage
            password = credentials.get('password', '')

            # Try to save password to keyring first
            if KEYRING_AVAILABLE:
                success = self._save_to_keyring(identifier, password)
                if success:
                    logging.debug("Password saved to keyring")
                else:
                    logging.warning("Keyring save failed, will use encrypted file")

            # Save non-password data to encrypted file
            non_password_data = {k: v for k, v in credentials.items() if k != 'password'}
            non_password_data['_uses_keyring'] = KEYRING_AVAILABLE

            success = self._save_to_file(identifier, non_password_data)

            # If keyring failed, also save password to encrypted file
            if not KEYRING_AVAILABLE or not success:
                non_password_data['password'] = password
                success = self._save_to_file(identifier, non_password_data)

            if success:
                logging.info("✓ Credentials saved successfully for: %s", identifier)
                return True
            else:
                logging.error("✗ Failed to save credentials")
                return False

        except Exception as e:
            logging.error("Error saving credentials: %s", e, exc_info=True)
            return False

    def load_credentials(self, identifier: str) -> Optional[Dict[str, str]]:
        """
        Load credentials for identifier.

        Args:
            identifier: Unique identifier

        Returns:
            Dictionary with credentials or None

        Example:
            >>> creds = manager.load_credentials("profile1")
            >>> print(creds['email'])
        """
        logging.debug("Loading credentials for: %s", identifier)

        try:
            # Load non-password data from file
            data = self._load_from_file(identifier)

            if not data:
                logging.warning("No credentials found for: %s", identifier)
                return None

            # Try to load password from keyring if it was stored there
            if data.get('_uses_keyring', False) and KEYRING_AVAILABLE:
                password = self._load_from_keyring(identifier)
                if password:
                    data['password'] = password
                    logging.debug("Password loaded from keyring")
                else:
                    logging.warning("Password not found in keyring")

            # Remove internal flags
            data.pop('_uses_keyring', None)

            logging.info("✓ Credentials loaded for: %s", identifier)
            return data

        except Exception as e:
            logging.error("Error loading credentials: %s", e, exc_info=True)
            return None

    def update_credentials(self, identifier: str, credentials: Dict[str, str]) -> bool:
        """
        Update existing credentials.

        Args:
            identifier: Unique identifier
            credentials: New credentials

        Returns:
            True if updated successfully
        """
        logging.info("Updating credentials for: %s", identifier)

        if not self.credential_exists(identifier):
            logging.warning("Credentials don't exist, creating new entry")

        return self.save_credentials(identifier, credentials)

    def delete_credentials(self, identifier: str) -> bool:
        """
        Delete credentials.

        Args:
            identifier: Unique identifier

        Returns:
            True if deleted successfully
        """
        logging.info("Deleting credentials for: %s", identifier)

        try:
            # Delete from keyring
            if KEYRING_AVAILABLE:
                try:
                    keyring.delete_password(self.service_name, identifier)
                    logging.debug("Deleted from keyring")
                except Exception as e:
                    logging.debug("Keyring deletion failed (may not exist): %s", e)

            # Delete encrypted file
            cred_file = self.storage_path / f"{identifier}.enc"
            if cred_file.exists():
                cred_file.unlink()
                logging.info("✓ Credentials deleted: %s", identifier)
                return True
            else:
                logging.warning("Credential file not found: %s", identifier)
                return False

        except Exception as e:
            logging.error("Error deleting credentials: %s", e, exc_info=True)
            return False

    def list_accounts(self) -> List[str]:
        """
        List all saved credential identifiers.

        Returns:
            List of identifiers

        Example:
            >>> accounts = manager.list_accounts()
            >>> print(accounts)
            ['gologin:account1:profile1', 'ix:account2:profile2']
        """
        logging.debug("Listing all accounts...")

        try:
            accounts = []

            # List all .enc files in storage directory
            for file_path in self.storage_path.glob("*.enc"):
                identifier = file_path.stem  # Filename without extension
                accounts.append(identifier)

            logging.info("Found %d account(s)", len(accounts))
            return accounts

        except Exception as e:
            logging.error("Error listing accounts: %s", e, exc_info=True)
            return []

    def credential_exists(self, identifier: str) -> bool:
        """
        Check if credentials exist for identifier.

        Args:
            identifier: Unique identifier

        Returns:
            True if credentials exist
        """
        logging.debug("Checking if credentials exist for: %s", identifier)

        cred_file = self.storage_path / f"{identifier}.enc"
        exists = cred_file.exists()

        logging.debug("Credentials exist: %s", exists)
        return exists

    def validate_credentials(self, credentials: Dict[str, str]) -> bool:
        """
        Validate credential format and required fields.

        Args:
            credentials: Credentials to validate

        Returns:
            True if valid
        """
        logging.debug("Validating credentials...")

        try:
            # Check required fields
            if 'email' not in credentials:
                logging.error("Missing required field: email")
                return False

            if 'password' not in credentials:
                logging.error("Missing required field: password")
                return False

            # Validate email format
            email = credentials['email']
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, email):
                # Also allow phone numbers for Facebook
                if not email.isdigit() or len(email) < 10:
                    logging.error("Invalid email/phone format: %s", email)
                    return False

            # Check password not empty
            password = credentials['password']
            if not password or len(password) < 1:
                logging.error("Password is empty")
                return False

            logging.debug("✓ Credentials valid")
            return True

        except Exception as e:
            logging.error("Error validating credentials: %s", e)
            return False

    def import_from_file(self, file_path: Path, format: str = "json") -> int:
        """
        Import credentials from file.

        Args:
            file_path: Path to import file
            format: File format (json, csv, etc.)

        Returns:
            Number of credentials imported
        """
        logging.info("Importing credentials from: %s", file_path)

        if not file_path.exists():
            logging.error("Import file not found: %s", file_path)
            return 0

        try:
            count = 0

            if format == "json":
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Expect format: {"identifier1": {"email": ..., "password": ...}, ...}
                for identifier, credentials in data.items():
                    if self.save_credentials(identifier, credentials):
                        count += 1

            elif format == "csv":
                import csv
                with open(file_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        identifier = row.get('identifier', f"imported_{count}")
                        credentials = {k: v for k, v in row.items() if k != 'identifier'}
                        if self.save_credentials(identifier, credentials):
                            count += 1

            logging.info("✓ Imported %d credential(s)", count)
            return count

        except Exception as e:
            logging.error("Error importing credentials: %s", e, exc_info=True)
            return 0

    def export_to_file(self, file_path: Path, format: str = "json", include_passwords: bool = False) -> bool:
        """
        Export credentials to file.

        Args:
            file_path: Path to export file
            format: File format
            include_passwords: Include passwords in export (dangerous!)

        Returns:
            True if exported successfully
        """
        logging.info("Exporting credentials to: %s", file_path)

        if include_passwords:
            logging.warning("⚠ Exporting with passwords - file will contain sensitive data!")

        try:
            accounts = self.list_accounts()
            export_data = {}

            for identifier in accounts:
                credentials = self.load_credentials(identifier)
                if credentials:
                    if not include_passwords:
                        credentials.pop('password', None)
                    export_data[identifier] = credentials

            if format == "json":
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, indent=2)

            elif format == "csv":
                import csv
                with open(file_path, 'w', encoding='utf-8', newline='') as f:
                    if not export_data:
                        return True

                    # Get all possible field names
                    fieldnames = set(['identifier'])
                    for creds in export_data.values():
                        fieldnames.update(creds.keys())

                    writer = csv.DictWriter(f, fieldnames=list(fieldnames))
                    writer.writeheader()

                    for identifier, credentials in export_data.items():
                        row = {'identifier': identifier}
                        row.update(credentials)
                        writer.writerow(row)

            logging.info("✓ Exported %d credential(s)", len(export_data))
            return True

        except Exception as e:
            logging.error("Error exporting credentials: %s", e, exc_info=True)
            return False

    # Internal methods

    def _get_or_create_encryption_key(self) -> bytes:
        """Get or create encryption key for file storage."""
        key_file = self.storage_path / ".encryption_key"

        try:
            if key_file.exists():
                # Load existing key
                with open(key_file, 'rb') as f:
                    key = f.read()
                logging.debug("Loaded existing encryption key")
            else:
                # Generate new key
                key = Fernet.generate_key()
                with open(key_file, 'wb') as f:
                    f.write(key)
                # Set file permissions (Unix only)
                try:
                    key_file.chmod(0o600)
                except:
                    pass
                logging.debug("Generated new encryption key")

            return key

        except Exception as e:
            logging.error("Error with encryption key: %s", e)
            # Return a default key (not secure, but allows operation)
            return Fernet.generate_key()

    def _save_to_keyring(self, identifier: str, password: str) -> bool:
        """Save password to system keyring."""
        if not KEYRING_AVAILABLE:
            return False

        try:
            keyring.set_password(self.service_name, identifier, password)
            return True
        except Exception as e:
            logging.error("Keyring save error: %s", e)
            return False

    def _load_from_keyring(self, identifier: str) -> Optional[str]:
        """Load password from keyring."""
        if not KEYRING_AVAILABLE:
            return None

        try:
            password = keyring.get_password(self.service_name, identifier)
            return password
        except Exception as e:
            logging.error("Keyring load error: %s", e)
            return None

    def _save_to_file(self, identifier: str, data: Dict) -> bool:
        """Save to encrypted file."""
        if not CRYPTOGRAPHY_AVAILABLE:
            logging.error("Cryptography library required")
            return False

        try:
            # Convert to JSON
            json_data = json.dumps(data)

            # Encrypt
            encrypted = self._encrypt_data(json_data, self.encryption_key)

            # Save to file
            cred_file = self.storage_path / f"{identifier}.enc"
            with open(cred_file, 'wb') as f:
                f.write(encrypted)

            # Set file permissions (Unix only)
            try:
                cred_file.chmod(0o600)
            except:
                pass

            return True

        except Exception as e:
            logging.error("File save error: %s", e, exc_info=True)
            return False

    def _load_from_file(self, identifier: str) -> Optional[Dict]:
        """Load from encrypted file."""
        if not CRYPTOGRAPHY_AVAILABLE:
            logging.error("Cryptography library required")
            return None

        try:
            cred_file = self.storage_path / f"{identifier}.enc"

            if not cred_file.exists():
                return None

            # Load encrypted data
            with open(cred_file, 'rb') as f:
                encrypted_data = f.read()

            # Decrypt
            json_data = self._decrypt_data(encrypted_data, self.encryption_key)

            # Parse JSON
            data = json.loads(json_data)

            return data

        except Exception as e:
            logging.error("File load error: %s", e, exc_info=True)
            return None

    def _encrypt_data(self, data: str, key: bytes) -> bytes:
        """Encrypt data using Fernet."""
        try:
            fernet = Fernet(key)
            encrypted = fernet.encrypt(data.encode('utf-8'))
            return encrypted
        except Exception as e:
            logging.error("Encryption error: %s", e)
            raise

    def _decrypt_data(self, encrypted_data: bytes, key: bytes) -> str:
        """Decrypt data using Fernet."""
        try:
            fernet = Fernet(key)
            decrypted = fernet.decrypt(encrypted_data)
            return decrypted.decode('utf-8')
        except Exception as e:
            logging.error("Decryption error: %s", e)
            raise
