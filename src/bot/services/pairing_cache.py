import random
import time


class PairingCache:
    def __init__(self):
        self.cache = {}
        self.ttl = 600  # 10 daqiqa yaroqli

    def generate_code(self, telegram_user_id: int) -> str:
        """Keshda saqlangan holda yangi 6 xonali tasodifiy kod yaratadi"""
        self._cleanup()
        code = str(random.randint(100000, 999999))
        self.cache[code] = (telegram_user_id, time.time() + self.ttl)
        return code

    def verify_code(self, code: str) -> int | None:
        """Kodni tekshiradi, agar to'g'ri bo'lsa uni keshdan o'chirib telegram_user_id ni qaytaradi"""
        self._cleanup()
        if code in self.cache:
            telegram_user_id, expire = self.cache.pop(code)
            return telegram_user_id
        return None

    def _cleanup(self):
        """Eskirgan kodlarni xotiradan tozalaydi"""
        now = time.time()
        expired = [k for k, v in self.cache.items() if v[1] < now]
        for k in expired:
            del self.cache[k]


pairing_cache = PairingCache()
