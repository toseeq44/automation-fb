# Firebase MVP Setup

This project now supports a Firestore-only MVP license flow.

## What you need to do

1. Create a Firebase project on the Spark plan.
2. Enable Cloud Firestore in Native mode.
3. Enable Authentication -> Sign-in method -> Anonymous.
4. Create a Web App in the Firebase project.
5. Copy these values into your local `config.json` under `license.firebase`:

```json
{
  "license": {
    "provider": "firebase",
    "heartbeat_interval_seconds": 300,
    "task_poll_interval_seconds": 60,
    "firebase": {
      "api_key": "YOUR_API_KEY",
      "auth_domain": "YOUR_PROJECT.firebaseapp.com",
      "project_id": "YOUR_PROJECT_ID",
      "app_id": "YOUR_APP_ID"
    }
  }
}
```

## Firestore collections

Create and manage these collections from Firebase Console:

- `licenses`
- `installations`
- `creator_snapshots`
- `license_events`

### Example `licenses/{license_key}` document

```json
{
  "active": true,
  "plan": "basic",
  "expiryAt": "2026-12-31T00:00:00+00:00",
  "boundHardwareId": "",
  "boundDeviceName": "",
  "lastSeenAt": "",
  "lastInstallationId": "",
  "notes": ""
}
```

## Suggested MVP Firestore rules

These rules are intentionally lightweight for the MVP:

```text
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /{document=**} {
      allow read, write: if request.auth != null;
    }
  }
}
```

## On-demand creator snapshot

To request creator URLs from a client:

1. Open `installations/{installation_id}` in Firebase Console.
2. Set `pendingTask` to `collect_creator_urls`.
3. Wait for the client poll cycle.
4. Review the uploaded payload in `creator_snapshots/{installation_id}`.
