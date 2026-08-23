from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from database import Base
import datetime
import secrets

def generate_api_key():
    return secrets.token_urlsafe(16)

class Channel(Base):
    __tablename__ = "channels"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(String, nullable=True)
    write_api_key = Column(String, unique=True, index=True, default=generate_api_key)
    read_api_key = Column(String, unique=True, index=True, default=generate_api_key)
    
    # Metadata for fields
    field1_name = Column(String, default="Field 1")
    field2_name = Column(String, default="Field 2")
    field3_name = Column(String, default="Field 3")
    field4_name = Column(String, default="Field 4")
    field5_name = Column(String, default="Field 5")
    field6_name = Column(String, default="Field 6")
    field7_name = Column(String, default="Field 7")
    field8_name = Column(String, default="Field 8")

    feeds = relationship("Feed", back_populates="channel")

class Feed(Base):
    __tablename__ = "feeds"

    id = Column(Integer, primary_key=True, index=True)
    channel_id = Column(Integer, ForeignKey("channels.id"))
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    field1 = Column(String, nullable=True)
    field2 = Column(String, nullable=True)
    field3 = Column(String, nullable=True)
    field4 = Column(String, nullable=True)
    field5 = Column(String, nullable=True)
    field6 = Column(String, nullable=True)
    field7 = Column(String, nullable=True)
    field8 = Column(String, nullable=True)

    channel = relationship("Channel", back_populates="feeds")
