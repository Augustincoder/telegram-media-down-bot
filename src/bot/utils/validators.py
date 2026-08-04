import re
from typing import Optional

# Endi nafaqat /reel/ balki /p/ (post) va /tv/ larni ham qabul qiladi
INSTAGRAM_LINK_PATTERN = re.compile(
    r'(?:https?:\/\/)?(?:www\.)?instagram\.com\/(?:p|reel|tv)\/([A-Za-z0-9_-]+)'
)

def extract_instagram_url(text: str) -> Optional[str]:
    match = INSTAGRAM_LINK_PATTERN.search(text)
    if match:
        shortcode = match.group(1)
        # Hamma linklarni /p/ ga standartlashtirib qaytaramiz (baza keshi uchun bir xillik)
        return f"https://www.instagram.com/p/{shortcode}/"
    return None
