# PRD — Media Downloader Telegram Bot

**Versiya:** 1.0
**Sana:** 2026-08-03
**Muallif:** Senior dasturchi tahlili asosida tuzildi

---

## 1. Umumiy g'oya (Overview)

Bu bot foydalanuvchilarga turli platformalardan (Instagram, Telegram) media kontentni yuklab olish imkonini beruvchi universal Telegram bot bo'ladi. Botning asosiy farqlanuvchi xususiyati — foydalanuvchining shaxsiy Instagram akkauntini bot bilan "pairing" (bog'lash) qilib, keyin shu Instagram akkauntga tashlangan reels'larni avtomatik ravishda Telegram'ga video sifatida yuborish imkoniyati.

### 1.1 Muammo
- Foydalanuvchilar Instagram, Telegram'dan video/audio yuklab olish uchun bir nechta turli botlarga yoki saytlarga murojaat qilishadi.
- Instagram'da do'stlar tashlagan reels'ni telefon xotirasiga saqlab, keyin qayta yuklash noqulay va sekin.
- Ochiq profil story'larini kuzatish va saqlash uchun qulay vosita yo'q.

### 1.2 Yechim
Bitta bot orqali barcha asosiy yuklab olish ehtiyojlarini qoplovchi, tezkor va kengaytiriladigan tizim.

---

## 2. Maqsadli foydalanuvchilar (Target Users)

- Kundalik ijtimoiy tarmoq foydalanuvchilari (video/reels saqlashni yoqtiruvchilar)
- Kontent yaratuvchilar (repost, arxivlash uchun)
- O'zbekiston va MDH bozoridagi Telegram foydalanuvchilari (past internet tezligi, arzon hosting sharoitlarini hisobga olish kerak)

---

## 3. Asosiy funksiyalar (MVP — Core Features)

### 3.1 Instagram Reels yuklab olish
- Foydalanuvchi reels linkini yuborsa, bot videoni watermark'siz, original sifatda yuklab beradi

### 3.2 Instagram Story yuklab olish (ochiq profil)
- Foydalanuvchi ochiq (public) profil linkini yuborsa, bot shu profilning oxirgi qo'yilgan story'larini yuklab beradi
- Yopiq (private) akkauntlar uchun ishlamaydi — bu haqda foydalanuvchiga aniq xabar beriladi

### 3.3 Telegram Story yuklab olish
- Ochiq akkauntli foydalanuvchi username'i yoki linki yuborilganda, botning shaxsiy akkaunt sessiyasi (userbot, masalan Telethon/Pyrogram MTProto orqali) orqali o'sha akkauntning joriy story'larini yuklab beradi
- Telegram Bot API orqali story'larni o'qib bo'lmaydi — bu funksiya albatta userbot (user session) talab qiladi

### 3.4 Instagram akkaunt pairing (bog'lash) tizimi — asosiy innovatsiya
**Ishlash mantiqi:**
1. Foydalanuvchi botga `/link_instagram` buyrug'ini yuboradi
2. Bot noyob, vaqtinchalik pairing kod (masalan 6 xonali kod yoki chuqur link) generatsiya qiladi
3. Foydalanuvchi shu kodni maxsus Instagram akkauntga (botning "markaziy" Instagram akkaunti) biror shaklda yuboradi — masalan DM orqali, yoki bio/caption orqali tasdiqlash
4. Tizim shu kodni tekshirib, Instagram user ID'ni Telegram user ID bilan bazada bog'laydi
5. Shundan keyin foydalanuvchi o'sha markaziy Instagram akkauntga istalgan reels/post'ni yuborsa (repost yoki DM orqali forward qilsa), tizim buni avtomatik aniqlaydi va bog'langan Telegram akkauntga video shaklida yuboradi

**Texnik talablar:**
- Instagram akkaunt sessiyasini doimiy ochiq va faol saqlash (session cookie, login state)
- Instagram DM'larni real-vaqtda kuzatish (polling yoki webhook — Instagram rasmiy API bunga to'liq ochiq emas, shuning uchun instagrapi kabi kutubxonalar polling orqali ishlaydi)
- Rate-limit va akkaunt bloklanish xavfini boshqarish (bu eng katta texnik risk — pastda alohida bo'limda batafsil)

---

## 4. Kengaytirilgan funksiyalar (Phase 2+ takliflar)

Bu bo'lim — "yana qanday funksiya qo'shish mumkin" degan savolga javob:

| Funksiya | Tavsif | Muhimlik |
|---|---|---|
| Yuklab olish tarixi | Foydalanuvchi oldin nima yuklaganini ko'rish | O'rta |
| Inline mode | Istalgan chatda `@bot link` yozib to'g'ridan-to'g'ri yuborish | Yuqori — UX uchun juda foydali |
| Premium/limit tizimi | Bepul foydalanuvchilarga kunlik limit, premium — cheksiz | Biznes uchun muhim |
| Ko'p tilli interfeys | O'zbek, rus, ingliz tillarida | Yuqori (maqsadli auditoriya uchun) |
| Media keshlash (cache) | Bir marta yuklangan linkni qayta yuklamaslik, database'dan tezkor berish | Yuqori — server resursini tejaydi |
| Avtomatik format tanlash | Foydalanuvchi sozlamalarida "har doim 720p" kabi default belgilash | O'rta |
| Guruh/kanal integratsiyasi | Botni guruhga qo'shib, guruhdagi linklarni avtomatik aniqlash | O'rta |
| Referral/ulashish tizimi | Do'st taklif qilib bonus olish | Past (o'sish uchun) |

---

## 5. Texnik arxitektura va texnologiyalar

### 5.1 Dasturlash tili tanlovi — **Python** (tavsiya etiladi)

**Nima uchun Python:**
- `instagrapi` — Instagram private API bilan ishlash uchun eng yaxshi Python kutubxonasi (login, DM o'qish, story/reels yuklash)
- `instaloader` — ochiq profil story/post'larini yuklash uchun yengil alternativ
- `Telethon` yoki `Pyrogram` — Telegram MTProto protokoli orqali userbot yaratish (story yuklash uchun majburiy, chunki oddiy Bot API story'larga kirisha olmaydi)
- `aiogram` yoki `python-telegram-bot` (async versiya) — asosiy bot logikasi uchun, ikkalasi ham to'liq asinxron va past resurs sarflaydi
- `ffmpeg-python` yoki to'g'ridan-to'g'ri `ffmpeg` CLI — audio ajratib olish, video formatlarini konvertatsiya qilish uchun

**Node.js bilan solishtirganda:** Node.js'da ham `instagram-private-api` kabi variantlar bor, lekin Instagram uchun eng barqaror va tez yangilanadigan kutubxonalar aynan Python ekotizimida. Shuning uchun Python — bu loyiha uchun optimal tanlov.

### 5.2 Asosiy komponentlar

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Telegram Bot   │────▶│   Task Queue     │────▶│  Download Worker│
│  (aiogram)      │     │   (Redis + RQ)   │     │  (instagrapi)   │
└─────────────────┘     └──────────────────┘     └─────────────────┘
        │                                                   │
        ▼                                                   ▼
┌─────────────────┐                              ┌─────────────────┐
│  PostgreSQL/    │                              │  Local storage /│
│  SQLite (DB)    │                              │  temp fayl cache│
└─────────────────┘                              └─────────────────┘
        ▲
        │
┌─────────────────┐
│  Instagram      │  (Telethon/instagrapi orqali doimiy
│  Userbot Session│   ishlaydigan fon jarayon — DM va
│  (background)   │   pairing'ni kuzatadi)
└─────────────────┘
```

**Asosiy oqim:**
1. **Bot Layer (aiogram)** — foydalanuvchi bilan muloqot, buyruqlar, inline tugmalar
2. **Queue Layer (Redis + RQ/Celery)** — yuklab olish vazifalarini navbatga qo'yish, bir vaqtda ko'p so'rovni boshqarish, serverni haddan tashqari yuklanishdan saqlash
3. **Worker Layer** — haqiqiy yuklab olish ishini bajaruvchi fon jarayonlar (bir nechta worker parallel ishlashi mumkin)
4. **Storage** — yuklangan fayllar vaqtincha saqlanadi, yuborilgach o'chiriladi (disk to'lib qolmasligi uchun)
5. **Database** — foydalanuvchilar, pairing bog'lanishlari, yuklash tarixi, limitlar

### 5.3 Kuchsiz (low-resource) hosting uchun optimallashtirish

Bu loyihaning eng muhim texnik cheklovi — arzon VPS (1-2GB RAM, 1 vCPU) da ishlashi kerak. Tavsiyalar:

1. **Selenium/Playwright'dan qoching** — brauzer avtomatlashtirish juda ko'p RAM (300-500MB har bir instance) yeydi. Buning o'rniga API-based kutubxonalar (`instagrapi`) ishlating — ular HTTP so'rovlar orqali ishlaydi, brauzer kerak emas.
2. **Asinxron arxitektura** — `asyncio` asosidagi `aiogram` bir nechta so'rovni bitta thread'da, minimal xotira bilan boshqaradi.
3. **Navbat (queue) tizimi majburiy** — bir vaqtda 10 ta yuklab olish so'rovi kelsa, hammasi parallel ishga tushsa server "yiqiladi". Redis + RQ orqali navbat qo'yib, masalan bir vaqtda faqat 2-3 ta worker ishlashini cheklash kerak.
4. **Fayllarni darhol o'chirish** — yuklangan video Telegram'ga yuborilgach, diskdan darhol o'chirilishi kerak (disk to'lib qolmasligi uchun). Doimiy saqlash kerak bo'lsa — tashqi ob'ekt xotira (masalan Cloudflare R2, Backblaze B2 — arzon va tez) ishlatish tavsiya etiladi, lokal diskda emas.
5. **Video sifatini cheklash** — juda yuqori sifatli (4K) videolarni default holda taklif qilmaslik, chunki bu ham CPU (konvertatsiya), ham tarmoq trafigini ko'p yeydi.
6. **Media keshlash** — bir xil link ikkinchi marta so'ralsa, qayta yuklab olmasdan, avval saqlangan `file_id`ni (Telegram o'zi fayllarni saqlaydi) bazadan olib qayta yuborish — bu eng katta resurs tejash usuli.
7. **Rate limiting** — foydalanuvchi boshiga daqiqasiga nechta so'rov qabul qilinishini cheklash, aks holda bitta foydalanuvchi butun serverni band qilib qo'yishi mumkin.

### 5.4 Instagram pairing tizimi — texnik tafsilotlar

- Pairing kodi Redis'da 5-10 daqiqalik TTL (muddat) bilan saqlanadi
- Instagram DM'larni tekshirish uchun `instagrapi`ning `direct_pending_inbox` yoki shunga o'xshash metodlaridan polling (masalan har 15-30 soniyada) orqali foydalaniladi — bu Instagram'ning norasmiy API'si bo'lgani uchun risk mavjud (pastga qarang)
- Har bir Telegram user_id ↔ Instagram user_id juftligi bazada saqlanadi
- Reels aniqlanganda, uning media_id'i orqali `instagrapi.video_download` chaqirilib, fayl Telegram'ga yuboriladi

---

## 6. Risklar va cheklovlar (Muhim!)

| Risk | Tavsif | Yechim/Kamaytirish |
|---|---|---|
| Instagram akkaunt bloklanishi | Instagram norasmiy API (instagrapi) ishlatilgani uchun, tez-tez so'rov yuborilsa akkaunt vaqtincha yoki butunlay bloklanishi mumkin | So'rovlar orasida tabiiy kechikish qo'shish, "aged" (eski, isitilgan) akkaunt ishlatish, proxy rotatsiyasi, bir nechta zaxira akkaunt tayyorlash |
| Instagram ToS | Bu platformalarning foydalanish shartlari uchinchi tomon yuklab olish vositalarini rasman taqiqlaydi | Foydalanuvchilarga shaxsiy foydalanish uchun ekanligini eslatish, mualliflik huquqi buzilishiga olib kelmaslik |
| Telegram Bot API fayl hajmi limiti | Oddiy Bot API orqali 50MB dan katta fayl yuborib bo'lmaydi | Local Bot API server o'rnatish (2GB gacha) yoki video sifatini avtomatik pasaytirish |
| Instagram API o'zgarishi | Instagram tez-tez ichki API'sini o'zgartiradi, bu kutubxonalarni buzishi mumkin | `instagrapi`ni doimiy yangilab turish, monitoring va xato haqida ogohlantirish tizimi |
| Yuridik javobgarlik | Boshqa odamlarning kontentini ruxsatsiz yuklab olish/tarqatish mualliflik huquqi masalalariga tegishli bo'lishi mumkin | Botni faqat shaxsiy foydalanish uchun ekanligini foydalanish shartlarida aniq yozish |

---

## 7. Muvaffaqiyat mezonlari (Success Metrics)

- Bitta yuklab olish so'rovini o'rtacha 5-15 soniyada bajarish (video hajmiga qarab)
- Server RAM sarfi 1GB dan oshmasligi (oddiy yuklanishda)
- Instagram akkaunt bloklanish darajasi oyiga 1 martadan kam
- Foydalanuvchi saqlanish (retention) darajasi — birinchi haftada qaytib foydalanish
