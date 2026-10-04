"""Seed explicitly development-only accounts; refuses outside APP_ENV=development."""

import asyncio

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal, engine
from app.core.security import hash_password
from app.models.user import User


async def main():
    if get_settings().app_env != "development":
        raise SystemExit("Refusing to seed non-development environment")
    users = [
        ("admin@example.com", "AdminDevOnly!123", "ADMIN"),
        ("user@example.com", "UserDevOnly!123", "USER"),
    ]
    async with SessionLocal() as session:
        for username, password, role in users:
            existing = await session.scalar(select(User).where(User.username == username))
            if not existing:
                session.add(
                    User(
                        username=username,
                        password_hash=hash_password(password),
                        role=role,
                        is_active=True,
                    )
                )
        await session.commit()
    await engine.dispose()
    print("Development accounts ensured; see README for credentials (development only).")


if __name__ == "__main__":
    asyncio.run(main())
