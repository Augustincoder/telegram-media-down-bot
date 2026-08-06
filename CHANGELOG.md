# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Changelog Enforcement Rule**: Implemented a `.cursorrules` file at the project root. This instructs all future AI assistant interactions to strictly document changes in `CHANGELOG.md` prior to executing any `git commit` commands, ensuring a professional and exhaustive audit trail.
- **Expandable Blockquote Captions**: When stories are downloaded and backed up to the private Telegram storage channel, they now include a rich metadata caption. The primary text shows the profile name and platform, while an expandable blockquote (Telegram Spoiler format) hides detailed information including username, platform, posted timestamp, and download timestamp.
- **`/recover_hashes` Command**: Added a dedicated command for admins to iterate through existing saved profiles in the database and automatically fetch their `access_hash` via Telethon, resolving the issue where old profiles without usernames could not be fetched.
- **Randomized Unlink Confirmation**: The `/unlink_all` command now generates a random 6-character alphanumeric code that the user must copy-paste to confirm the deletion of all linked Instagram profiles. This prevents accidental execution.
- **SQLiteSession for Telethon**: Replaced the ephemeral `StringSession` with `SQLiteSession` for Telegram Userbot authentication. This ensures that session state and entities are properly persisted across container restarts, drastically reducing the rate of "Could not find the input entity" errors.
- **Database Maintenance**: Added `cron_cleaner.py` to automatically prune 30-day-old `StoryCache` and `Download` entries to prevent database bloat over time.
- **Linting & Code Quality**: Added `ruff` and applied PEP8 compliance across the codebase.

### Changed
- **Dynamic Polling Backoff**: Updated `instagram_polling.py` to use a dynamic sleep interval. It starts at 45 seconds and increments by 10 seconds (up to a maximum of 180 seconds) when no new messages are detected. This significantly lowers the risk of Instagram rate-limiting (429/403) while maintaining responsiveness.
- **Routing Architecture Refactor**: Removed massive "spaghetti code" `if/else` text matchers from `messages.py`. Transitioned `📥 Yuklab olish`, `⚙️ Sozlamalar`, `💾 Saqlangan profillar`, and `🔗 Akkaunt ulash` handlers to modular Aiogram `@router.message(F.text == "...")` decorators across their respective files (`saved.py`, `pairing.py`, `commands.py`, etc.).
- **Enhanced Story Caching**: Improved Telegram story downloading mechanism to ensure temporary files are properly deleted from Northflank local storage utilizing strict `finally` blocks, resolving potential local disk exhaustion.

### Fixed
- **Memory Leak in Polling**: Fixed an unbounded dictionary `processed_message_ids` in `instagram_polling.py` by implementing an `OrderedDict` with a strict `MAX_PROCESSED = 5000` limit, preventing RAM exhaustion during long uptimes.
- **Database Schema Mismatch**: Fixed a bug in `cron_cleaner.py` where it referenced a non-existent `added_at` field in `StoryCache`; corrected it to `downloaded_at`.
- **Aiogram Router Imports**: Resolved a `NameError` crash where `F` filter was omitted in the router imports after the architectural split.

---

> **Developer Note (Agent Instruction):**
> As per the project requirements, **every future code change** that modifies behavior, fixes bugs, or introduces new features MUST be logged in this `CHANGELOG.md` file BEFORE committing and pushing to GitHub. Updating this file is a strict requirement for all subsequent tasks.
