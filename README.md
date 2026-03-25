# FolderScribe 📁✏

A desktop file-browser for Windows that adds **AI-powered + manual descriptions** to every file and folder — like sticky notes, but smart.

Descriptions are stored in portable `.folderscribe.json` sidecar files that travel with your project when you share it.

---

## Features

| Feature | Detail |
|---|---|
| 📝 Descriptions | Short (≤20 words) + Extended (≤60 words) per file and folder |
| 🤖 AI generation | Uses Groq API (fast, free tier available) |
| ✏ Manual editing | Write your own — locks out AI auto-updates |
| 🔄 Auto-refresh | Checks every 30 min (configurable); skips files idle > 4 days |
| 🔐 Sensitive data | Detects API keys, passwords, tokens — never puts values in desc |
| 📤 Share export | One click strips sensitive flags for safe sharing |
| 📁 Portable | Sidecar `.folderscribe.json` travels with the folder |

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
3. Create an API key starting with `gsk_…`

### 4. Run

```bash
python main.py
```

### 5. Add your API key

Click **⚙ Settings** in the toolbar → paste your Groq key → Save.

---

## How to use

1. **Open a folder** — click `📂 Open Folder` in the toolbar or navigate the left tree.
2. **Browse files** — the centre panel shows all files with mini-descriptions.
3. **Click a file or folder** — the right panel shows full descriptions.
4. **Edit manually** — click `✏ Edit` to write your own description (this locks AI updates for that item).
5. **Refresh with AI** — click `🤖 Refresh with AI` to re-generate. If manually written, a confirmation popup appears.
6. **Refresh all** — `🔄 Refresh All` in the toolbar re-describes everything in the current folder.
7. **Share** — `📤 Export (share-safe)` writes a `.folderscribe.share.json` with sensitive entries scrubbed.

---

## How descriptions are generated

```
Individual files → AI reads content → short + long desc
        ↓ (all file short descs collected)
Folder description → AI summarises file descriptions (bottom-up)
        ↓ (subfolders summarised)
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
| Images | Resized thumbnail → Groq vision model |
| > 10 MB | Filename + size only |

### Sensitive data detection

Patterns detected (values are **never** included in descriptions):
- API keys (`gsk_`, `sk-`, `AIza`, `ghp_`, …)
- Passwords / secrets in variable assignments
- Private key PEM headers
- Bearer tokens, AWS credentials
- Database / connection strings

---

## Auto-update rules

| Condition | Behaviour |
|---|---|
| File modified since last description | Re-describe on next 30-min cycle |
| File not touched in > 4 days | Skip (stop auto-updating) |
| Description manually written | Never auto-update; show AI popup on manual refresh |
| AI key not configured | Skip AI calls; show "No API Key" chip |

---

## Sidecar format

`.folderscribe.json` lives inside every annotated folder:

```json
{
  "version": "1.0",
  "folder": {
    "short_desc": "Django REST API for the user service.",
    "long_desc": "...",
    "manual_lock": false,
    "last_updated": "2025-03-15T14:32:00",
    "sensitive_detected": false
  },
  "files": {
    "views.py": {
      "short_desc": "API view handlers for user CRUD endpoints.",
      "long_desc": "...",
      "manual_lock": false,
      "last_updated": "2025-03-15T14:32:10",
      "last_file_modified": "2025-03-14T09:10:00",
      "sensitive_detected": false,
      "sensitive_types": []
    }
  }
}
```

---

## Project structure

```
folderscribe/
├── main.py              Entry point
├── config.py            App configuration + persistence
├── requirements.txt
├── core/
│   ├── ai_engine.py     Groq API calls, file extraction, sensitive detection
│   ├── sidecar.py       Read/write .folderscribe.json files
│   └── watcher.py       Background scheduler + update workers
└── ui/
    ├── main_window.py   Main window, tree, file list
    ├── desc_panel.py    Right-side description panel widget
    ├── dialogs.py       Settings, Edit, AI-confirm dialogs
    └── styles.py        QSS dark theme
```

---

## Settings

All settings are saved to `~/.folderscribe/config.json`.

| Setting | Default | Description |
|---|---|---|
| Groq API key | — | Your `gsk_…` key |
| Text model | `llama3-8b-8192` | Groq model for descriptions |
| Check interval | 30 min | How often auto-update runs |
| Stop after | 4 days | Idle threshold for auto-updates |
| Max file size | 10 MB | Files larger than this are skipped |
| Text head limit | 3 000 chars | How much of a text file to send |
| CSV preview rows | 20 | Rows sent for CSV/Excel files |
