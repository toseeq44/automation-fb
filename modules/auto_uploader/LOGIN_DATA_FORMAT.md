# login_data.txt Format Guide

The `login_data.txt` file contains credentials and page information for Facebook automation.

## Location

Place `login_data.txt` in each account folder:
```
creator_shortcuts/
├── IX/
│   └── mrprofessor0342@gmail.com/
│       ├── login_data.txt          ← Here!
│       └── Creators/
│           └── My Page Name/
└── email@example.com/
    ├── login_data.txt              ← Or here!
    └── Creators/
        └── ...
```

---

## Format 1: Key-Value (Recommended ✅)

Simple and easy to read format:

```
browser: ix
email: mrprofessor0342@gmail.com
password: Tosee@1122
page_name: My Page Name
page_id: 123456789
```

### Multiple Pages

Separate multiple pages with `---`:

```
browser: ix
email: mrprofessor0342@gmail.com
password: Tosee@1122
page_name: First Page
page_id: 123456789
---
browser: ix
email: mrprofessor0342@gmail.com
password: Tosee@1122
page_name: Second Page
page_id: 987654321
```

### Field Descriptions

| Field | Aliases | Required | Description |
|-------|---------|----------|-------------|
| `browser` | `browser_type` | No | Browser type: `ix`, `gologin`, `vpn`, or `free_automation` |
| `email` | `facebook_email` | **YES** | Facebook account email/username |
| `password` | `facebook_password` | **YES** | Facebook account password |
| `page_name` | `page` | **YES** | Page/creator name (must match folder name!) |
| `page_id` | `pageid` | No | Facebook page ID |
| `profile_name` | `profile` | No | Browser profile name (defaults to page_name) |

---

## Format 2: Pipe-Separated (Legacy)

For advanced users:

```
profile_name|facebook_email|facebook_password|page_name|page_id|browser_type
Profile1|mrprofessor0342@gmail.com|Tosee@1122|My Page Name|123456789|ix
Profile2|mrprofessor0342@gmail.com|Tosee@1122|Another Page|987654321|ix
```

### Order of Fields:
1. `profile_name` - Browser profile name
2. `facebook_email` - Facebook login email
3. `facebook_password` - Facebook login password
4. `page_name` - **Must match creator folder name!**
5. `page_id` - Facebook page ID (optional)
6. `browser_type` - `ix`, `gologin`, `vpn`, or `free_automation` (optional)

---

## Important Notes

### ⚠️ Page Name Must Match Folder Name!

The `page_name` field **MUST** exactly match your creator folder name:

```
creator_shortcuts/
└── mrprofessor0342@gmail.com/
    ├── login_data.txt
    └── Creators/
        └── My Page Name/        ← This name must match!
```

**login_data.txt:**
```
browser: ix
email: mrprofessor0342@gmail.com
password: Tosee@1122
page_name: My Page Name          ← Must be exactly the same!
page_id: 123456789
```

### 🔐 Security

Passwords are automatically encrypted and stored securely by the application.

### 📝 Comments

Add comments with `#`:

```
# This is my main account
browser: ix
email: mrprofessor0342@gmail.com
password: Tosee@1122
page_name: My Page Name
page_id: 123456789
```

---

## Example: Complete Setup

**Folder Structure:**
```
Desktop/
└── creator_shortcuts/
    └── IX/
        └── mrprofessor0342@gmail.com/
            ├── login_data.txt
            └── Creators/
                ├── Tech Reviews/
                │   ├── bulk videos.lnk
                │   ├── single video.lnk
                │   └── profile.lnk
                └── Gaming Channel/
                    ├── bulk videos.lnk
                    ├── single video.lnk
                    └── profile.lnk
```

**login_data.txt:**
```
# First Page - Tech Reviews
browser: ix
email: mrprofessor0342@gmail.com
password: Tosee@1122
page_name: Tech Reviews
page_id: 123456789
---
# Second Page - Gaming Channel
browser: ix
email: mrprofessor0342@gmail.com
password: Tosee@1122
page_name: Gaming Channel
page_id: 987654321
```

---

## Troubleshooting

### Error: "No login data for..."

**Problem:** File format is incorrect or missing required fields.

**Solution:** Make sure you have:
- `email` field
- `password` field
- `page_name` field

### Error: "No creator shortcuts found"

**Problem:** `page_name` doesn't match folder name.

**Solution:** Check that folder name in `Creators/` exactly matches `page_name` in login_data.txt.

### Error: "Invalid format at line X"

**Problem:** Using wrong format or syntax error.

**Solution:**
- Use key-value format: `key: value`
- Or pipe format: `field1|field2|field3|field4|field5|field6`
- Don't mix both formats!

---

## Quick Start Template

Copy this template and fill in your details:

```
browser: ix
email: YOUR_EMAIL@gmail.com
password: YOUR_PASSWORD
page_name: YOUR_PAGE_NAME
page_id: YOUR_PAGE_ID
```

Remember:
1. ✅ Replace placeholders with actual values
2. ✅ Make sure `page_name` matches your creator folder name
3. ✅ Use `---` to separate multiple pages
