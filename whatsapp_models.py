import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text
from database import Base

class WhatsAppUser(Base):
    __tablename__ = "whatsapp_users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    api_key = Column(String, unique=True, index=True)
    plan_name = Column(String, default="Smart Business (10 JD)")
    monthly_limit = Column(Integer, default=1000)
    messages_sent = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)

class WhatsAppMessageLog(Base):
    __tablename__ = "whatsapp_message_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=True)
    recipient = Column(String, index=True)
    message = Column(Text)
    status = Column(String, default="sent") # sent, failed, queued
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
