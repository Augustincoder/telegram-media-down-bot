import asyncio
from bot.config import config
from bot.services.instagram import ig_service

async def test():
    if config.instagram_session_id:
        ig_service.login(None, None, session_id=config.instagram_session_id)
        
        # Test pending and threads
        try:
            threads = ig_service.client.direct_threads(amount=2)
            print(f"Got {len(threads)} threads.")
            for t in threads:
                print(f"Thread ID: {t.id}, Users: {[u.username for u in t.users]}")
                if t.messages:
                    m = t.messages[0]
                    print(f" Latest MSG ID: {m.id}, Type: {m.item_type}, Text: {m.text}")
        except Exception as e:
            print("Error:", e)

if __name__ == "__main__":
    asyncio.run(test())
