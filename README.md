# FileSense

A desktop file-browser for Windows that adds AI-powered and manual descriptions to every file and folder — like sticky notes, but smart.

Descriptions are stored in portable `.filesense.json` sidecar files that travel with your project when you share it.

---

## Features

| Feature | Detail |
|---|---|
| Descriptions & Narratives | Short/Extended descriptions + evolution narratives for file history |
| AI generation | Uses Groq API with fast models |
| Manual editing | Write your own — locks out AI auto-updates |
| Semantic Tags | AI-generated topic tags for structured retrieval |
| Live Watcher | Real-time file system monitoring via Watchdog |
| SQLite Memory Layer | FTS5 full-text search across all descriptions |
| Sensitive data | Advanced entropy scanning; detects API keys, passwords, tokens, PII, etc. |
| Share export | One click strips sensitive flags and privacy history for safe sharing |
| Portable | Sidecar `.filesense.json` travels with the folder |
| Graph View | Horizontal mind-map of files and folders, 3 levels deep |

---

## Quick start

### 1. Install Python 3.11+

Download from https://python.org

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Get a free Groq API key


1. Go to https://console.groq.com
2. Sign up (free)
3. Create an API key starting with `gsk_...`

### 4. Run

```bash
python main.py
```

### 5. Add your API key

Click **Settings** in the toolbar -> paste your Groq key -> Save.

---

## To use

1. **Open a folder** — click `Open Folder` in the toolbar or navigate the left tree.
2. **Browse files** — the centre panel shows all files with mini-descriptions.
3. **Click a file or folder** — the right panel shows full descriptions.
4. **Edit manually** — click `Edit` to write your own description (locks AI updates for that item). The edit panel slides in inline — no popup.
5. **Refresh with AI** — click `Refresh with AI` to re-generate. If manually written, an inline confirmation banner appears — no popup.
6. **Refresh all** — `Refresh All` in the toolbar re-describes everything in the current folder.
7. **Graph View** — `Graph View` shows a horizontal mind-map of your folder, 3 levels deep.
8. **Home** — `Home` returns to the file browser from Settings or Graph View.
9. **Export** — `Export` writes a `.filesense.share.json` with sensitive entries scrubbed.

---

## Toolbar order

```
Settings | Open Folder | Home | Graph View | Refresh All | Export
```

---

## How descriptions are generated

```
Individual files -> AI reads content -> short + long desc + tags + evolution narrative
        | (all file short descs collected)
Folder description -> AI summarises file descriptions (bottom-up)
        | (subfolders summarised)
Parent folder description
```

### File size tiers

| Type | Strategy |
|---|---|
| Code / text / markdown | First 3 000 chars + last 500 chars |
| CSV / TSV | Header + first 20 rows |
| JSON | First 3 000 chars |
| Excel | First 3 sheets, 20 rows each |
| PDF | First 10 pages (up to 3 000 chars) |
| Word (.docx) | Full text, first 3 000 chars |
| Images | Resized thumbnail -> Groq vision model |
| > 10 MB | Filename + size only |

### Sensitive data detection

Patterns detected (values are **never** included in descriptions):
- API keys (Groq, OpenAI, Google, Stripe, Twilio, SendGrid, etc.)
- OAuth tokens (GitHub, Slack, Facebook)
- High-entropy strings (via Shannon entropy checking)
- Passwords / secrets in variable assignments
- Private key PEM headers
- Bearer tokens, AWS credentials
- Database / connection strings
- PII (SSNs, credit card numbers)

---

## Auto-update rules

| Condition | Behaviour |
|---|---|
| File modified | Real-time update via Watchdog file system observer |
| File not touched in > 4 days | Skip (stop auto-updating) |
| Description manually written | Never auto-update; show inline confirm on manual refresh |
| AI key not configured | Skip AI calls |

---

## Sidecar format v2

`.filesense.json` lives inside every annotated folder (automatically migrated from v1):

```json
{
  "version": "2.0",
  "folder": {
    "short_desc": "Django REST API for the user service.",
    "long_desc": "...",
    "tags": ["backend", "django"],
    "manual_lock": false,
    "last_updated": "2025-03-15T14:32:00",
    "sensitive_detected": false
  },
  "files": {
    "views.py": {
      "short_desc": "API view handlers for user CRUD endpoints.",
      "long_desc": "...",
      "narrative": "Started as a basic view module, evolved to handle full CRUD operations.",
      "tags": ["api", "views", "crud"],
      "manual_lock": false,
      "last_updated": "2025-03-15T14:32:10",
      "last_file_modified": "2025-03-14T09:10:00",
      "sensitive_detected": false,
      "sensitive_types": [],
      "history": [],
      "last_error": ""
    }
  }
}
```

---

## Project structure

```
filesense/
├── main.py              Entry point
├── config.py            App configuration + persistence
├── requirements.txt
├── core/
│   ├── ai_engine.py     Groq API calls, tags, narratives, entropy detection
│   ├── memory.py        SQLite memory index + FTS5 full-text search
│   ├── sidecar.py       Read/write .filesense.json persistence files
│   └── watcher.py       Real-time background scheduler/workers
└── ui/
    ├── main_window.py   Main window, toolbar, inline panels
    ├── desc_panel.py    Right-side description panel widget
    ├── dialogs.py       Inline Settings, Edit Desc, AI-confirm panels
    ├── graph.py         Horizontal mind-map (Graph View)
    └── styles.py        QSS dark theme
```

---

## Settings

All settings are saved to `~/.filesense/config.json`.

| Setting | Default | Description |
|---|---|---|
| Groq API key | -- | Your `gsk_...` key |
| Text model | `llama-3.1-8b-instant` | Groq model for descriptions |
| Memory DB Path | `~/.filesense/memory.db` | Location of the SQLite memory store |
| Check interval | 30 min | How often auto-update runs |
| Stop after | 4 days | Idle threshold for auto-updates |
| Max file size | 10 MB | Files larger than this are skipped |
| Text head limit | 3 000 chars | How much of a text file to send |
| CSV preview rows | 20 | Rows sent for CSV/Excel files |
