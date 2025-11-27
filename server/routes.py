"""
API routes for license management
"""
from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
from models import db, License, ValidationLog, SecurityAlert
import secrets
import string
import os
import base64
import hmac
import hashlib
import os

api = Blueprint('api', __name__)

SIGNING_SECRET = os.getenv('LICENSE_SIGNING_SECRET', 'ONESOUL_SUPER_SECRET_KEY_2025').encode()


def _make_payload(email: str, hardware_id: str, plan_type: str, expiry_iso: str) -> str:
    payload = f"{email}|{hardware_id}|{plan_type}|{expiry_iso}"
    payload_b64 = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
    return payload_b64


def _sign(payload_b64: str) -> str:
    sig = hmac.new(SIGNING_SECRET, payload_b64.encode(), hashlib.sha256).hexdigest()
    # shorten but still strong
    return sig[:32]


def generate_license_token(email: str, hardware_id: str, plan_type: str, expiry_iso: str) -> str:
    """Create a tamper-proof license token bound to hardware"""
    payload_b64 = _make_payload(email, hardware_id, plan_type, expiry_iso)
    signature = _sign(payload_b64)
    return f"ONESOUL-{payload_b64}.{signature}"


def verify_license_token(token: str):
    """Verify token signature and return payload parts or None"""
    if not token.startswith("ONESOUL-") or '.' not in token:
        return None
    try:
        payload_b64, signature = token.replace("ONESOUL-", "", 1).split('.', 1)
        expected_sig = _sign(payload_b64)
        if not hmac.compare_digest(signature, expected_sig):
            return None
        # restore padding for b64 decode
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        decoded = base64.urlsafe_b64decode(padded.encode()).decode()
        email, hardware_id, plan_type, expiry_iso = decoded.split('|')
        return {
            "email": email,
            "hardware_id": hardware_id,
            "plan_type": plan_type,
            "expiry_iso": expiry_iso
        }
    except Exception:
        return None

def log_validation(license_key, hardware_id, ip, action, status, message):
    """Create a validation log entry"""
    try:
        log = ValidationLog(
            license_key=license_key,
            hardware_id=hardware_id,
            ip_address=ip,
            action=action,
            status=status,
            message=message
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        print(f"Error logging validation: {e}")

def create_security_alert(license_key, alert_type, description, severity='medium'):
    """Create a security alert"""
    try:
        alert = SecurityAlert(
            license_key=license_key,
            alert_type=alert_type,
            description=description,
            severity=severity
        )
        db.session.add(alert)
        db.session.commit()
    except Exception as e:
        print(f"Error creating security alert: {e}")

def calculate_days_remaining(expiry_date):
    """Calculate days remaining until expiry"""
    if not expiry_date:
        return 0
    delta = expiry_date - datetime.utcnow()
    return max(0, delta.days)

@api.route('/license/activate', methods=['POST'])
def activate_license():
    """
    Activate a license on a specific device

    Request body:
    {
        "license_key": "ONESOUL-XXXX-XXXX-XXXX-XXXX",
        "hardware_id": "sha256_hash_of_hardware",
        "device_name": "John's PC"
    }
    """
    try:
        data = request.get_json()
        license_key = data.get('license_key', '').strip()
        hardware_id = data.get('hardware_id', '').strip()
        device_name = data.get('device_name', 'Unknown Device').strip()
        ip_address = request.remote_addr

        # Validation
        if not license_key or not hardware_id:
            log_validation(license_key, hardware_id, ip_address, 'activate', 'failed', 'Missing license key or hardware ID')
            return jsonify({'success': False, 'message': 'License key and hardware ID are required'}), 400

        # Verify token signature/payload
        token_payload = verify_license_token(license_key)
        if not token_payload:
            log_validation(license_key, hardware_id, ip_address, 'activate', 'failed', 'Invalid or tampered license token')
            return jsonify({'success': False, 'message': 'Invalid license token'}), 400

        # Find license
        license_obj = License.query.filter_by(license_key=license_key).first()

        if not license_obj:
            log_validation(license_key, hardware_id, ip_address, 'activate', 'failed', 'License key not found')
            return jsonify({'success': False, 'message': 'Invalid license key'}), 404

        # Check if suspended
        if license_obj.is_suspended:
            log_validation(license_key, hardware_id, ip_address, 'activate', 'failed', 'License suspended')
            return jsonify({'success': False, 'message': 'This license has been suspended. Please contact support.'}), 403

        # Check if expired
        if datetime.utcnow() > license_obj.expiry_date:
            log_validation(license_key, hardware_id, ip_address, 'activate', 'failed', 'License expired')
            return jsonify({
                'success': False,
                'message': f'License expired on {license_obj.expiry_date.strftime("%Y-%m-%d")}. Please renew your subscription.'
            }), 403

        # Check token hardware matches request
        if token_payload.get('hardware_id') and token_payload.get('hardware_id') != hardware_id:
            log_validation(license_key, hardware_id, ip_address, 'activate', 'failed', 'Hardware mismatch in token')
            return jsonify({'success': False, 'message': 'License token is bound to a different hardware ID'}), 403

        # Check if already activated on a different device
        if license_obj.hardware_id and license_obj.hardware_id != hardware_id:
            # Different device trying to activate
            log_validation(license_key, hardware_id, ip_address, 'activate', 'failed', 'Already activated on different device')
            create_security_alert(
                license_key,
                'multiple_devices',
                f'Attempted activation from different device. Original: {license_obj.device_name}, New: {device_name}',
                'high'
            )
            return jsonify({
                'success': False,
                'message': f'License is already activated on "{license_obj.device_name}". Deactivate it first to use on this device.'
            }), 403

        # Same device re-activating or first time activation
        if not license_obj.hardware_id:
            license_obj.activation_count += 1

        license_obj.hardware_id = hardware_id
        license_obj.device_name = device_name
        license_obj.is_active = True
        license_obj.last_validation = datetime.utcnow()
        license_obj.updated_at = datetime.utcnow()

        db.session.commit()

        days_remaining = calculate_days_remaining(license_obj.expiry_date)

        log_validation(license_key, hardware_id, ip_address, 'activate', 'success', f'Activated on {device_name}')

        return jsonify({
            'success': True,
            'message': f'License activated successfully on {device_name}',
            'plan_type': license_obj.plan_type,
            'expiry_date': license_obj.expiry_date.isoformat(),
            'days_remaining': days_remaining
        }), 200

    except Exception as e:
        db.session.rollback()
        print(f"Error in activate_license: {e}")
        return jsonify({'success': False, 'message': 'Internal server error'}), 500

@api.route('/license/validate', methods=['POST'])
def validate_license():
    """
    Validate a license

    Request body:
    {
        "license_key": "ONESOUL-XXXX-XXXX-XXXX-XXXX",
        "hardware_id": "sha256_hash_of_hardware"
    }
    """
    try:
        data = request.get_json()
        license_key = data.get('license_key', '').strip()
        hardware_id = data.get('hardware_id', '').strip()
        ip_address = request.remote_addr

        if not license_key or not hardware_id:
            return jsonify({'valid': False, 'message': 'License key and hardware ID are required'}), 400

        license_obj = License.query.filter_by(license_key=license_key).first()

        if not license_obj:
            log_validation(license_key, hardware_id, ip_address, 'validate', 'failed', 'License not found')
            return jsonify({'valid': False, 'message': 'Invalid license key'}), 404

        # Verify token signature/payload
        token_payload = verify_license_token(license_key)
        if not token_payload:
            log_validation(license_key, hardware_id, ip_address, 'validate', 'failed', 'Invalid or tampered license token')
            return jsonify({'valid': False, 'message': 'Invalid license token'}), 400

        # Check hardware ID match (token + stored)
        if token_payload.get('hardware_id') and token_payload.get('hardware_id') != hardware_id:
            log_validation(license_key, hardware_id, ip_address, 'validate', 'failed', 'Hardware mismatch in token')
            create_security_alert(
                license_key,
                'hardware_mismatch',
                f'Validation attempted with wrong hardware ID',
                'medium'
            )
            return jsonify({
                'valid': False,
                'message': 'Hardware ID mismatch. License is registered to a different device.'
            }), 403

        if license_obj.hardware_id != hardware_id:
            log_validation(license_key, hardware_id, ip_address, 'validate', 'failed', 'Hardware ID mismatch')
            create_security_alert(
                license_key,
                'hardware_mismatch',
                f'Validation attempted with wrong hardware ID',
                'medium'
            )
            return jsonify({
                'valid': False,
                'message': 'Hardware ID mismatch. License is registered to a different device.'
            }), 403

        # Check if suspended
        if license_obj.is_suspended:
            log_validation(license_key, hardware_id, ip_address, 'validate', 'failed', 'License suspended')
            return jsonify({'valid': False, 'is_suspended': True, 'message': 'License has been suspended'}), 403

        # Check expiry
        is_expired = datetime.utcnow() > license_obj.expiry_date
        days_remaining = calculate_days_remaining(license_obj.expiry_date)

        # Update last validation
        license_obj.last_validation = datetime.utcnow()
        license_obj.updated_at = datetime.utcnow()
        db.session.commit()

        log_validation(license_key, hardware_id, ip_address, 'validate', 'success', 'Valid')

        return jsonify({
            'valid': not is_expired,
            'is_expired': is_expired,
            'expiry_date': license_obj.expiry_date.isoformat(),
            'plan_type': license_obj.plan_type,
            'days_remaining': days_remaining,
            'message': 'License is valid' if not is_expired else 'License has expired'
        }), 200

    except Exception as e:
        db.session.rollback()
        print(f"Error in validate_license: {e}")
        return jsonify({'valid': False, 'message': 'Internal server error'}), 500

@api.route('/license/deactivate', methods=['POST'])
def deactivate_license():
    """
    Deactivate a license from current device

    Request body:
    {
        "license_key": "ONESOUL-XXXX-XXXX-XXXX-XXXX",
        "hardware_id": "sha256_hash_of_hardware"
    }
    """
    try:
        data = request.get_json()
        license_key = data.get('license_key', '').strip()
        hardware_id = data.get('hardware_id', '').strip()
        ip_address = request.remote_addr

        if not license_key or not hardware_id:
            return jsonify({'success': False, 'message': 'License key and hardware ID are required'}), 400

        license_obj = License.query.filter_by(license_key=license_key).first()

        if not license_obj:
            log_validation(license_key, hardware_id, ip_address, 'deactivate', 'failed', 'License not found')
            return jsonify({'success': False, 'message': 'Invalid license key'}), 404

        # Verify token signature/payload
        token_payload = verify_license_token(license_key)
        if not token_payload:
            log_validation(license_key, hardware_id, ip_address, 'deactivate', 'failed', 'Invalid or tampered license token')
            return jsonify({'success': False, 'message': 'Invalid license token'}), 400

        # Security: Verify hardware ID matches (token + stored)
        if token_payload.get('hardware_id') and token_payload.get('hardware_id') != hardware_id:
            log_validation(license_key, hardware_id, ip_address, 'deactivate', 'failed', 'Hardware mismatch in token')
            create_security_alert(
                license_key,
                'unauthorized_deactivation',
                f'Deactivation attempted with wrong hardware ID',
                'high'
            )
            return jsonify({
                'success': False,
                'message': 'Cannot deactivate. Hardware ID mismatch.'
            }), 403

        if license_obj.hardware_id != hardware_id:
            log_validation(license_key, hardware_id, ip_address, 'deactivate', 'failed', 'Hardware ID mismatch')
            create_security_alert(
                license_key,
                'unauthorized_deactivation',
                f'Deactivation attempted with wrong hardware ID',
                'high'
            )
            return jsonify({
                'success': False,
                'message': 'Cannot deactivate. Hardware ID mismatch.'
            }), 403

        # Deactivate
        license_obj.hardware_id = None
        license_obj.device_name = None
        license_obj.is_active = False
        license_obj.updated_at = datetime.utcnow()
        db.session.commit()

        log_validation(license_key, hardware_id, ip_address, 'deactivate', 'success', 'Deactivated')

        return jsonify({
            'success': True,
            'message': 'License deactivated successfully. You can now activate it on another device.'
        }), 200

    except Exception as e:
        db.session.rollback()
        print(f"Error in deactivate_license: {e}")
        return jsonify({'success': False, 'message': 'Internal server error'}), 500

@api.route('/license/status', methods=['POST'])
def license_status():
    """
    Get detailed license information

    Request body:
    {
        "license_key": "ONESOUL-XXXX-XXXX-XXXX-XXXX"
    }
    """
    try:
        data = request.get_json()
        license_key = data.get('license_key', '').strip()

        if not license_key:
            return jsonify({'success': False, 'message': 'License key is required'}), 400

        license_obj = License.query.filter_by(license_key=license_key).first()

        if not license_obj:
            return jsonify({'success': False, 'message': 'Invalid license key'}), 404

        days_remaining = calculate_days_remaining(license_obj.expiry_date)
        is_expired = datetime.utcnow() > license_obj.expiry_date

        return jsonify({
            'success': True,
            'license_key': license_obj.license_key,
            'email': license_obj.email,
            'plan_type': license_obj.plan_type,
            'purchase_date': license_obj.purchase_date.isoformat(),
            'expiry_date': license_obj.expiry_date.isoformat(),
            'device_name': license_obj.device_name,
            'is_active': license_obj.is_active,
            'is_expired': is_expired,
            'is_suspended': license_obj.is_suspended,
            'days_remaining': days_remaining,
            'last_validation': license_obj.last_validation.isoformat() if license_obj.last_validation else None
        }), 200

    except Exception as e:
        print(f"Error in license_status: {e}")
        return jsonify({'success': False, 'message': 'Internal server error'}), 500

@api.route('/admin/generate', methods=['POST'])
def generate_license():
    """
    Generate a new license (Admin only)

    Request body:
    {
        "email": "user@example.com",
        "user_name": "John",
        "hardware_id": "abc123...",
        "plan_type": "basic" or "pro",
        "duration_days": 30,
        "admin_key": "your_admin_secret_key"
    }
    """
    try:
        data = request.get_json()
        email = data.get('email', '').strip()
        user_name = data.get('user_name', '').strip()
        hardware_id = data.get('hardware_id', '').strip()
        plan_type = data.get('plan_type', '').strip().lower()
        duration_days = int(data.get('duration_days', 30))
        admin_key = data.get('admin_key', '').strip()

        # Simple admin key check (in production, use environment variable)
        ADMIN_KEY = os.getenv('ADMIN_KEY', 'ONESOUL_ADMIN_2025')  # TODO: Move to environment variable

        if admin_key != ADMIN_KEY:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 401

        if not email or not plan_type or not hardware_id:
            return jsonify({'success': False, 'message': 'Email, plan type, and hardware_id are required'}), 400

        if plan_type not in ['basic', 'pro']:
            return jsonify({'success': False, 'message': 'Invalid plan type. Must be: basic or pro'}), 400

        if duration_days <= 0:
            return jsonify({'success': False, 'message': 'duration_days must be positive'}), 400

        # Calculate expiry date
        purchase_date = datetime.utcnow()
        expiry_date = purchase_date + timedelta(days=duration_days)

        # Generate tamper-proof license token
        expiry_iso = expiry_date.isoformat()
        license_key = generate_license_token(email=email, hardware_id=hardware_id, plan_type=plan_type, expiry_iso=expiry_iso)

        # Create license
        new_license = License(
            license_key=license_key,
            email=email,
            plan_type=plan_type,
            purchase_date=purchase_date,
            expiry_date=expiry_date,
            hardware_id=hardware_id if hardware_id else None,
            device_name=user_name if user_name else None,
            is_active=False,  # Not active until first activation
            is_suspended=False,
            activation_count=0
        )

        db.session.add(new_license)
        db.session.commit()

        return jsonify({
            'success': True,
            'license_key': license_key,
            'email': email,
            'plan_type': plan_type,
            'expiry_date': expiry_date.isoformat(),
            'message': 'License generated successfully'
        }), 201

    except Exception as e:
        db.session.rollback()
        print(f"Error in generate_license: {e}")
        return jsonify({'success': False, 'message': 'Internal server error'}), 500

@api.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()}), 200
