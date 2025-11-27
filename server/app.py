"""
OneSoul License Server
Flask application for managing license activation and validation
"""
import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox

import requests
from flask import Flask
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from models import db
from routes import api


def create_app():
    """Create and configure Flask application"""
    app = Flask(__name__)

    # Configuration
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///licenses.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['JSON_SORT_KEYS'] = False

    # Initialize database
    db.init_app(app)

    # Initialize rate limiter
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=["200 per day", "50 per hour"],
        storage_uri="memory://"
    )

    # Apply rate limiting to API routes
    limiter.limit("10 per minute")(api)

    # Register blueprints
    app.register_blueprint(api, url_prefix='/api')

    # Create tables
    with app.app_context():
        db.create_all()
        print("Database tables created successfully")

    @app.route('/')
    def index():
        return {
            'service': 'OneSoul License Server',
            'version': '1.0.0',
            'status': 'running',
            'endpoints': {
                'health': '/api/health',
                'activate': '/api/license/activate',
                'validate': '/api/license/validate',
                'deactivate': '/api/license/deactivate',
                'status': '/api/license/status',
                'admin_generate': '/api/admin/generate'
            }
        }

    return app


if __name__ == '__main__':
    app = create_app()
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('DEBUG', 'False').lower() == 'true'
    admin_key = os.getenv('ADMIN_KEY', 'ONESOUL_ADMIN_2025')

    def run_flask():
        app.run(host='0.0.0.0', port=port, debug=debug, use_reloader=False)

    def open_admin_gui():
        root = tk.Tk()
        root.title("OneSoul License Admin")
        root.geometry("520x480")

        style = ttk.Style()
        style.theme_use('clam')
        style.configure('Main.TFrame', background='#0f172a')
        style.configure('TLabel', background='#0f172a', foreground='#e2e8f0')
        style.configure('TEntry', fieldbackground='#1f2937', foreground='#e2e8f0')
        style.configure('Accent.TButton', background='#10b981', foreground='white')
        style.map('Accent.TButton', background=[('active', '#0ea472')])
        style.configure('Secondary.TButton', background='#1f2937', foreground='#e2e8f0')
        style.map('Secondary.TButton', background=[('active', '#111827')])

        root.configure(bg='#0f172a')
        main_frame = ttk.Frame(root, padding=12, style='Main.TFrame')
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Email").grid(row=0, column=0, sticky="w")
        email_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=email_var, width=40).grid(row=0, column=1, sticky="ew")

        ttk.Label(main_frame, text="User Name").grid(row=1, column=0, sticky="w")
        name_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=name_var, width=30).grid(row=1, column=1, sticky="ew")

        ttk.Label(main_frame, text="Hardware ID").grid(row=2, column=0, sticky="w")
        hw_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=hw_var, width=40).grid(row=2, column=1, sticky="ew")

        ttk.Label(main_frame, text="Plan").grid(row=3, column=0, sticky="w")
        plan_var = tk.StringVar(value="basic")
        ttk.Combobox(main_frame, textvariable=plan_var, values=["basic", "pro"], state="readonly").grid(
            row=3, column=1, sticky="ew"
        )

        ttk.Label(main_frame, text="Duration (days)").grid(row=4, column=0, sticky="w")
        duration_var = tk.IntVar(value=30)
        ttk.Entry(main_frame, textvariable=duration_var, width=10).grid(row=4, column=1, sticky="w")

        ttk.Label(main_frame, text="Admin Key").grid(row=5, column=0, sticky="w")
        admin_var = tk.StringVar(value=admin_key)
        ttk.Entry(main_frame, textvariable=admin_var, width=40, show="*").grid(row=5, column=1, sticky="ew")

        ttk.Label(main_frame, text="License Key (result)").grid(row=6, column=0, sticky="w")
        result_var = tk.StringVar()
        result_entry = ttk.Entry(main_frame, textvariable=result_var, width=40, state="readonly")
        result_entry.grid(row=6, column=1, sticky="ew")
        def copy_result():
            val = result_var.get().strip()
            if not val:
                messagebox.showwarning("Nothing to copy", "Generate a license first.")
                return
            root.clipboard_clear()
            root.clipboard_append(val)
            messagebox.showinfo("Copied", "License key copied to clipboard.")
        ttk.Button(main_frame, text="Copy Key", style='Secondary.TButton', command=copy_result).grid(
            row=6, column=2, padx=(6, 0), sticky="ew"
        )

        status_var = tk.StringVar(value="Ready")
        ttk.Label(main_frame, textvariable=status_var, foreground="#2c3e50").grid(
            row=7, column=0, columnspan=3, sticky="w", pady=(8, 4)
        )

        def generate_key():
            email = email_var.get().strip()
            plan = plan_var.get().strip().lower()
            duration = duration_var.get()
            hw = hw_var.get().strip()
            name = name_var.get().strip()
            adm = admin_var.get().strip()

            if not email or not plan or not adm:
                messagebox.showerror("Missing Data", "Email, plan, and admin key are required.")
                return

            payload = {
                "email": email,
                "user_name": name,
                "hardware_id": hw,
                "plan_type": plan,
                "duration_days": duration,
                "admin_key": adm
            }

            try:
                resp = requests.post(f"http://localhost:{port}/api/admin/generate", json=payload, timeout=10)
                data = resp.json()
                if resp.status_code == 201 and data.get("success"):
                    result_var.set(data.get("license_key", ""))
                    status_var.set(f"Success. Expires: {data.get('expiry_date', '')}")
                    messagebox.showinfo("License Created", f"License Key:\n{data.get('license_key')}")
                else:
                    status_var.set(data.get("message", f"Failed: {resp.status_code}"))
                    messagebox.showerror("Error", data.get("message", "Failed to generate license"))
            except Exception as e:
                status_var.set(f"Error: {e}")
                messagebox.showerror("Error", str(e))

        ttk.Button(main_frame, text="Generate License", style='Accent.TButton', command=generate_key).grid(
            row=8, column=0, columnspan=3, pady=10, sticky="ew", ipadx=6, ipady=4
        )

        info_text = (
            "Tokens are tamper-proof:\n"
            "✅ Signed (HMAC-SHA256)\n"
            "✅ Hardware ID bound\n"
            "✅ Signature verification on server"
        )
        ttk.Label(main_frame, text=info_text, foreground="#10b981").grid(
            row=9, column=0, columnspan=3, sticky="w", pady=(4, 0)
        )

        for i in range(3):
            main_frame.columnconfigure(i, weight=1)

        root.mainloop()

    print(
        "------------------------------------------------------------\n"
        f"  OneSoul License Server\n"
        f"  Running on: http://localhost:{port}\n"
        f"  Debug Mode: {debug}\n"
        "------------------------------------------------------------"
    )

    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    open_admin_gui()
