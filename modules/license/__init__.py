"""License management module"""
from .hardware_id import generate_hardware_id, get_device_name
from .license_manager import LicenseManager

__all__ = ['generate_hardware_id', 'get_device_name', 'LicenseManager']
