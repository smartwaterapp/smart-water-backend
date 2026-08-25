# Custom ThingSpeak Backend

This is a lightweight custom backend designed to fully mimic the ThingSpeak API endpoints used by the Smart Water Flutter app. 

It completely bypasses ThingSpeak's rate limits and message caps because it runs entirely on your own machine (or a VPS) and stores data in a local SQLite database (`thingspeak.db`).

## How to Run It

Since you already have Flutter/Dart installed for your app, you can run this server instantly without installing anything else!

1. Open your terminal in this folder (`smart_water_backend`).
2. Run the server using Dart:
   ```bash
   dart run server.dart
   ```

The server will start running locally at `http://127.0.0.1:5000`.

## Endpoints Supported
- `GET /update?api_key=...&field1=...` (Saves data to `feeds.json`)
- `GET /channels/<id>/feeds/last.json` (Gets the most recent feed for the gauges)
- `GET /channels/<id>/feeds.json` (Gets all recent feeds for the charts)

## How to connect the Flutter App
In your `smart_water_flutter` app, you will need to replace `https://api.thingspeak.com` with `http://127.0.0.1:5000` (or whatever URL this server ends up being hosted on).
