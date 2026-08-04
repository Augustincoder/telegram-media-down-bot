# Roadmap — Media Downloader Telegram Bot

**Versiya:** 1.0
**Umumiy taxminiy muddat:** ~8-10 hafta (1 dasturchi, part-time/full-time aralash)

Har bir faza — mustaqil ishga tushiriladigan (deploy qilinadigan) bosqich. Shu tartibda borish tavsiya etiladi, chunki har keyingi faza avvalgisiga tayanadi.

---

## Faza 0 — Tayyorgarlik (3-5 kun)

**Maqsad:** Loyiha skeletini va infratuzilmani tayyorlash.

- [ ] Repo tuzilishi, Python muhiti (`poetry` yoki `venv`), `.env` konfiguratsiya tizimi
- [ ] Telegram bot yaratish (@BotFather), token olish
- [ ] `aiogram` asosida minimal "salom" bot (echo bot) ishga tushirish
- [ ] PostgreSQL/SQLite bazasini sozlash, asosiy jadvallar: `users`, `downloads`, `instagram_links`
- [ ] Redis o'rnatish (navbat va cache uchun)
- [ ] Arzon VPS'ni sozlash (masalan 1-2GB RAM), ffmpeg o'rnatish

**Natija:** Bot ishga tushadi, `/start` buyrug'iga javob beradi, infratuzilma tayyor.

---

## Faza 1 — Instagram Reels yuklab olish (MVP core #1) (1 hafta)

**Maqsad:** Eng muhim funksiya.

- [ ] `instagrapi` yoki `instaloader` integratsiyasi (public content uchun `instaloader` yetarli, xavfsizroq)
- [ ] Reels link validatsiyasi va media ID ajratib olish
- [ ] Redis + RQ orqali navbat tizimini ulash (bir nechta so'rovni parallel emas, navbat bilan boshqarish)
- [ ] Yuklab olish va Telegram'ga yuborish, yuklangan faylni diskdan darhol o'chirish
- [ ] Xatoliklarni boshqarish (private/o'chirilgan post holatlari)
- [ ] Media cache — bir xil link qayta so'ralsa, `file_id` orqali tezkor javob berish (bazaga link → file_id saqlash)
- [ ] Fayl hajmi 50MB dan katta bo'lsa foydalanuvchiga tushunarli xabar

**Natija:** Reels linkini yuborib, videoni watermark'siz olish mumkin.

---

## Faza 2 — Instagram va Telegram Story yuklab olish (1.5 hafta)

**Maqsad:** Story funksiyalarini qo'shish — bu ko'proq texnik murakkablikka ega, chunki login talab qiladi.

- [ ] Botning shaxsiy "xizmat" Instagram akkauntini sozlash (`instagrapi` orqali login, session cookie saqlash)
- [ ] Ochiq profil linki yuborilganda, o'sha profilning joriy story'larini olish
- [ ] Session'ni barqaror saqlash (login har safar emas, faqat kerak bo'lganda)
- [ ] Telegram tomonida — `Telethon`/`Pyrogram` orqali userbot sessiyasini sozlash
- [ ] Ochiq akkauntli foydalanuvchi username'i orqali uning joriy story'larini olish
- [ ] Ikkala holatda ham "story topilmadi" yoki "akkaunt yopiq" xabarlarini to'g'ri qaytarish

**Natija:** Ikkala platformadan ham ochiq profil story'larini yuklab olish ishlaydi.

**⚠️ Diqqat:** Bu faza eng ko'p sinov (testing) va monitoring talab qiladi, chunki norasmiy API'lar beqaror bo'lishi mumkin.

---

## Faza 3 — Instagram Pairing tizimi (2 hafta) — Asosiy innovatsiya

**Maqsad:** Loyihaning eng murakkab va farqlanuvchi qismini qurish.

- [ ] `/link_instagram` buyrug'i va pairing kod generatsiyasi (Redis'da TTL bilan)
- [ ] Foydalanuvchiga kodni qanday tasdiqlash kerakligi bo'yicha aniq yo'riqnoma (masalan: "shu kodni @bot_instagram akkauntiga DM qiling")
- [ ] Fon jarayon (background worker) — markaziy Instagram akkauntning DM inbox'ini muntazam tekshirish (polling, masalan har 20-30 soniyada)
- [ ] Kod topilganda, Instagram user ID ↔ Telegram user ID bog'lanishini bazaga yozish
- [ ] Bog'langandan keyin, o'sha Instagram foydalanuvchisidan kelgan yangi reels/post'larni aniqlash mantig'i
- [ ] Aniqlangan reels'ni avtomatik yuklab, bog'langan Telegram akkauntga yuborish
- [ ] Xavfsizlik: bir Instagram akkaunt faqat bitta Telegram akkauntga bog'lanishi, pairing kodni qayta ishlatib bo'lmasligi
- [ ] Akkaunt bloklanish xavfini kamaytirish choralari: so'rovlar orasida random kechikish, kunlik limit belgilash

**Natija:** Foydalanuvchi bir marta bog'lagach, keyin shunchaki markaziy Instagram akkauntga reels tashlasa, avtomatik Telegram'da video sifatida oladi.

---

## Faza 4 — Barqarorlashtirish va UX yaxshilash (1 hafta)

**Maqsad:** MVP'ni "production-ready" holatga keltirish.

- [ ] Xatoliklarni global boshqarish (try/except, foydalanuvchiga tushunarli xabarlar)
- [ ] Foydalanuvchi uchun `/help`, `/history` (yuklash tarixi) buyruqlari
- [ ] Kunlik/soatlik rate-limit tizimi (spam va server yuklanishini oldini olish)
- [ ] Logging va monitoring (masalan Sentry yoki oddiy log fayl + xatolik haqida admin'ga xabar)
- [ ] Load testing — bir vaqtda 10-20 so'rov kelganda server qanday ishlashini tekshirish

**Natija:** Bot barqaror, xatoliklarga chidamli, kuzatiladigan holatda.

---

## Faza 5 — Kengaytirilgan funksiyalar (ixtiyoriy, keyingi bosqichlar)

Bu funksiyalar MVP'dan keyin, foydalanuvchi fikr-mulohazasiga qarab tanlab qo'shiladi:

1. **Inline mode** (1-2 kun) — tez va yuqori qiymatli, birinchi navbatda qo'shish tavsiya etiladi
2. **Ko'p tilli interfeys** (2-3 kun) — o'zbek/rus/ingliz
3. **Premium/limit tizimi** (3-4 kun) — Telegram Stars yoki boshqa to'lov integratsiyasi bilan
4. **Guruh integratsiyasi** (2-3 kun) — botni guruhga qo'shib avtomatik link aniqlash

---

## Umumiy vaqt jadvali (xulosa)

| Faza | Mazmuni | Muddat |
|---|---|---|
| 0 | Infratuzilma | 3-5 kun |
| 1 | Instagram Reels | 1 hafta |
| 2 | Story'lar (IG + TG) | 1.5 hafta |
| 3 | Pairing tizimi | 2 hafta |
| 4 | Barqarorlashtirish | 1 hafta |
| **MVP jami** | | **~6-7 hafta** |
| 5 | Kengaytirilgan funksiyalar | +2-3 hafta (ixtiyoriy) |

---

## Muhim eslatma

Faza 2 va 3 (story'lar va pairing tizimi) eng ko'p texnik risk va noaniqlikni o'z ichiga oladi, chunki ular Instagram'ning norasmiy API'siga tayanadi. Tavsiya: MVP'ni avval Faza 1 (Reels) bilan chiqarib, real foydalanuvchi fikr-mulohazasini olib, keyin Faza 2-3'ga o'tish — bu risk va vaqtni oqilona taqsimlash imkonini beradi.
