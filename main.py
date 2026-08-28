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

# ── Seed known channels on startup so reads never 404 after a fresh deploy ──
_SEED_CHANNELS = [
    {"id": 2, "name": "Smart Water Channel",  "write_api_key": "IPwXiTFSujeNNWd2HAMRfg", "read_api_key": "v_9jxuU6dHmXxNUsCdcERA"},
    {"id": 3, "name": "Motor Control Channel", "write_api_key": "MOTOR_WRITE_KEY",        "read_api_key": "MOTOR_READ_KEY"},
    {"id": 4, "name": "Tita Main Tanks",       "write_api_key": "TITA_WRITE_KEY",         "read_api_key": "TITA_READ_KEY"},
    {"id": 5, "name": "Tita Motor 1",          "write_api_key": "TITA_M1_WRITE",          "read_api_key": "TITA_M1_READ"},
    {"id": 6, "name": "Tita Motor 2",          "write_api_key": "TITA_M2_WRITE",          "read_api_key": "TITA_M2_READ"},
]

@app.on_event("startup")
def seed_channels():
    from database import SessionLocal
    db = SessionLocal()
    try:
        for ch in _SEED_CHANNELS:
            exists = db.query(models.Channel).filter(models.Channel.id == ch["id"]).first()
            if not exists:
                db.add(models.Channel(**ch))
        db.commit()
        print(f"✅ Seeded {len(_SEED_CHANNELS)} channels (skipped existing)")
    except Exception as e:
        db.rollback()
        print(f"⚠️ Channel seeding error: {e}")
    finally:
        db.close()

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

import smtplib
from email.message import EmailMessage

last_alarm_time = {"tank1": 0, "tank3": 0}

# ===== GMAIL CONFIGURATION =====
# You MUST put your Gmail and App Password here before uploading to GitHub!
GMAIL_SENDER = "the.smart.water.app@gmail.com"
GMAIL_APP_PASSWORD = "lhdmvbptobgzjapa"

def send_email_alarm(target_email, tank_name, percentage):
    if not target_email or target_email == "none": return
    if GMAIL_SENDER == "the.smart.water.app@gmail.com":
        print("Gmail not configured! Cannot send email.")
        return
        
    msg = EmailMessage()
    msg.set_content(f"âš ï¸  URGENT ALARM: {tank_name} water level is critically low! (Currently at {percentage}%)\n\nPlease turn on the pump.")
    msg['Subject'] = f"ðŸš¨ Water Alarm: {tank_name} is Low!"
    msg['From'] = GMAIL_SENDER
    msg['To'] = target_email

    try:
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(GMAIL_SENDER, GMAIL_APP_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f"Email successfully sent to {target_email}!")
    except Exception as e:
        print("Failed to send email:", e)

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
    try:
        channel = db.query(models.Channel).filter(models.Channel.write_api_key == api_key).first()
        if not channel:
            if api_key == "IPwXiTFSujeNNWd2HAMRfg":
                channel = models.Channel(id=2, name="Smart Water Channel", write_api_key="IPwXiTFSujeNNWd2HAMRfg", read_api_key="v_9jxuU6dHmXxNUsCdcERA")
                db.add(channel)
                try:
                    db.commit()
                    db.refresh(channel)
                except:
                    db.rollback()
                    channel = db.query(models.Channel).filter(models.Channel.write_api_key == api_key).first()
            elif api_key == "MOTOR_WRITE_KEY":
                channel = models.Channel(id=3, name="Motor Control Channel", write_api_key="MOTOR_WRITE_KEY", read_api_key="MOTOR_READ_KEY")
                db.add(channel)
                try: db.commit(); db.refresh(channel)
                except: db.rollback(); channel = db.query(models.Channel).filter(models.Channel.write_api_key == api_key).first()
            elif api_key == "TITA_WRITE_KEY":
                channel = models.Channel(id=4, name="Tita Main Tanks", write_api_key="TITA_WRITE_KEY", read_api_key="TITA_READ_KEY")
                db.add(channel)
                try: db.commit(); db.refresh(channel)
                except: db.rollback(); channel = db.query(models.Channel).filter(models.Channel.write_api_key == api_key).first()
            elif api_key == "TITA_M1_WRITE":
                channel = models.Channel(id=5, name="Tita Motor 1", write_api_key="TITA_M1_WRITE", read_api_key="TITA_M1_READ")
                db.add(channel)
                try: db.commit(); db.refresh(channel)
                except: db.rollback(); channel = db.query(models.Channel).filter(models.Channel.write_api_key == api_key).first()
            elif api_key == "TITA_M2_WRITE":
                channel = models.Channel(id=6, name="Tita Motor 2", write_api_key="TITA_M2_WRITE", read_api_key="TITA_M2_READ")
                db.add(channel)
                try: db.commit(); db.refresh(channel)
                except: db.rollback(); channel = db.query(models.Channel).filter(models.Channel.write_api_key == api_key).first()
            else:
                raise HTTPException(status_code=400, detail="Invalid API Key")

        # Inherit fields
        prev_feed = db.query(models.Feed).filter(models.Feed.channel_id == channel.id).order_by(models.Feed.created_at.desc()).first()
        if prev_feed:
            if field1 is None: field1 = prev_feed.field1
            if field2 is None: field2 = prev_feed.field2
            if field3 is None: field3 = prev_feed.field3
            if field4 is None: field4 = prev_feed.field4
            if field5 is None: field5 = prev_feed.field5
            if field6 is None: field6 = prev_feed.field6
            if field7 is None: field7 = prev_feed.field7
            if field8 is None: field8 = prev_feed.field8

        db_feed = models.Feed(
            channel_id=channel.id, field1=field1, field2=field2, field3=field3,
            field4=field4, field5=field5, field6=field6, field7=field7, field8=field8
        )
        db.add(db_feed)
        db.commit()

        # Alarm logic
        if field1 is not None or field3 is not None:
            def get_last_val_str(field_name):
                f = db.query(getattr(models.Feed, field_name)).filter(models.Feed.channel_id == channel.id, getattr(models.Feed, field_name) != None).order_by(models.Feed.created_at.desc()).first()
                return f[0] if f else None
                
            alarm_data = get_last_val_str("field8")
            target_email = "none"
            threshold = 20.0
            
            if alarm_data:
                parts = alarm_data.split("|")
                if len(parts) == 2:
                    target_email = parts[0]
                    try: threshold = float(parts[1])
                    except: pass
                else:
                    try: threshold = float(alarm_data)
                    except: pass

            if target_email != "none":
                import datetime
                if field1 is not None:
                    try:
                        pct1 = float(field1)
                        if pct1 < threshold:
                            now = datetime.datetime.utcnow()
                            last = last_alarm_time.get("tank1")
                            if not last or (now - last).total_seconds() > 3600:
                                send_email_alarm(target_email, "Tank 1", pct1)
                                last_alarm_time["tank1"] = now
                    except: pass
                if field3 is not None:
                    try:
                        pct3 = float(field3)
                        if pct3 < threshold:
                            now = datetime.datetime.utcnow()
                            last = last_alarm_time.get("tank3")
                            if not last or (now - last).total_seconds() > 3600:
                                send_email_alarm(target_email, "Tank 3", pct3)
                                last_alarm_time["tank3"] = now
                    except: pass

        entry_count = db.query(models.Feed).filter(models.Feed.channel_id == channel.id).count()
        return entry_count
        
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return str(traceback.format_exc())


@app.get("/channels/{channel_id}/feeds.json", tags=["Data Retrieval"])
def read_feeds(
    channel_id: int, 
    api_key: str, 
    results: int = 100,
    db: Session = Depends(get_db)
):
    channel = db.query(models.Channel).filter(models.Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
        
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
            "field3": channel.field3_name,
            "field4": channel.field4_name,
            "field5": channel.field5_name,
            "field6": channel.field6_name,
            "field7": channel.field7_name,
            "field8": channel.field8_name,
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
            } for feed in reversed(feeds)
        ]
    }
    return response

@app.get("/channels/{channel_id}/fields/{field_id}/last.json", tags=["Data Retrieval"])
def read_last_field(
    channel_id: int,
    field_id: int,
    api_key: str,
    db: Session = Depends(get_db)
):
    if field_id < 1 or field_id > 8:
        raise HTTPException(status_code=400, detail="Invalid field ID (must be 1-8)")

    channel = db.query(models.Channel).filter(models.Channel.id == channel_id).first()
    if not channel:
        return "-1"
        
    if channel.read_api_key != api_key:
        raise HTTPException(status_code=403, detail="-1")

    feed = db.query(models.Feed).filter(models.Feed.channel_id == channel_id)\
             .order_by(models.Feed.created_at.desc()).first()
             
    if not feed:
        return "-1"
        
    # Get the specific field
    field_value = getattr(feed, f"field{field_id}")
    if field_value is None:
        return "-1"
        
    return str(field_value)
