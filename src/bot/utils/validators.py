import re

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

def extract_instagram_url(text: str) -> str | None:
    match = INSTAGRAM_LINK_PATTERN.search(text)
    if match:
        shortcode = match.group(1)
        return f"https://www.instagram.com/p/{shortcode}/"
    return None

def extract_instagram_username(text: str) -> str | None:
    match = INSTAGRAM_STORY_LINK_PATTERN.search(text)
    if match:
        return match.group(1)
        
    match = INSTAGRAM_PROFILE_PATTERN.search(text)
    if match:
        return match.group(1)
        
    return None

# Telegram Story kabi manzillar uchun
TELEGRAM_STORY_PATTERN = re.compile(
    r'(?:https?:\/\/)?(?:t\.me|telegram\.me)\/(c\/)?([A-Za-z0-9_]+)\/s\/(\d+)'
)

def extract_telegram_story_info(text: str) -> tuple[str, int] | None:
    """
    Qaytaradi: (peer_nomi, story_id)
    Masalan: ('durov', 1) yoki ('c/123456789', 5)
    """
    match = TELEGRAM_STORY_PATTERN.search(text)
    if match:
        is_private = match.group(1)
        peer = match.group(2)
        story_id = int(match.group(3))
        
        if is_private:
            # Agar t.me/c/12345/s/1 bo'lsa
            peer = f"-100{peer}"
            
        return (peer, story_id)
    return None

def extract_simple_username(text: str) -> str | None:
    text = text.strip()
    if " " not in text and not text.startswith("http"):
        if text.startswith("@"):
            return text[1:]
        # Username regex: faqta harf, son, pastki chiziq va nuqta
        if re.match(r'^[A-Za-z0-9_\.]+$', text):
            return text
    return None
