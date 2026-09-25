from fastapi import FastAPI, Depends, HTTPException, Query, Form as FastForm
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
from fastapi.responses import HTMLResponse, RedirectResponse

app = FastAPI(title="Smart Water Backend (ThingSpeak Clone)")

@app.get('/', response_class=HTMLResponse, tags=['Dashboard'])
def web_dashboard(db: Session = Depends(get_db)):
    channels = db.query(models.Channel).all()
    html = """<html><head><title>Smart Water Dashboard</title>
<style>
body{font-family:sans-serif;padding:20px;background:#f4f4f9;}
.card{background:white;padding:20px;margin-bottom:15px;border-radius:8px;box-shadow:0 2px 5px rgba(0,0,0,0.1);position:relative;}
input,button{padding:8px 12px;margin:4px;border-radius:4px;border:1px solid #ccc;}
button{background:#4CAF50;color:white;border:none;cursor:pointer;}
.btn-delete{background:#e53935;color:white;border:none;cursor:pointer;padding:8px 14px;border-radius:4px;font-weight:bold;}
.btn-delete:hover{background:#b71c1c;}
.btn-clear{background:#fb8c00;color:white;border:none;cursor:pointer;padding:8px 14px;border-radius:4px;font-weight:bold;}
.btn-clear:hover{background:#e65100;}
.actions-row{display:flex;gap:10px;align-items:center;margin-top:10px;}
.form-card{background:#e8f5e9;padding:20px;margin-bottom:20px;border-radius:8px;}
label{font-weight:bold;margin-right:8px;}
</style></head><body>
<h1>💧 Smart Water Web Dashboard</h1>
<div class="form-card"><h2>➕ Create New Channel</h2>
<form method="POST" action="/channels/create">
<label>Name:</label><input type="text" name="name" required placeholder="My Channel"><br>
<label>ID (optional):</label><input type="number" name="id" placeholder="Auto"><br>
<label>Write Key (optional):</label><input type="text" name="write_api_key" placeholder="Auto"><br>
<label>Read Key (optional):</label><input type="text" name="read_api_key" placeholder="Auto"><br>
<button type="submit">Create Channel</button>
</form></div>"""
    if not channels:
        html += '<p>No channels found.</p>'
    for c in channels:
        feed_count = db.query(models.Feed).filter(models.Feed.channel_id == c.id).count()
        html += f'<div class="card"><h2>{c.name} (ID: {c.id})</h2>'
        html += f'<p><b>Read Key:</b> <code>{c.read_api_key}</code></p>'
        html += f'<p><b>Write Key:</b> <code>{c.write_api_key}</code></p>'
        html += f'<p><b>Total Feeds:</b> {feed_count}</p>'
        html += f'<a href="/channels/{c.id}/feeds.json?api_key={c.read_api_key}&results=5" target="_blank">View Data (JSON)</a>'
        html += '<div class="actions-row">'
        html += f'<form method="POST" action="/channels/{c.id}/clear" onsubmit="return confirm(\'Are you sure you want to clear all feed data for {c.name} (ID: {c.id})?\');" style="display:inline;">'
        html += '<button type="submit" class="btn-clear">🧹 Clear Data</button></form>'
        html += f'<form method="POST" action="/channels/{c.id}/delete" onsubmit="return confirm(\'Are you sure you want to completely DELETE channel {c.name} (ID: {c.id}) and all its data?\');" style="display:inline;">'
        html += '<button type="submit" class="btn-delete">🗑️ Delete Channel</button></form>'
        html += '</div></div>'
    html += '</body></html>'
    return html

@app.post('/channels/create', tags=['Management'])
def create_channel_form(
    name: str = FastForm(...),
    id: Optional[int] = FastForm(None),
    write_api_key: Optional[str] = FastForm(None),
    read_api_key: Optional[str] = FastForm(None),
    db: Session = Depends(get_db)
):
    kwargs = {"name": name}
    if id is not None and id > 0:
        existing = db.query(models.Channel).filter(models.Channel.id == id).first()
        if existing:
            return HTMLResponse(f"<h2>Error: Channel {id} already exists!</h2><a href='/'>Go Back</a>", status_code=409)
        kwargs["id"] = id
    if write_api_key and write_api_key.strip():
        kwargs["write_api_key"] = write_api_key.strip()
    if read_api_key and read_api_key.strip():
        kwargs["read_api_key"] = read_api_key.strip()
    db_channel = models.Channel(**kwargs)
    db.add(db_channel)
    db.commit()
    return RedirectResponse(url="/", status_code=303)

@app.post('/channels/{channel_id}/delete', tags=['Management'])
def delete_channel_form(channel_id: int, db: Session = Depends(get_db)):
    db.query(models.Feed).filter(models.Feed.channel_id == channel_id).delete()
    channel = db.query(models.Channel).filter(models.Channel.id == channel_id).first()
    if channel:
        db.delete(channel)
        db.commit()
    return RedirectResponse(url="/", status_code=303)

@app.post('/channels/{channel_id}/clear', tags=['Management'])
def clear_channel_feeds(channel_id: int, db: Session = Depends(get_db)):
    db.query(models.Feed).filter(models.Feed.channel_id == channel_id).delete()
    db.commit()
    return RedirectResponse(url="/", status_code=303)

@app.delete('/channels/{channel_id}', tags=['Management'])
def delete_channel_api(channel_id: int, db: Session = Depends(get_db)):
    channel = db.query(models.Channel).filter(models.Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    db.query(models.Feed).filter(models.Feed.channel_id == channel_id).delete()
    db.delete(channel)
    db.commit()
    return {"message": f"Channel {channel_id} deleted successfully"}

# -- Seed known channels on startup so reads never 404 after a fresh deploy --
_SEED_CHANNELS = [
    {"id": 1, "name": "yousvin8 tank",         "write_api_key": "yousvin8",                "read_api_key": "elias gg"},
    {"id": 2, "name": "Smart Water Channel",  "write_api_key": "IPwXiTFSujeNNWd2HAMRfg", "read_api_key": "v_9jxuU6dHmXxNUsCdcERA"},
    {"id": 3, "name": "Tank 3 Motor Channel", "write_api_key": "MOTOR_WRITE_KEY",        "read_api_key": "MOTOR_READ_KEY"},
    {"id": 4, "name": "Tita Main Tanks",       "write_api_key": "TITA_WRITE_KEY",         "read_api_key": "TITA_READ_KEY"},
    {"id": 5, "name": "Tita Motor 1",          "write_api_key": "TITA_M1_WRITE",          "read_api_key": "TITA_M1_READ"},
    {"id": 6, "name": "Tita Motor 2",          "write_api_key": "TITA_M2_WRITE",          "read_api_key": "TITA_M2_READ"},
    {"id": 7, "name": "Tank 1 Motor Channel",   "write_api_key": "TANK1_M_WRITE",          "read_api_key": "TANK1_M_READ"},
    {"id": 8, "name": "Mafia Game Sync",       "write_api_key": "MAFIA_WRITE_KEY",        "read_api_key": "MAFIA_READ_KEY"},
]

def cleanup_old_feeds(db: Session, max_age_days: int = 2):
    """
    Deletes feeds in all channels where created_at is older than `max_age_days` (default 2 days).
    Always retains the single latest feed for every channel so tanks always retain their current state.
    """
    try:
        from datetime import datetime, timedelta
        cutoff = datetime.utcnow() - timedelta(days=max_age_days)
        # Find all distinct channels with feeds older than cutoff
        channels = db.query(models.Channel).all()
        for ch in channels:
            latest = db.query(models.Feed).filter(models.Feed.channel_id == ch.id)\
                       .order_by(models.Feed.created_at.desc()).first()
            query = db.query(models.Feed).filter(
                models.Feed.channel_id == ch.id,
                models.Feed.created_at < cutoff
            )
            # Make sure we never delete the latest reading even if inactive
            if latest:
                query = query.filter(models.Feed.id != latest.id)
            deleted_count = query.delete(synchronize_session=False)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Cleanup error: {e}")

@app.on_event("startup")
def startup_init():
    from database import SessionLocal
    db = SessionLocal()
    try:
        for ch in _SEED_CHANNELS:
            exists = db.query(models.Channel).filter(models.Channel.id == ch["id"]).first()
            if not exists:
                db.add(models.Channel(**ch))
            else:
                exists.name = ch["name"]
                exists.write_api_key = ch["write_api_key"]
                exists.read_api_key = ch["read_api_key"]
        db.commit()
        print(f"Seeded/Updated {len(_SEED_CHANNELS)} channels")
        # Run cleanup on startup
        cleanup_old_feeds(db, max_age_days=2)
    except Exception as e:
        db.rollback()
        print(f"Startup initialization error: {e}")
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
    id: Optional[int] = None
    write_api_key: Optional[str] = None
    read_api_key: Optional[str] = None

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
    kwargs = {"name": channel.name, "description": channel.description}
    if channel.id is not None:
        existing = db.query(models.Channel).filter(models.Channel.id == channel.id).first()
        if existing:
            raise HTTPException(status_code=409, detail=f"Channel {channel.id} already exists")
        kwargs["id"] = channel.id
    if channel.write_api_key:
        kwargs["write_api_key"] = channel.write_api_key
    if channel.read_api_key:
        kwargs["read_api_key"] = channel.read_api_key
    db_channel = models.Channel(**kwargs)
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
GMAIL_SENDER = "the.smart.water.app@gmail.com"
GMAIL_APP_PASSWORD = "lhdmvbptobgzjapa"

def send_email_alarm(target_email, tank_name, percentage):
    if not target_email or target_email == "none": return
    if GMAIL_SENDER == "the.smart.water.app@gmail.com":
        print("Gmail not configured! Cannot send email.")
        return
        
    msg = EmailMessage()
    msg.set_content(f"URGENT ALARM: {tank_name} water level is critically low! (Currently at {percentage}%)\n\nPlease turn on the pump.")
    msg['Subject'] = f"Water Alarm: {tank_name} is Low!"
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
            if api_key == "yousvin8":
                ch1 = db.query(models.Channel).filter(models.Channel.id == 1).first()
                if ch1:
                    ch1.write_api_key = "yousvin8"
                    ch1.read_api_key = "elias gg"
                    ch1.name = "yousvin8 tank"
                    db.commit()
                    db.refresh(ch1)
                    channel = ch1
                else:
                    channel = models.Channel(id=1, name="yousvin8 tank", write_api_key="yousvin8", read_api_key="elias gg")
                    db.add(channel)
                    try: db.commit(); db.refresh(channel)
                    except: db.rollback(); channel = db.query(models.Channel).filter(models.Channel.write_api_key == api_key).first()
            elif api_key == "IPwXiTFSujeNNWd2HAMRfg":
                channel = models.Channel(id=2, name="Smart Water Channel", write_api_key="IPwXiTFSujeNNWd2HAMRfg", read_api_key="v_9jxuU6dHmXxNUsCdcERA")
                db.add(channel)
                try:
                    db.commit()
                    db.refresh(channel)
                except:
                    db.rollback()
                    channel = db.query(models.Channel).filter(models.Channel.write_api_key == api_key).first()
            elif api_key == "MOTOR_WRITE_KEY":
                channel = models.Channel(id=3, name="Tank 3 Motor Channel", write_api_key="MOTOR_WRITE_KEY", read_api_key="MOTOR_READ_KEY")
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
            elif api_key == "TANK1_M_WRITE":
                channel = models.Channel(id=7, name="Tank 1 Motor Channel", write_api_key="TANK1_M_WRITE", read_api_key="TANK1_M_READ")
                db.add(channel)
                try: db.commit(); db.refresh(channel)
                except: db.rollback(); channel = db.query(models.Channel).filter(models.Channel.write_api_key == api_key).first()
            elif api_key == "MAFIA_WRITE_KEY":
                channel = models.Channel(id=8, name="Mafia Game Sync", write_api_key="MAFIA_WRITE_KEY", read_api_key="MAFIA_READ_KEY")
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
                import datetime as dt_module
                if field1 is not None:
                    try:
                        pct1 = float(field1)
                        if pct1 < threshold:
                            now = dt_module.datetime.utcnow()
                            last = last_alarm_time.get("tank1")
                            if not last or (now - last).total_seconds() > 3600:
                                send_email_alarm(target_email, "Tank 1", pct1)
                                last_alarm_time["tank1"] = now
                    except: pass
                if field3 is not None:
                    try:
                        pct3 = float(field3)
                        if pct3 < threshold:
                            now = dt_module.datetime.utcnow()
                            last = last_alarm_time.get("tank3")
                            if not last or (now - last).total_seconds() > 3600:
                                send_email_alarm(target_email, "Tank 3", pct3)
                                last_alarm_time["tank3"] = now
                    except: pass

        # Clean up records older than 2 days automatically
        cleanup_old_feeds(db, max_age_days=2)

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
    minutes: Optional[int] = None,
    db: Session = Depends(get_db)
):
    # Lookup by ID, or fallback to matching by read_api_key (supports channel 2 alias for channel 3211060)
    channel = db.query(models.Channel).filter(models.Channel.id == channel_id).first()
    if not channel and channel_id == 2:
        channel = db.query(models.Channel).filter(models.Channel.id == 3211060).first()
    if not channel:
        channel = db.query(models.Channel).filter(models.Channel.read_api_key == api_key).first()
        
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
        
    # Auto-repair channel 1 keys if accessed with 'elias gg'
    if channel.id == 1 and api_key == "elias gg" and channel.read_api_key != "elias gg":
        channel.read_api_key = "elias gg"
        channel.write_api_key = "yousvin8"
        channel.name = "yousvin8 tank"
        db.commit()

    if channel.read_api_key != api_key:
        raise HTTPException(status_code=403, detail="Invalid Read API Key")

    # Clean up data older than 2 days automatically on read
    cleanup_old_feeds(db, max_age_days=2)

    query = db.query(models.Feed).filter(models.Feed.channel_id == channel.id)
    
    if minutes is not None and minutes > 0:
        import datetime as dt_module
        cutoff = dt_module.datetime.utcnow() - dt_module.timedelta(minutes=minutes)
        query = query.filter(models.Feed.created_at >= cutoff)
        feeds = query.order_by(models.Feed.created_at.asc()).all()
    else:
        feeds = query.order_by(models.Feed.created_at.desc()).limit(results).all()
        feeds = list(reversed(feeds))
             
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
            } for feed in feeds
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

    field_value = getattr(feed, f"field{field_id}")
    if field_value is None:
        return "-1"
    return str(field_value)
