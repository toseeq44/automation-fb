# Nuitka Critical-Module Experiment

This flow is intentionally **local-only** and **separate from the production PyInstaller build**.

## Goal

Compile only the most sensitive custom modules to `.pyd` extension modules:

- `modules.license.hardware_id`
- `modules.license.firebase_license_manager`
- `modules.license.license_manager`
- `modules.license.creator_links_tracking`
- `modules.license.lease_crypto`
- `modules.security.hardening`

This avoids trying to compile heavy/high-risk areas like:

- `PyQt` surface
- `Playwright`
- `Selenium`
- `MediaPipe`
- `torch`
- `video_editor`
- `auto_uploader`

## Why This Approach

Official Nuitka docs support compiling:

- a single module with `--module`
- a package with `--module some_package --include-package=some_package`

For this repo, **single-module compilation is safer** than package-mode because:

- we only want to harden critical code
- package-mode is trickier when source and compiled packages coexist

Sources:

- https://nuitka.net/user-documentation/use-cases.html
- https://nuitka.net/info/compiled-package-hidden-by-package.html
- https://nuitka.net/info/unwanted-module.html

## Step-by-Step

1. Install Nuitka in the same Python environment used by the project:

```powershell
.\.venv\Scripts\python.exe -m pip install -U nuitka
```

2. Build the compiled overlay:

```powershell
python build_nuitka_critical.py
```

Or:

```powershell
build_nuitka_critical_modules.bat
```

3. Verify the compiled modules are loading:

```powershell
python launch_nuitka_critical_test.py --probe-only
```

4. Launch the app with the compiled overlay active:

```powershell
python launch_nuitka_critical_test.py
```

## What The Builder Produces

- compiled `.pyd` files under `.nuitka_critical`
- Nuitka XML reports under `build/nuitka_reports`
- temporary module build output under `build/nuitka_module_build`

## Hybrid Release Build

After the local overlay test passes, you can build a hybrid release like this:

```powershell
build_hybrid_secure.bat
```

What this does:

1. rebuilds the critical Nuitka modules
2. probes them
3. enables a PyInstaller spec flag
4. packages the app while including the compiled `.pyd` files
5. excludes the source versions of those specific modules from the PyInstaller bundle

This keeps the normal app architecture, but swaps these sensitive modules into compiled form for release packaging.

## Important Notes

- This does **not** touch the production PyInstaller build.
- This does **not** replace the source files in the repo.
- This is only the first-pass feasibility check.
- If this works, the next step is deciding how to integrate the compiled modules into the release build safely.

## Recommended Test Order

1. `--probe-only`
2. app startup
3. license validation
4. activation dialog
5. Firebase validation/heartbeat
6. admin GUI
7. suspicious process / integrity flows

If any of the above breaks, stop there and fix before trying deeper integration.
