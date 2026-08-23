from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List
import models
from database import engine, get_db
from pydantic import BaseModel
from datetime import datetime

# Create database tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Smart Water Backend (ThingSpeak Clone)")

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

@app.get("/update", tags=["IoT Devices"])
@app.post("/update", tags=["IoT Devices"])
def update_feed(
    api_key: str = Query(..., description="Write API Key for the channel"),
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
    """
    Update a channel feed. This mimics the typical GET /update endpoint used by ESP32/Arduino devices.
    """
    channel = db.query(models.Channel).filter(models.Channel.write_api_key == api_key).first()
    if not channel:
        raise HTTPException(status_code=400, detail="Invalid API Key")

    db_feed = models.Feed(
        channel_id=channel.id,
        field1=field1,
        field2=field2,
        field3=field3,
        field4=field4,
        field5=field5,
        field6=field6,
        field7=field7,
        field8=field8
    )
    db.add(db_feed)
    db.commit()
    db.refresh(db_feed)
    
    # ThingSpeak returns the number of entries in the channel
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
