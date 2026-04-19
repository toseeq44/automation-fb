"""
API routes for license management
"""
from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
from models import db, License, ValidationLog, SecurityAlert, ClientInstallation
import secrets
import base64
import hmac
import hashlib
import os
import json
from pathlib import Path

from lease_signing import issue_lease_token
from presence import presence_state_code
from request_meta import extract_client_public_ip

api = Blueprint('api', __name__)

SIGNING_SECRET = os.getenv('LICENSE_SIGNING_SECRET', 'ONESOUL_SUPER_SECRET_KEY_2025').encode()
LEASE_DURATION_DAYS = int(os.getenv('LEASE_DURATION_DAYS', '7'))


def _route_log(tag: str, **fields):
    try:
        bits = [f"{key}={value}" for key, value in fields.items()]
        print(f"[LicenseServer][{tag}] " + " | ".join(bits), flush=True)
    except Exception:
        pass


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


def _parse_iso_datetime(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        if parsed.tzinfo is not None:
            parsed = parsed.replace(tzinfo=None)
        return parsed
    except Exception:
        return None


def _client_presence_state(client: ClientInstallation) -> str:
    return presence_state_code(client.last_seen, bool(client.is_online))


def _tracking_exports_root() -> Path:
    root = Path(__file__).resolve().parent / "client_tracking_exports"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _issue_client_lease(license_obj, hardware_id: str, installation_id: str):
    return issue_lease_token(
        license_key=license_obj.license_key,
        hardware_id=hardware_id,
        installation_id=installation_id,
        plan_type=license_obj.plan_type,
        duration_days=LEASE_DURATION_DAYS,
    )


def _upsert_client_installation(
    *,
    license_obj,
    installation_id: str,
    hardware_id: str,
    device_name: str,
    app_version: str,
    ip_address: str,
    lan_ip: str = "",
    event_type: str,
    lease_expires_at=None,
):
    if not installation_id:
        return None

    client = ClientInstallation.query.filter_by(installation_id=installation_id).first()
    if not client:
        client = ClientInstallation(
            installation_id=installation_id,
            license_key=license_obj.license_key,
            hardware_id=hardware_id,
            first_seen=datetime.utcnow(),
        )
        db.session.add(client)

    client.license_key = license_obj.license_key
    client.hardware_id = hardware_id
    client.device_name = device_name or license_obj.device_name
    client.app_version = app_version or client.app_version
    client.last_ip = ip_address
    client.last_lan_ip = lan_ip or client.last_lan_ip
    client.last_status = event_type
    client.last_seen = datetime.utcnow()
    client.is_online = event_type != 'shutdown'
    client.updated_at = datetime.utcnow()
    if lease_expires_at:
        client.lease_expires_at = lease_expires_at
    return client

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
        installation_id = data.get('installation_id', '').strip()
        app_version = data.get('app_version', '').strip()
        client_lan_ip = data.get('client_lan_ip', '').strip()
        ip_address = extract_client_public_ip(request)
        _route_log("activate_request", installation_id=installation_id or "-", device=device_name or "-", public_ip=ip_address, lan_ip=client_lan_ip or "-")

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
        lease = _issue_client_lease(license_obj, hardware_id, installation_id or hardware_id)
        _upsert_client_installation(
            license_obj=license_obj,
            installation_id=installation_id or hardware_id,
            hardware_id=hardware_id,
            device_name=device_name,
            app_version=app_version,
            ip_address=ip_address,
            lan_ip=client_lan_ip,
            event_type='startup',
            lease_expires_at=_parse_iso_datetime(lease['lease_payload']['lease_expires_at']),
        )
        db.session.commit()

        log_validation(license_key, hardware_id, ip_address, 'activate', 'success', f'Activated on {device_name}')
        _route_log("activate_success", installation_id=installation_id or hardware_id, device=device_name, public_ip=ip_address)

        return jsonify({
            'success': True,
            'message': f'License activated successfully on {device_name}',
            'plan_type': license_obj.plan_type,
            'expiry_date': license_obj.expiry_date.isoformat(),
            'days_remaining': days_remaining,
            'lease_token': lease['lease_token'],
            'lease_expires_at': lease['lease_payload']['lease_expires_at'],
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
        installation_id = data.get('installation_id', '').strip()
        app_version = data.get('app_version', '').strip()
        client_lan_ip = data.get('client_lan_ip', '').strip()
        ip_address = extract_client_public_ip(request)
        _route_log("validate_request", installation_id=installation_id or "-", public_ip=ip_address, lan_ip=client_lan_ip or "-")

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
        lease = _issue_client_lease(license_obj, hardware_id, installation_id or hardware_id)
        _upsert_client_installation(
            license_obj=license_obj,
            installation_id=installation_id or hardware_id,
            hardware_id=hardware_id,
            device_name=license_obj.device_name or 'Unknown Device',
            app_version=app_version,
            ip_address=ip_address,
            lan_ip=client_lan_ip,
            event_type='running',
            lease_expires_at=_parse_iso_datetime(lease['lease_payload']['lease_expires_at']),
        )
        db.session.commit()

        log_validation(license_key, hardware_id, ip_address, 'validate', 'success', 'Valid')
        _route_log("validate_success", installation_id=installation_id or hardware_id, public_ip=ip_address, expired=is_expired)

        return jsonify({
            'valid': not is_expired,
            'is_expired': is_expired,
            'expiry_date': license_obj.expiry_date.isoformat(),
            'plan_type': license_obj.plan_type,
            'days_remaining': days_remaining,
            'message': 'License is valid' if not is_expired else 'License has expired',
            'lease_token': lease['lease_token'],
            'lease_expires_at': lease['lease_payload']['lease_expires_at'],
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
        installation_id = data.get('installation_id', '').strip()
        ip_address = extract_client_public_ip(request)

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
        if installation_id:
            client = ClientInstallation.query.filter_by(installation_id=installation_id).first()
            if client:
                client.is_online = False
                client.last_status = 'shutdown'
                client.last_seen = datetime.utcnow()
                client.updated_at = datetime.utcnow()
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


@api.route('/license/heartbeat', methods=['POST'])
def heartbeat_license():
    """
    Track a running client instance and refresh its signed lease.

    Request body:
    {
        "license_key": "...",
        "hardware_id": "...",
        "installation_id": "...",
        "device_name": "...",
        "app_version": "1.0.0",
        "event_type": "startup|running|shutdown"
    }
    """
    try:
        data = request.get_json()
        license_key = data.get('license_key', '').strip()
        hardware_id = data.get('hardware_id', '').strip()
        installation_id = data.get('installation_id', '').strip()
        device_name = data.get('device_name', 'Unknown Device').strip()
        app_version = data.get('app_version', '').strip()
        event_type = data.get('event_type', 'running').strip().lower() or 'running'
        client_lan_ip = data.get('client_lan_ip', '').strip()
        ip_address = extract_client_public_ip(request)
        _route_log("heartbeat_request", installation_id=installation_id or "-", event=event_type, public_ip=ip_address, lan_ip=client_lan_ip or "-")

        if not license_key or not hardware_id or not installation_id:
            return jsonify({'success': False, 'message': 'license_key, hardware_id, and installation_id are required'}), 400

        license_obj = License.query.filter_by(license_key=license_key).first()
        if not license_obj:
            log_validation(license_key, hardware_id, ip_address, 'heartbeat', 'failed', 'License not found')
            return jsonify({'success': False, 'message': 'Invalid license key'}), 404

        token_payload = verify_license_token(license_key)
        if not token_payload:
            log_validation(license_key, hardware_id, ip_address, 'heartbeat', 'failed', 'Invalid or tampered license token')
            return jsonify({'success': False, 'message': 'Invalid license token'}), 400

        if token_payload.get('hardware_id') and token_payload.get('hardware_id') != hardware_id:
            log_validation(license_key, hardware_id, ip_address, 'heartbeat', 'failed', 'Hardware mismatch in token')
            return jsonify({'success': False, 'message': 'Hardware ID mismatch'}), 403

        if license_obj.hardware_id and license_obj.hardware_id != hardware_id:
            log_validation(license_key, hardware_id, ip_address, 'heartbeat', 'failed', 'Hardware mismatch in record')
            return jsonify({'success': False, 'message': 'License is registered to a different device'}), 403

        if license_obj.is_suspended:
            log_validation(license_key, hardware_id, ip_address, 'heartbeat', 'failed', 'License suspended')
            return jsonify({'success': False, 'message': 'License has been suspended'}), 403

        if datetime.utcnow() > license_obj.expiry_date:
            log_validation(license_key, hardware_id, ip_address, 'heartbeat', 'failed', 'License expired')
            return jsonify({'success': False, 'message': 'License has expired'}), 403

        lease = _issue_client_lease(license_obj, hardware_id, installation_id)
        client = _upsert_client_installation(
            license_obj=license_obj,
            installation_id=installation_id,
            hardware_id=hardware_id,
            device_name=device_name,
            app_version=app_version,
            ip_address=ip_address,
            lan_ip=client_lan_ip,
            event_type=event_type,
            lease_expires_at=_parse_iso_datetime(lease['lease_payload']['lease_expires_at']),
        )

        license_obj.last_validation = datetime.utcnow()
        license_obj.updated_at = datetime.utcnow()
        db.session.commit()

        log_validation(license_key, hardware_id, ip_address, 'heartbeat', 'success', f'Heartbeat: {event_type}')
        _route_log("heartbeat_success", installation_id=installation_id, event=event_type, presence=client.last_status, public_ip=ip_address)

        return jsonify({
            'success': True,
            'message': f'Heartbeat accepted ({event_type})',
            'lease_token': lease['lease_token'],
            'lease_expires_at': lease['lease_payload']['lease_expires_at'],
            'server_time': datetime.utcnow().isoformat(),
        }), 200

    except Exception as e:
        db.session.rollback()
        print(f"Error in heartbeat_license: {e}")
        return jsonify({'success': False, 'message': 'Internal server error'}), 500


@api.route('/license/poll-tasks', methods=['POST'])
def poll_client_tasks():
    """Return pending admin-triggered tasks for an online client."""
    try:
        data = request.get_json()
        license_key = data.get('license_key', '').strip()
        hardware_id = data.get('hardware_id', '').strip()
        installation_id = data.get('installation_id', '').strip()
        device_name = data.get('device_name', 'Unknown Device').strip()
        client_lan_ip = data.get('client_lan_ip', '').strip()
        ip_address = extract_client_public_ip(request)
        _route_log("poll_request", installation_id=installation_id or "-", public_ip=ip_address, lan_ip=client_lan_ip or "-")

        if not license_key or not hardware_id or not installation_id:
            return jsonify({'success': False, 'message': 'license_key, hardware_id, and installation_id are required'}), 400

        license_obj = License.query.filter_by(license_key=license_key).first()
        if not license_obj or license_obj.hardware_id != hardware_id:
            return jsonify({'success': False, 'message': 'Invalid client identity'}), 403

        client = _upsert_client_installation(
            license_obj=license_obj,
            installation_id=installation_id,
            hardware_id=hardware_id,
            device_name=device_name,
            app_version="",
            ip_address=ip_address,
            lan_ip=client_lan_ip,
            event_type="running",
        )

        pending_task = client.pending_task or ""
        pending_task_id = client.pending_task_id or ""
        message = "No pending tasks."

        if pending_task:
            client.active_task_id = pending_task_id
            client.pending_task = None
            client.pending_task_id = None
            client.pending_task_created_at = None
            client.last_tracking_status = "dispatched"
            message = "Pending task dispatched."
        elif client.active_task_id and str(client.last_tracking_status or "").strip().lower() == "dispatched":
            pending_task = "collect_creator_urls"
            pending_task_id = client.active_task_id or ""
            message = "Active task re-dispatched after reconnect."
        db.session.commit()
        _route_log("poll_result", installation_id=installation_id, task=pending_task or "none", task_id=pending_task_id or "-")

        return jsonify({
            'success': True,
            'message': message,
            'pending_task': pending_task,
            'pending_task_id': pending_task_id,
        }), 200
    except Exception as e:
        db.session.rollback()
        print(f"Error in poll_client_tasks: {e}")
        return jsonify({'success': False, 'message': 'Internal server error'}), 500


@api.route('/license/report-creator-links', methods=['POST'])
def report_creator_links():
    """Receive tracked creator-profile links from a client and store them on the server."""
    try:
        data = request.get_json()
        license_key = data.get('license_key', '').strip()
        hardware_id = data.get('hardware_id', '').strip()
        installation_id = data.get('installation_id', '').strip()
        task_id = data.get('task_id', '').strip()
        device_name = data.get('device_name', 'Unknown Device').strip()
        client_lan_ip = data.get('client_lan_ip', '').strip()
        success = bool(data.get('success', False))
        file_name = (data.get('file_name', '') or '').strip()
        creator_count = int(data.get('creator_count', 0) or 0)
        payload = data.get('payload') or {}
        error_message = (data.get('error_message', '') or '').strip()
        ip_address = extract_client_public_ip(request)
        _route_log("track_report_request", installation_id=installation_id or "-", task_id=task_id or "-", success=success, public_ip=ip_address)

        if not license_key or not hardware_id or not installation_id or not task_id:
            return jsonify({'success': False, 'message': 'Missing required tracking fields'}), 400

        license_obj = License.query.filter_by(license_key=license_key).first()
        if not license_obj or license_obj.hardware_id != hardware_id:
            return jsonify({'success': False, 'message': 'Invalid client identity'}), 403

        client = ClientInstallation.query.filter_by(installation_id=installation_id).first()
        if not client:
            return jsonify({'success': False, 'message': 'Unknown installation'}), 404

        if client.active_task_id != task_id:
            return jsonify({'success': False, 'message': 'Tracking task is not active anymore'}), 409

        client.last_ip = ip_address
        client.last_lan_ip = client_lan_ip or client.last_lan_ip
        client.device_name = device_name or client.device_name
        client.last_seen = datetime.utcnow()
        client.last_status = "running"
        client.is_online = True
        client.updated_at = datetime.utcnow()
        client.active_task_id = None

        if success:
            safe_name = Path(file_name).name or f"creator_links_{installation_id}.json"
            export_dir = _tracking_exports_root() / installation_id
            export_dir.mkdir(parents=True, exist_ok=True)
            output_path = export_dir / safe_name
            with open(output_path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, ensure_ascii=False)

            client.last_tracking_status = "completed"
            client.last_tracking_error = None
            client.last_links_file = str(output_path)
            client.last_links_count = creator_count
            client.last_links_updated_at = datetime.utcnow()
            message = f"Creator links saved ({creator_count})"
            _route_log("track_report_saved", installation_id=installation_id, file=safe_name, creator_count=creator_count)
        else:
            client.last_tracking_status = "failed"
            client.last_tracking_error = error_message or "Unknown tracking error"
            message = client.last_tracking_error
            _route_log("track_report_failed", installation_id=installation_id, error=message)

        db.session.commit()
        return jsonify({'success': True, 'message': message}), 200
    except Exception as e:
        db.session.rollback()
        print(f"Error in report_creator_links: {e}")
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


@api.route('/admin/request-creator-links', methods=['POST'])
def request_creator_links():
    """Queue a creator-links tracking task for a currently-online client."""
    try:
        data = request.get_json()
        installation_id = data.get('installation_id', '').strip()
        admin_key = data.get('admin_key', '').strip()
        ADMIN_KEY = os.getenv('ADMIN_KEY', 'ONESOUL_ADMIN_2025')

        if admin_key != ADMIN_KEY:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 401

        if not installation_id:
            return jsonify({'success': False, 'message': 'installation_id is required'}), 400

        client = ClientInstallation.query.filter_by(installation_id=installation_id).first()
        if not client:
            return jsonify({'success': False, 'message': 'Client installation not found'}), 404

        if _client_presence_state(client) != "online":
            _route_log("admin_track_blocked", installation_id=installation_id, reason="client_not_online")
            return jsonify({'success': False, 'message': 'Client is not currently online'}), 409

        if client.pending_task or client.active_task_id:
            _route_log("admin_track_blocked", installation_id=installation_id, reason="task_already_pending")
            return jsonify({'success': False, 'message': 'A tracking task is already queued or running for this client'}), 409

        client.pending_task = 'collect_creator_urls'
        client.pending_task_id = secrets.token_hex(8)
        client.pending_task_created_at = datetime.utcnow()
        client.last_tracking_status = 'queued'
        client.last_tracking_error = None
        client.updated_at = datetime.utcnow()
        db.session.commit()
        _route_log("admin_track_queued", installation_id=installation_id, task_id=client.pending_task_id)

        return jsonify({
            'success': True,
            'message': 'Creator link tracking queued successfully.',
            'task_id': client.pending_task_id,
        }), 200
    except Exception as e:
        db.session.rollback()
        print(f"Error in request_creator_links: {e}")
        return jsonify({'success': False, 'message': 'Internal server error'}), 500

@api.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()}), 200
