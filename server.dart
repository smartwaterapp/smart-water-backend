import 'dart:io';
import 'dart:convert';

// Path to data store
const dataFile = 'feeds.json';
int currentEntryId = 0;
List<Map<String, dynamic>> feeds = [];

void loadData() {
  final file = File(dataFile);
  if (file.existsSync()) {
    final contents = file.readAsStringSync();
    if (contents.isNotEmpty) {
      final List<dynamic> jsonList = jsonDecode(contents);
      feeds = jsonList.cast<Map<String, dynamic>>();
      if (feeds.isNotEmpty) {
        currentEntryId = feeds.last['entry_id'] as int;
      }
    }
  }
}

void saveData() {
  final file = File(dataFile);
  file.writeAsStringSync(jsonEncode(feeds));
}

void main() async {
  loadData();
  
  final server = await HttpServer.bind(InternetAddress.anyIPv4, 5000);
  print('----------------------------------------------------');
  print('✅ Custom ThingSpeak Backend running on http://127.0.0.1:5000');
  print('----------------------------------------------------');

  await for (HttpRequest request in server) {
    // Enable CORS so Flutter Web can talk to it
    request.response.headers.add('Access-Control-Allow-Origin', '*');
    request.response.headers.add('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
    request.response.headers.add('Access-Control-Allow-Headers', '*');

    if (request.method == 'OPTIONS') {
      request.response.statusCode = HttpStatus.ok;
      await request.response.close();
      continue;
    }

    try {
      final path = request.uri.path;
      
      if (path == '/') {
        request.response.headers.contentType = ContentType.html;
        request.response.write('<h1>✅ Custom ThingSpeak Backend is Running!</h1>');
        await request.response.close();
      } else if (path == '/update') {
        _handleUpdate(request);
      } else if (path.endsWith('/feeds/last.json')) {
        _handleLastFeed(request);
      } else if (path.endsWith('/feeds.json')) {
        _handleFeeds(request);
      } else {
        request.response.statusCode = HttpStatus.notFound;
        request.response.write('Not Found');
        await request.response.close();
      }
    } catch (e) {
      print('Error: $e');
      request.response.statusCode = HttpStatus.internalServerError;
      await request.response.close();
    }
  }
}

void _handleUpdate(HttpRequest request) async {
  final params = request.uri.queryParameters;
  final apiKey = params['api_key'];
  
  if (apiKey == null || apiKey.isEmpty) {
    request.response.write('0');
    await request.response.close();
    return;
  }
  
  final channelId = params['channel_id'] ?? 'custom_channel';
  currentEntryId++;
  
  final newEntry = {
    'entry_id': currentEntryId,
    'channel_id': channelId,
    'api_key': apiKey,
    'created_at': DateTime.now().toUtc().toIso8601String() + 'Z',
    'field1': params['field1'],
    'field2': params['field2'],
    'field3': params['field3'],
    'field4': params['field4'],
    'field5': params['field5'],
    'field6': params['field6'],
    'field7': params['field7'],
    'field8': params['field8'],
  };
  
  feeds.add(newEntry);
  saveData();
  
  print('Received Update! Entry ID: $currentEntryId');
  request.response.write('$currentEntryId');
  await request.response.close();
}

void _handleLastFeed(HttpRequest request) async {
  final pathSegments = request.uri.pathSegments;
  final channelId = pathSegments.length >= 2 ? pathSegments[1] : '0';
  
  if (feeds.isEmpty) {
    final emptyResponse = {
      "channel": {"id": channelId},
      "created_at": "",
      "entry_id": 0
    };
    request.response.headers.contentType = ContentType.json;
    request.response.write(jsonEncode(emptyResponse));
  } else {
    request.response.headers.contentType = ContentType.json;
    request.response.write(jsonEncode(feeds.last));
  }
  await request.response.close();
}

void _handleFeeds(HttpRequest request) async {
  final pathSegments = request.uri.pathSegments;
  final channelId = pathSegments.length >= 2 ? pathSegments[1] : '0';
  final params = request.uri.queryParameters;
  
  final resultsParam = params['results'];
  int limit = 100;
  if (resultsParam != null) {
    limit = int.tryParse(resultsParam) ?? 100;
  }
  
  final reversedFeeds = feeds.reversed.take(limit).toList();
  
  final responseMap = {
    "channel": {"id": channelId, "name": "Custom Channel"},
    "feeds": reversedFeeds.reversed.toList()
  };
  
  request.response.headers.contentType = ContentType.json;
  request.response.write(jsonEncode(responseMap));
  await request.response.close();
}
