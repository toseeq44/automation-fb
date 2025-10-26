````markdown
# Cookies (DO NOT COMMIT)

This folder is used to store local cookies files for downloading private/age-restricted content.

Important:
- DO NOT commit real cookies or session files to git.
- If you need to share configuration, share a README or example file without secrets.

How to export cookies (example with yt-dlp):
```bash
# Example (replace <browser> and <url>):
yt-dlp --cookies-from-browser <browser> --cookies cookies/tiktok.txt <url>
```

Where to place cookies:
- Project cookies folder: `./cookies/tiktok.txt`
- Desktop fallback (optional): `~/Desktop/toseeq-cookies.txt`

If your cookies have been exposed:
- Revoke sessions on the platform (logout everywhere), rotate credentials or API keys immediately.
- Remove the cookie files from the git history (use git filter-repo or BFG; coordinate with collaborators).
````
