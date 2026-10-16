from __future__ import annotations

import os
import requests


def send_discord(message: str) -> bool:
    url = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
    if not url:
        return False
    r = requests.post(url, json={"content": message[:1900]}, timeout=15)
    r.raise_for_status()
    return True
