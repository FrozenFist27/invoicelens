"""Create <project>/.env by copying ONLY the keys this project needs from the
workspace secrets.env. Values are never printed or logged."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SECRETS = ROOT.parent / "secrets.env"
NEEDED = ["ANTHROPIC_API_KEY", "LLM_PROVIDER", "LLM_MODEL"]

# Read secrets.env without echoing values
kv = {}
with open(SECRETS, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        kv[k.strip()] = v.strip().strip('"').strip("'")

lines = []
for k in NEEDED:
    if k in kv and kv[k]:
        lines.append(f"{k}={kv[k]}")
    elif k == "LLM_PROVIDER":
        lines.append("LLM_PROVIDER=anthropic")
    elif k == "LLM_MODEL":
        lines.append("LLM_MODEL=claude-haiku-5-5")
# project-specific non-secret settings
_tess = os.environ.get("TESSERACT_CMD", "C:/Program Files/Tesseract-OCR/tesseract.exe")
lines.append(f"TESSERACT_CMD={_tess}")
lines.append("REVIEW_THRESHOLD=0.7")
lines.append("MAX_RETRIES=2")

env_path = ROOT / ".env"
env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"wrote {env_path} with {len(lines)} keys (values not shown)")
