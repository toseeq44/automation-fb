"""
Database models for license management system
"""
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class License(db.Model):
    """License table for managing user subscriptions"""
    __tablename__ = 'licenses'

    id = db.Column(db.Integer, primary_key=True)
    license_key = db.Column(db.String(100), unique=True, nullable=False, index=True)
    email = db.Column(db.String(255), nullable=False)
    plan_type = db.Column(db.String(20), nullable=False)  # 'monthly', 'yearly', 'trial'
    purchase_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    expiry_date = db.Column(db.DateTime, nullable=False)
    hardware_id = db.Column(db.String(255), nullable=True)  # Null until activated
    device_name = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_suspended = db.Column(db.Boolean, default=False, nullable=False)
    activation_count = db.Column(db.Integer, default=0, nullable=False)
    last_validation = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    validation_logs = db.relationship('ValidationLog', backref='license', lazy=True, cascade='all, delete-orphan')
    security_alerts = db.relationship('SecurityAlert', backref='license', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<License {self.license_key} - {self.email}>'

    def to_dict(self):
        """Convert license object to dictionary"""
        return {
            'license_key': self.license_key,
            'email': self.email,
            'plan_type': self.plan_type,
            'purchase_date': self.purchase_date.isoformat() if self.purchase_date else None,
            'expiry_date': self.expiry_date.isoformat() if self.expiry_date else None,
            'device_name': self.device_name,
            'is_active': self.is_active,
            'is_suspended': self.is_suspended,
            'last_validation': self.last_validation.isoformat() if self.last_validation else None,
        }

class ValidationLog(db.Model):
    """Log all license validation attempts for monitoring"""
    __tablename__ = 'validation_logs'

    id = db.Column(db.Integer, primary_key=True)
    license_key = db.Column(db.String(100), db.ForeignKey('licenses.license_key'), nullable=False, index=True)
    hardware_id = db.Column(db.String(255), nullable=True)
    ip_address = db.Column(db.String(50), nullable=True)
    action = db.Column(db.String(20), nullable=False)  # 'activate', 'validate', 'deactivate'
    status = db.Column(db.String(20), nullable=False)  # 'success', 'failed', 'suspicious'
    message = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    def __repr__(self):
        return f'<ValidationLog {self.license_key} - {self.action} - {self.status}>'

class SecurityAlert(db.Model):
    """Track security alerts for suspicious activity"""
    __tablename__ = 'security_alerts'

    id = db.Column(db.Integer, primary_key=True)
    license_key = db.Column(db.String(100), db.ForeignKey('licenses.license_key'), nullable=False, index=True)
    alert_type = db.Column(db.String(50), nullable=False)  # 'multiple_devices', 'rapid_validation', etc.
    description = db.Column(db.Text, nullable=False)
    severity = db.Column(db.String(20), nullable=False)  # 'low', 'medium', 'high', 'critical'
    is_resolved = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    def __repr__(self):
        return f'<SecurityAlert {self.license_key} - {self.alert_type} - {self.severity}>'
