import re
from typing import Optional

# Post, Reel va IGTV lar uchun
INSTAGRAM_LINK_PATTERN = re.compile(
    r'(?:https?:\/\/)?(?:www\.)?instagram\.com\/(?:p|reel|tv)\/([A-Za-z0-9_-]+)'
)

# Profil manzillari uchun (masalan: instagram.com/username). Zaxiradagi nomlarni (p, reel, tv) inkor qiladi.
INSTAGRAM_PROFILE_PATTERN = re.compile(
    r'(?:https?:\/\/)?(?:www\.)?instagram\.com\/(?!p\/|reel\/|tv\/|stories\/|explore)([A-Za-z0-9_.]+)\/?'
)

# Story'larning aniq manzillari uchun (masalan: instagram.com/stories/username/123)
INSTAGRAM_STORY_LINK_PATTERN = re.compile(
    r'(?:https?:\/\/)?(?:www\.)?instagram\.com\/stories\/([A-Za-z0-9_.]+)\/?'
)

def extract_instagram_url(text: str) -> Optional[str]:
    match = INSTAGRAM_LINK_PATTERN.search(text)
    if match:
        shortcode = match.group(1)
        return f"https://www.instagram.com/p/{shortcode}/"
    return None

def extract_instagram_username(text: str) -> Optional[str]:
    match = INSTAGRAM_STORY_LINK_PATTERN.search(text)
    if match:
        return match.group(1)
        
    match = INSTAGRAM_PROFILE_PATTERN.search(text)
    if match:
        return match.group(1)
        
    return None
