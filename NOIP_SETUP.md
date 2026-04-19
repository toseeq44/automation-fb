# No-IP Fixed URL Setup

## Goal

Use a stable fixed client URL without Quick Tunnel:

`http://os-license-5102.no-ip.org:5000`

After setup, your normal flow should be:

1. Run `server\start_license_server.bat`
2. Open admin panel
3. Activate/check clients

## Code Status

The app already prefers the fixed URL from `license_endpoints.json`.
Old `trycloudflare.com` URLs are ignored/cleaned automatically.

## One-Time Network Setup

### 1. No-IP hostname

Make sure your hostname is active:

- `os-license-5102.no-ip.org`

It should always point to your current public IP.

### 2. Router port forwarding

Create a rule in your router:

- External port: `5000`
- Protocol: `TCP`
- Internal IP: your server PC LAN IP
- Internal port: `5000`

Example internal IP:

- `192.168.100.2`

### 3. Windows Firewall

Allow inbound TCP port `5000` for Python/Waitress/server.

## Local Checks

In the admin panel:

- Open `Client Activity`
- Click `Fixed URL Status`

You should look for:

- `Local server health: OK`
- `DNS resolves to: ...`

If local health is OK but remote EXEs still cannot connect, the issue is usually:

- No-IP hostname not updated
- Router port forwarding missing
- Firewall blocking port `5000`

## Important

Do not use:

- `cloudflared.exe tunnel --url http://localhost:5000`

That creates a random Quick Tunnel URL and breaks the fixed URL model.
