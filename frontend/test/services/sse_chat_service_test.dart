import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:weathergpt/core/api/api_client.dart';
import 'package:weathergpt/models/location.dart';
import 'package:weathergpt/services/chat/chat_service.dart';
import 'package:weathergpt/services/chat/sse_chat_service.dart';

import '../helpers/mock_backend.dart';

/// SSE frame as the FastAPI route emits it.
String sse(String event, Map<String, dynamic> data) =>
    'event: $event\ndata: ${jsonEncode(data)}\n\n';

Map<String, dynamic> candidateJson(String name) => {
      'name': name,
      'state': 'Test',
      'country': 'India',
      'country_code': 'IN',
      'latitude': 22.57,
      'longitude': 88.36,
      'source': 'open-meteo',
      'confidence': 0.99,
    };

Map<String, dynamic> chatDoneJson({
  String intent = 'current_weather',
  String text = 'Right now in Kolkata: 29°C, Overcast.',
}) =>
    {
      'text': text,
      'intent': intent,
      'observation': observationJson(),
      'forecast': <Object>[],
      'alerts': <Object>[],
      'location': candidateJson('Kolkata'),
      'candidates': <Object>[],
      'suggestions': ['Will it rain tomorrow?', 'Any alerts nearby?'],
      'source_name': 'Open-Meteo',
      'provenance_check': {'verified': true, 'checked_numbers': 2, 'unverified_numbers': <Object>[]},
    };

/// A single MockClient serving BOTH the `/chat` SSE stream (configurable) and
/// the typed endpoints the fallback service needs.
class SseBackend {
  SseBackend({
    this.chatError = false,
    this.chatUnreachable = false,
    this.disambiguation = false,
    this.emptyStream = false,
  });

  bool chatError;
  bool chatUnreachable;
  bool disambiguation;
  bool emptyStream;
  Map<String, dynamic>? lastChatBody;

  late final MockClient client = MockClient((request) async {
    final path = request.url.path;
    const jsonHeaders = {'content-type': 'application/json'};
    // Starlette emits text/event-stream with charset=utf-8; without the
    // charset, http.Response would latin1-encode non-ASCII (e.g. "°") and
    // the strict UTF-8 decoder would reject it.
    const sseHeaders = {'content-type': 'text/event-stream; charset=utf-8'};

    if (path.endsWith('/chat')) {
      if (chatUnreachable) {
        throw http.ClientException('connection refused (test)');
      }
      lastChatBody = jsonDecode(request.body) as Map<String, dynamic>;
      if (chatError) {
        return http.Response(sse('error', {'message': 'boom (test)'}), 200,
            headers: sseHeaders);
      }
      if (disambiguation) {
        final done = chatDoneJson()
          ..['text'] = 'I found several places named "Ranipur". Which one do you mean?'
          ..['observation'] = null
          ..['candidates'] = [
            candidateJson('Ranipur')..['state'] = 'Uttarakhand',
            candidateJson('Ranipur')..['state'] = 'Uttar Pradesh',
          ];
        return http.Response(
            sse('meta', {'status': 'resolving'}) + sse('done', done), 200,
            headers: sseHeaders);
      }
      if (emptyStream) {
        return http.Response(sse('meta', {'status': 'resolving'}), 200,
            headers: sseHeaders);
      }
      final done = chatDoneJson();
      return http.Response(
        sse('meta', {'status': 'resolving'}) +
            sse('meta', {'status': 'generating'}) +
            sse('delta', {'text': 'Right now in'}) +
            sse('delta', {'text': 'Kolkata: 29°C, Overcast.'}) +
            sse('done', done),
        200,
        headers: sseHeaders,
      );
    }

    // Typed endpoints (fallback path).
    if (path.endsWith('/locations/search')) {
      final q = request.url.queryParameters['q'] ?? 'kolkata';
      final name = q[0].toUpperCase() + q.substring(1);
      return http.Response(
        jsonEncode({
          'query': q,
          'normalized': q,
          'ambiguous': false,
          'candidates': [candidateJson(name)],
        }),
        200,
        headers: jsonHeaders,
      );
    }
    if (path.endsWith('/weather/current')) {
      return http.Response(
        jsonEncode({
          'observation': observationJson(),
          'provider_used': 'open-meteo',
          'validation': {'valid': true, 'issues': <Object>[]},
        }),
        200,
        headers: jsonHeaders,
      );
    }
    return http.Response('not found', 404);
  });
}

SseChatService service(SseBackend backend) =>
    SseChatService(api: ApiClient(client: backend.client));

void main() {
  test('ask consumes the SSE stream into a grounded ChatReply', () async {
    final backend = SseBackend();
    final reply = await service(backend).ask('weather in Kolkata');

    expect(backend.lastChatBody!['message'], 'weather in Kolkata');
    expect(reply.intent, ChatIntent.currentWeather);
    expect(reply.text, contains('Right now in Kolkata'));
    expect(reply.observation, isNotNull);
    expect(reply.observation!.temperatureC, 29.4);
    expect(reply.location!.name, 'Kolkata');
    expect(reply.sourceName, 'Open-Meteo');
    expect(reply.suggestions, isNotEmpty);
  });

  test('sends the current location with the message', () async {
    final backend = SseBackend();
    const kolkata = SelectedLocation(
      name: 'Kolkata',
      latitude: 22.57,
      longitude: 88.36,
    );
    await service(backend).ask('alerts near me', currentLocation: kolkata);

    final current = backend.lastChatBody!['current_location'] as Map;
    expect(current['name'], 'Kolkata');
    expect(current['latitude'], 22.57);
  });

  test('maps a disambiguation done-payload to candidates', () async {
    final backend = SseBackend(disambiguation: true);
    final reply = await service(backend).ask('weather in Ranipur');

    expect(reply.candidates, hasLength(2));
    expect(reply.candidates.first.name, 'Ranipur');
    expect(reply.text, contains('Which one do you mean'));
    expect(reply.observation, isNull);
  });

  test('answerForLocation posts the candidate + intent', () async {
    final backend = SseBackend();
    const mumbai = LocationCandidate(
      name: 'Mumbai',
      state: 'Maharashtra',
      latitude: 19.07,
      longitude: 72.87,
      source: 'aliases',
      confidence: 0.9,
    );
    await service(backend).answerForLocation(ChatIntent.forecast, mumbai);

    final body = backend.lastChatBody!;
    expect(body['intent'], 'forecast');
    expect((body['candidate'] as Map)['name'], 'Mumbai');
  });

  test('server-side error event falls back to the typed endpoints', () async {
    final backend = SseBackend(chatError: true);
    final reply = await service(backend).ask('weather in Kolkata');

    // Fallback answered from the real typed endpoints (grounded, no crash).
    expect(reply.text, contains('Right now in Kolkata'));
    expect(reply.observation, isNotNull);
  });

  test('unreachable backend falls back to the typed endpoints', () async {
    final backend = SseBackend(chatUnreachable: true);
    final reply = await service(backend).ask('weather in Kolkata');

    expect(reply.text, contains('Right now in Kolkata'));
    expect(reply.observation, isNotNull);
  });

  test('stream ending without done falls back to the typed endpoints', () async {
    final backend = SseBackend(emptyStream: true);
    final reply = await service(backend).ask('weather in Kolkata');

    expect(reply.text, contains('Right now in Kolkata'));
    expect(reply.observation, isNotNull);
  });

  group('stream()', () {
    test('emits each delta as it arrives, then the done reply', () async {
      final backend = SseBackend();
      final events =
          await service(backend).stream('weather in Kolkata').toList();

      expect(events, hasLength(3));
      expect((events[0] as ChatDelta).text, 'Right now in');
      expect((events[1] as ChatDelta).text, 'Kolkata: 29°C, Overcast.');

      final done = events.last;
      expect(done, isA<ChatDone>());
      final reply = (done as ChatDone).reply;
      expect(reply.text, contains('Right now in Kolkata'));
      expect(reply.observation, isNotNull);
      expect(reply.location!.name, 'Kolkata');
    });

    test('meta frames produce no events (progress is not answer text)', () async {
      final backend = SseBackend();
      final events =
          await service(backend).stream('weather in Kolkata').toList();

      expect(events.whereType<ChatDelta>(), hasLength(2));
      expect(events.whereType<ChatDone>(), hasLength(1));
    });

    test('a server-side error still ends in a complete fallback reply',
        () async {
      final backend = SseBackend(chatError: true);
      final events =
          await service(backend).stream('weather in Kolkata').toList();

      final done = events.single as ChatDone;
      expect(done.reply.text, contains('Right now in Kolkata'));
      expect(done.reply.observation, isNotNull);
    });

    test('an unreachable backend falls back inside the stream too', () async {
      final backend = SseBackend(chatUnreachable: true);
      final events =
          await service(backend).stream('weather in Kolkata').toList();

      expect((events.single as ChatDone).reply.observation, isNotNull);
    });

    test('the current location rides along on the streaming request', () async {
      final backend = SseBackend();
      const kolkata = SelectedLocation(
        name: 'Kolkata',
        latitude: 22.57,
        longitude: 88.36,
      );
      await service(backend)
          .stream('alerts near me', currentLocation: kolkata)
          .toList();

      final current = backend.lastChatBody!['current_location'] as Map;
      expect(current['name'], 'Kolkata');
    });

    test('ask() and stream() agree on the same answer', () async {
      final backend = SseBackend();
      final service_ = service(backend);

      final buffered = await service_.ask('weather in Kolkata');
      final streamed =
          (await service_.stream('weather in Kolkata').last) as ChatDone;

      expect(streamed.reply.text, buffered.text);
      expect(streamed.reply.sourceName, buffered.sourceName);
      expect(streamed.reply.observation!.temperatureC,
          buffered.observation!.temperatureC);
    });
  });
}