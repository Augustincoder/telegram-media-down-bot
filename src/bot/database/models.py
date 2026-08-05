import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # Telegram User ID
    username: Mapped[str | None] = mapped_column(String(32), nullable=True)
    full_name: Mapped[str] = mapped_column(String(128))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    downloads: Mapped[list["Download"]] = relationship(
        "Download", back_populates="user"
    )
    pairing: Mapped[Optional["InstagramPairing"]] = relationship(
        "InstagramPairing", back_populates="user", uselist=False
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username})>"


class InstagramPairing(Base):
    __tablename__ = "instagram_pairings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    instagram_user_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    instagram_username: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    paired_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationship back to User
    user: Mapped["User"] = relationship("User", back_populates="pairing")

    def __repr__(self) -> str:
        return f"<InstagramPairing(user_id={self.user_id}, ig_username={self.instagram_username})>"


class Download(Base):
    __tablename__ = "downloads"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    platform: Mapped[str] = mapped_column(String(20))  # e.g., 'instagram', 'telegram'
    media_type: Mapped[str] = mapped_column(String(20))  # e.g., 'reels', 'story'
    url: Mapped[str] = mapped_column(String)
    file_id: Mapped[str | None] = mapped_column(
        String, nullable=True, index=True
    )  # Cached Telegram file_id
    downloaded_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationship back to User
    user: Mapped["User"] = relationship("User", back_populates="downloads")

    def __repr__(self) -> str:
        return f"<Download(id={self.id}, platform={self.platform}, user_id={self.user_id})>"


class SavedProfile(Base):
    __tablename__ = "saved_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    platform: Mapped[str] = mapped_column(String, default="instagram")
    ig_username: Mapped[str] = mapped_column(String, index=True)
    ig_user_id: Mapped[str | None] = mapped_column(String, nullable=True)
    added_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User"] = relationship("User")

    def __repr__(self) -> str:
        return f"<SavedProfile(user_id={self.user_id}, ig_username={self.ig_username})>"


class SystemState(Base):
    __tablename__ = "system_state"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    value: Mapped[str] = mapped_column(String)


class StoryCache(Base):
    __tablename__ = "story_cache"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String, default="instagram")
    ig_username: Mapped[str] = mapped_column(String, index=True)
    story_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    telegram_msg_id: Mapped[int] = mapped_column(BigInteger)
    downloaded_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<StoryCache(ig_username={self.ig_username}, story_id={self.story_id})>"

class UsernameHistory(Base):
    __tablename__ = "username_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("saved_profiles.id"))
    old_username: Mapped[str] = mapped_column(String)
    new_username: Mapped[str] = mapped_column(String)
    changed_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    profile: Mapped["SavedProfile"] = relationship("SavedProfile")

    def __repr__(self) -> str:
        return f"<UsernameHistory(profile_id={self.profile_id}, old={self.old_username}, new={self.new_username})>"
