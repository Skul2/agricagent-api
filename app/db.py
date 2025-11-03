import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./data.db")

engine = create_async_engine(DATABASE_URL, echo=False, future=True)
AsyncSessionLocal = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = sa.Column(sa.Integer, primary_key=True, index=True)
    phone = sa.Column(sa.String, unique=True, index=True)
    language = sa.Column(sa.String, default="en")
    region = sa.Column(sa.String, nullable=True)

class Message(Base):
    __tablename__ = "messages"
    id = sa.Column(sa.Integer, primary_key=True, index=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey("users.id"))
    role = sa.Column(sa.String)
    text = sa.Column(sa.Text)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_or_create_user(phone: str):
    async with AsyncSessionLocal() as session:
        q = await session.execute(sa.select(User).where(User.phone==phone))
        user = q.scalars().first()
        if user:
            return user
        user = User(phone=phone)
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user

async def save_message(user_id: int, role: str, text: str):
    async with AsyncSessionLocal() as session:
        msg = Message(user_id=user_id, role=role, text=text)
        session.add(msg)
        await session.commit()
        return msg

async def get_all_messages(limit: int = 200):
    async with AsyncSessionLocal() as session:
        q = await session.execute(sa.select(Message).order_by(Message.id.desc()).limit(limit))
        return [ {"id":m.id,"user_id":m.user_id,"role":m.role,"text":m.text} for m in q.scalars().all() ]
