# ER EPOWERdoc Automation Bridge

An AI automation system built by **Rasm** for **Frisco ER** that bridges a modern web dashboard with the legacy **EPOWERdoc (EPD)** Electronic Health Record system via GUI automation.

---

## What This Does

When a patient checks in through the web dashboard, it sends a webhook to this Python server running on the clinic's Windows machine. The server then automatically drives the EPOWERdoc desktop application — opening screens, filling in fields, and saving — as if a human were typing. This eliminates manual double-entry of patient data between systems.

---

## Development Environment

> **Critical context for future agents and developers:**

- **Code is written on a Mac (macOS)** and pushed to GitHub.
- **The application runs on a Windows 11 Pro (x64) machine** at the clinic.
- The deployment workflow is: write on Mac → push to GitHub → pull on Windows → run on Windows.
- `pywinauto` is a **Windows-only** library. The server **will not start on macOS** without modification. Do not attempt to run the full server locally on a Mac — it will crash on import.
- All UI automation testing must be done on the Windows machine with EPOWERdoc open.
- The Windows machine runs EPOWERdoc under the process name **`EPD.exe`**.

---

## Architecture

### Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.14+ |
| Web server | FastAPI + Uvicorn |
| Data validation | Pydantic v2 + pydantic-settings |
| GUI automation | pywinauto (UIA backend) |
| Config | python-dotenv (.env file) |
| Target OS | Windows 11 Pro x64 |

### Networking

```
Web Dashboard
     │
     │  HTTPS POST (webhook)
     ▼
Secure Tunnel (Ngrok / Cloudflare)
     │
     │  HTTP POST → localhost
     ▼
FastAPI Server (this app)
     │
     │  pywinauto UIA calls
     ▼
EPOWERdoc (EPD.exe) — running on same Windows machine
```

The web dashboard sends patient data to a secure tunnel URL. The tunnel forwards it to the FastAPI server running locally on the Windows machine. The server drives EPOWERdoc's GUI directly.

### Project Structure

```
er-epowerdocs-automation/
│
├── main.py                        # Entry point — creates FastAPI app, mounts router
│
├── app/
│   ├── config.py                  # Loads settings from .env (Pydantic Settings)
│   │
│   ├── shared/
│   │   └── epd_connect.py         # Shared EPD process connection (used by all flows)
│   │
│   ├── models/
│   │   └── register_patient.py    # Pydantic payload model for registration flow
│   │
│   ├── flows/
│   │   └── register_patient.py    # Full registration automation logic
│   │
│   └── routers/
│       └── webhook.py             # All HTTP endpoints + shared flow dispatcher
│
├── inspect_epd.py                 # Dev utility: prints EPD UI control identifiers
├── inspect_add_pt.md              # Output of inspect_epd.py on the Add Patient screen
├── inspect_add_existing_pt.md     # Output with an existing patient visible in results
├── inspect_registration_pt.md     # Output of the Registration screen
│
├── requirements.txt
├── .env.example                   # Safe template — copy to .env and fill in values
├── .gitignore                     # .env is strictly gitignored
└── README.md
```

---

## How to Add a New Flow

Each automation workflow (flow) is fully self-contained. Adding one requires exactly three steps:

1. **`app/models/your_flow.py`** — Define a Pydantic model for the webhook payload.
2. **`app/flows/your_flow.py`** — Write the pywinauto automation logic. Expose a single `run(payload)` function.
3. **`app/routers/webhook.py`** — Add one `@router.post("/your-endpoint")` block that calls `_run_flow(your_flow.run, payload)`.

Nothing else in the codebase needs to change.

---

## Flows

### 1. Register Patient — `POST /webhook/register`

Registers a new patient or opens an existing one in EPOWERdoc.

**Payload:**
```json
{
  "first_name":      "John",
  "last_name":       "Doe",
  "dob":             "1990-01-15",
  "gender":          "M",
  "cell_number":     "2145550100",
  "chief_complaint": "chest pain",
  "insurance_id":    "ABC123"
}
```

**Workflow:**
1. Connects to the running `EPD.exe` process via pywinauto UIA backend
2. Clicks **ADD Patient** on the main Frisco Registration panel (`auto_id="L1"`)
3. Fills Last Name, First Name, DOB (split into Month/Day/Year fields), and Gender in the Patient Search form
4. Waits 1.5 seconds for EPD's auto-search to run
5. **If an existing patient appears** in the results grid (`lLName0`) → clicks their row
6. **If no match** → clicks the **New Patient** button (`auto_id="cmdAddVisit"`)
7. On the Registration screen: unchecks "No cell phone number" if needed, fills the Cell field (`auto_id="txtCell"`), clicks **Save and Close** (`auto_id="btnSaveClose"`)

---

## HIPAA Compliance

This application handles Protected Health Information (PHI). The following constraints are enforced throughout the codebase and must never be violated:

| Rule | Implementation |
|---|---|
| **Zero PHI in logs** | All `logger` calls use only metadata strings. PHI field values are never interpolated into log messages. |
| **No PHI on disk** | No `FileHandler` loggers. No temp files. No database writes. Patient data exists only in volatile RAM during execution. |
| **PHI cleared from RAM** | The payload object is explicitly `del`'d in the `finally` block of every endpoint after the flow completes. |
| **Webhook authentication** | Every request must include an `X-Webhook-Secret` header. Validated using `hmac.compare_digest` (constant-time, prevents timing attacks). |
| **Secrets never committed** | `.env` is gitignored. All credentials live in `.env` on the Windows machine only. |
| **No Swagger UI** | `docs_url=None`, `redoc_url=None` — the API schema is not browsable on the live server. |
| **No access logs** | `access_log=False` on Uvicorn — access logs would echo request bodies containing PHI. |

---

## Setup (Windows Machine)

### Prerequisites

- Python 3.14+ ([python.org](https://python.org/downloads)) — check **"Add Python to PATH"** during install
- Git ([git-scm.com](https://git-scm.com/download/win))
- EPOWERdoc (`EPD.exe`) installed and licensed

### First-Time Setup

```powershell
# Clone the repo
git clone https://github.com/NayeemBelal/er-epowerdocs-automation.git
cd er-epowerdocs-automation

# Install dependencies
pip install -r requirements.txt

# Create your .env from the template
copy .env.example .env
# Open .env in Notepad and fill in real values
notepad .env

# Run the server
python main.py
```

### Updating

```powershell
git pull
python main.py
```

---

## Environment Variables (`.env`)

| Variable | Description |
|---|---|
| `SERVER_HOST` | Host to bind (default: `127.0.0.1`) |
| `SERVER_PORT` | Port to bind (default: `8000`) |
| `WEBHOOK_SECRET` | Shared secret sent in `X-Webhook-Secret` header by the dashboard |
| `EPOWER_PROCESS_NAME` | EPD executable name (confirmed: `EPD.exe`) |
| `UI_TIMEOUT` | Seconds pywinauto waits for controls to appear (default: `10`) |

Generate a strong webhook secret:
```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## Testing a Webhook Locally

Open a second PowerShell window while the server is running:

```powershell
$headers = @{
    "Content-Type"    = "application/json"
    "X-Webhook-Secret" = "your_secret_here"
}
$body = '{"first_name":"EPD","last_name":"TEST","dob":"1979-10-05","gender":"F","cell_number":"2145550100","chief_complaint":"test","insurance_id":"ABC123"}'

Invoke-RestMethod -Uri "http://127.0.0.1:8000/webhook/register" -Method POST -Headers $headers -Body $body
```

---

## Inspecting EPOWERdoc UI Controls

When building a new flow, run this script with the target EPD screen open to discover control identifiers:

```powershell
python inspect_epd.py
```

Paste the output into a `.md` file in the repo for reference (see `inspect_add_pt.md` etc.). Use `auto_id` values to locate controls in pywinauto — prefer `auto_id` over title-based lookups as titles can change with locale or version.

---

## Future Work

- [ ] Additional flows (chief complaint entry, insurance verification, etc.)
- [ ] PyInstaller `.exe` build via GitHub Actions for non-technical staff deployment
- [ ] Cloudflare / Ngrok tunnel configuration documentation
- [ ] Retry logic for transient UI timing failures
