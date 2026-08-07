import json
import getpass
from instagrapi import Client
from instagrapi.exceptions import ChallengeRequired

def get_challenge_code(username, choice):
    mode = "SMS" if choice == 1 else "Email"
    print(f"\n[DIQQAT] Instagram {username} uchun tasdiqlash kodini {mode} orqali yubordi!")
    return input(f"Iltimos, {mode} ga kelgan 6 xonali kodni kiriting: ")

def main():
    print("=== Instagram Session Generator ===")
    print("Bu script kompyuteringizda Instagram'ga ulanib, xavfsiz 'session_json' kodini oladi.")
    print("Shundan so'ng u kodni Northflank'da ishlatishingiz mumkin.\n")
    
    username = input("Instagram Username: ").strip()
    password = getpass.getpass("Instagram Password: ").strip()
    
    cl = Client()
    cl.challenge_code_handler = get_challenge_code
    
    try:
        print("\nTizimga kirilmoqda (iltimos kuting)...")
        cl.login(username, password)
        print("Muvaffaqiyatli kirildi!\n")
        
        settings = cl.get_settings()
        session_json = json.dumps(settings)
        
        print("=" * 50)
        print("Sizning INSTAGRAM_SESSION_JSON kodingiz:\n")
        print(session_json)
        print("\n" + "=" * 50)
        print("Yuqoridagi to'liq kodni nusxalang va Northflank'da INSTAGRAM_SESSION_JSON (yoki IG_SESSION_JSON) deb saqlang.")
        
    except ChallengeRequired:
        print("\nXatolik: Tasdiqlash talab etildi (Challenge Required) lekin hal qilib bo'lmadi.")
    except Exception as e:
        print(f"\nXatolik yuz berdi: {e}")

if __name__ == "__main__":
    main()
