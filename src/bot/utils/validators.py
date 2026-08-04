import re
from typing import Optional

# Regex pattern for Instagram Reels (and general posts)
INSTAGRAM_REEL_PATTERN = re.compile(
    r"(?:https?:\/\/)?(?:www\.)?instagram\.com\/(?:reel|p)\/([A-Za-z0-9_-]+)\/?(?:\S+)?"
)

def extract_instagram_url(text: str) -> Optional[str]:
    """
    Extracts the first Instagram Reel or Post URL from the given text.
    Returns the clean URL or None if not found.
    """
    match = INSTAGRAM_REEL_PATTERN.search(text)
    if match:
        shortcode = match.group(1)
        return f"https://www.instagram.com/reel/{shortcode}/"
    return None
