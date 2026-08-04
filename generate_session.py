import asyncio
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

API_ID = int(input("Enter your API_ID: ").strip())
API_HASH = input("Enter your API_HASH: ").strip()

async def main():
    async with TelegramClient(StringSession(), API_ID, API_HASH) as client:
        session_string = client.session.save()
        print("\n--- MUVAFFAQIYATLI ---\n")
        print("Sizning USERBOT_SESSION kodingiz:\n")
        print(session_string)
        print("\nUshbu kodni nusxalang va .env fayliga TELEGRAM_USERBOT_SESSION_STRING o'zgaruvchisiga qo'shing.")

if __name__ == "__main__":
    asyncio.run(main())
