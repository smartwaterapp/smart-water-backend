from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List
import models
from database import engine, get_db
from pydantic import BaseModel
from datetime import datetime

import time
import urllib.request
import json

# Create database tables
models.Base.metadata.create_all(bind=engine)

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Smart Water Backend (ThingSpeak Clone)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Schemas for API responses ---
class ChannelCreate(BaseModel):
    name: str
    description: Optional[str] = None

class FeedResponse(BaseModel):
    created_at: datetime
    entry_id: int
    field1: Optional[str] = None
    field2: Optional[str] = None
    field3: Optional[str] = None
    field4: Optional[str] = None
    field5: Optional[str] = None
    field6: Optional[str] = None
    field7: Optional[str] = None
    field8: Optional[str] = None

    class Config:
        from_attributes = True

# --- Management Endpoints ---
@app.post("/channels", tags=["Management"])
def create_channel(channel: ChannelCreate, db: Session = Depends(get_db)):
    db_channel = models.Channel(name=channel.name, description=channel.description)
    db.add(db_channel)
    db.commit()
    db.refresh(db_channel)
    return {
        "channel_id": db_channel.id,
        "name": db_channel.name,
        "write_api_key": db_channel.write_api_key,
        "read_api_key": db_channel.read_api_key
    }

# --- ThingSpeak Compatible Endpoints ---

last_alarm_time = {"tank1": 0, "tank3": 0}
TELEGRAM_TOKEN = "8994007169:AAFl1cfVzYXZyE1x7K6RhvqAFEtWakXmLuM"
TELEGRAM_CHAT_ID = "693872472"

def send_telegram_alarm(tank_name, percentage):
    msg = f"⚠️ ALARM: {tank_name} water level is extremely low! ({percentage}%)"
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = json.dumps({"chat_id": TELEGRAM_CHAT_ID, "text": msg}).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    try:
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        print("Telegram error:", e)

@app.get("/update", tags=["Data Update"])
def update_channel(
    api_key: str,
    field1: Optional[str] = None,
    field2: Optional[str] = None,
    field3: Optional[str] = None,
    field4: Optional[str] = None,
    field5: Optional[str] = None,
    field6: Optional[str] = None,
    field7: Optional[str] = None,
    field8: Optional[str] = None,
    db: Session = Depends(get_db)
):
    channel = db.query(models.Channel).filter(models.Channel.write_api_key == api_key).first()
    if not channel:
        raise HTTPException(status_code=400, detail="Invalid API Key")

    db_feed = models.Feed(
        channel_id=channel.id, field1=field1, field2=field2, field3=field3,
        field4=field4, field5=field5, field6=field6, field7=field7, field8=field8
    )
    db.add(db_feed)
    db.commit()
    db.refresh(db_feed)

    # TELEGRAM ALARM LOGIC
    if field1 is not None or field3 is not None:
        def get_last_val(field_name):
            f = db.query(getattr(models.Feed, field_name)).filter(models.Feed.channel_id == channel.id, getattr(models.Feed, field_name) != None).order_by(models.Feed.created_at.desc()).first()
            return float(f[0]) if f else None
            
        threshold = get_last_val("field8")
        if threshold is None: threshold = 20.0 # Default alarm threshold

        if field1 is not None:
            t1_tank = get_last_val("field4")
            t1_water = get_last_val("field5")
            if t1_tank and t1_water:
                water_cm = t1_tank - float(field1)
                if water_cm >= 0:
                    pct1 = max(0, min(100, int((water_cm / t1_water) * 100)))
                    if pct1 <= threshold:
                        now = time.time()
                        if now - last_alarm_time["tank1"] > 3600: # 1 hour cooldown
                            send_telegram_alarm("Tank 1", pct1)
                            last_alarm_time["tank1"] = now

        if field3 is not None:
            t3_tank = get_last_val("field6")
            t3_water = get_last_val("field7")
            if t3_tank and t3_water:
                water_cm = t3_tank - float(field3)
                if water_cm >= 0:
                    pct3 = max(0, min(100, int((water_cm / t3_water) * 100)))
                    if pct3 <= threshold:
                        now = time.time()
                        if now - last_alarm_time["tank3"] > 3600: # 1 hour cooldown
                            send_telegram_alarm("Tank 3", pct3)
                            last_alarm_time["tank3"] = now

    entry_count = db.query(models.Feed).filter(models.Feed.channel_id == channel.id).count()
    return entry_count


@app.get("/channels/{channel_id}/feeds.json", tags=["Data Retrieval"])
def read_feeds(
    channel_id: int,
    api_key: Optional[str] = Query(None, description="Read API Key (if channel is private)"),
    results: int = Query(100, description="Number of entries to retrieve"),
    db: Session = Depends(get_db)
):
    """
    Retrieve feeds for a channel. Mimics the ThingSpeak GET feeds JSON endpoint.
    """
    channel = db.query(models.Channel).filter(models.Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
        
    # In a real app you might check if the channel is public, but for now we enforce the read key
    if channel.read_api_key != api_key:
        raise HTTPException(status_code=403, detail="Invalid Read API Key")

    feeds = db.query(models.Feed).filter(models.Feed.channel_id == channel_id)\
              .order_by(models.Feed.created_at.desc())\
              .limit(results).all()
              
    # Format response to look similar to ThingSpeak
    response = {
        "channel": {
            "id": channel.id,
            "name": channel.name,
            "description": channel.description,
            "field1": channel.field1_name,
            "field2": channel.field2_name,
        },
        "feeds": [
            {
                "created_at": feed.created_at.isoformat() + "Z",
                "entry_id": feed.id,
                "field1": feed.field1,
                "field2": feed.field2,
                "field3": feed.field3,
                "field4": feed.field4,
                "field5": feed.field5,
                "field6": feed.field6,
                "field7": feed.field7,
                "field8": feed.field8,
            }
            for feed in reversed(feeds) # Chronological order
        ]
    }
    return response

@app.get("/channels/{channel_id}/fields/{field_id}/last", tags=["Data Retrieval"])
def read_last_field(
    channel_id: int,
    field_id: int,
    api_key: Optional[str] = Query(None, description="Read API Key"),
    db: Session = Depends(get_db)
):
    """
    Retrieve the last value of a specific field. Mimics ThingSpeak's last field endpoint.
    Returns plain text.
    """
    channel = db.query(models.Channel).filter(models.Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="-1")
        
    if channel.read_api_key != api_key:
        raise HTTPException(status_code=403, detail="-1")

    feed = db.query(models.Feed).filter(models.Feed.channel_id == channel_id)\
             .order_by(models.Feed.created_at.desc()).first()
             
    if not feed:
        return "-1"
        
    # Get the specific field
    field_value = getattr(feed, f"field{field_id}", None)
    if field_value is None:
        return "-1"
        
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(str(field_value))

@app.get("/", tags=["Health"])
def root():
    return {"message": "Smart Water Backend is running. Access /docs for API documentation."}
