import 'dart:convert';

import '../../core/api/api_client.dart';
import '../../models/alert.dart';
import '../../models/location.dart';
import '../../models/weather.dart';
import 'chat_service.dart';
import 'typed_endpoint_chat_service.dart';

/// Phase 5 ChatService implementation — the real backend `/chat` endpoint
/// over Server-Sent Events.
///
/// The backend streams query understanding → retrieval → grounded answer:
///   `meta`  — pipeline progress (ignored here; the UI shows its own spinner)
///   `delta` — partial answer text → surfaced as [ChatDelta]
///   `done`  — the full structured reply (text + cards + suggestions)
///             → surfaced as [ChatDone]
///   `error` — fatal server-side message
///
/// [ask] is the buffered form (deltas dropped, the `done` reply returned) and
/// [stream] is the progressive form the chat UI renders as it arrives; both
/// share one code path, so their fallback behaviour cannot drift apart.
///
/// Resilience: when the backend is unreachable or streams an error, this
/// falls back to the deterministic [TypedEndpointChatService] (grounded in
/// the real typed endpoints) — the demo never dies on a backend outage.
class SseChatService extends ChatService {
  SseChatService({ApiClient? api, ChatService? fallback})
      : _api = api ?? ApiClient(),
        _fallback = fallback ?? TypedEndpointChatService(api: api);

  final ApiClient _api;
  final ChatService _fallback;

  @override
  Stream<ChatStreamEvent> stream(
    String message, {
    SelectedLocation? currentLocation,
  }) async* {
    // Note the `await for` + `yield` loops rather than `yield*`: an error
    // raised by a `yield*` escapes the `async*` body's try/catch (it is
    // forwarded straight to the listener), which would silently skip the
    // fallback below.
    try {
      final events = await _api.postSse('/chat', json: {
        'message': message,
        if (currentLocation != null) 'current_location': _locationJson(currentLocation),
      });
      await for (final event in _consume(events)) {
        yield event;
      }
    } on ApiException {
      // Transport failure or server-side error → deterministic typed endpoints.
      // This also covers a stream that dies *after* some deltas: the UI
      // replaces its draft with this complete reply, so the bubble still ends
      // grounded rather than half-written.
      await for (final event
          in _fallback.stream(message, currentLocation: currentLocation)) {
        yield event;
      }
    }
  }

  @override
  Future<ChatReply> ask(
    String message, {
    SelectedLocation? currentLocation,
  }) =>
      _replyFrom(stream(message, currentLocation: currentLocation));

  @override
  Future<ChatReply> answerForLocation(
    ChatIntent intent,
    LocationCandidate candidate,
  ) async {
    try {
      final events = await _api.postSse('/chat', json: {
        'candidate': _candidateJson(candidate),
        'intent': _intentName(intent),
      });
      return await _replyFrom(_consume(events));
    } on ApiException {
      return _fallback.answerForLocation(intent, candidate);
    }
  }

  // -------------------------------------------------------------------------
  // SSE consumption
  // -------------------------------------------------------------------------

  /// Consumes an SSE stream into [ChatStreamEvent]s. A stream that ends
  /// without `done` is a failure, not a successful empty answer.
  Stream<ChatStreamEvent> _consume(Stream<SseEvent> events) async* {
    await for (final event in events) {
      switch (event.event) {
        case 'delta':
          final text = _deltaText(event.data);
          if (text.isNotEmpty) yield ChatDelta(text);
        case 'done':
          yield ChatDone(_replyFromJson(_decode(event.data)));
          return;
        case 'error':
          throw ApiException(_errorMessage(event.data));
      }
    }
    throw const ApiException('The chat stream ended without a reply.');
  }

  /// The buffered form of [_consume].
  Future<ChatReply> _replyFrom(Stream<ChatStreamEvent> events) async {
    await for (final event in events) {
      if (event is ChatDone) return event.reply;
    }
    throw const ApiException('The chat stream ended without a reply.');
  }

  /// A malformed `delta` frame is skipped rather than fatal: `done` still
  /// carries the complete text, so a dropped chunk can only cost a flicker.
  String _deltaText(String data) {
    try {
      final decoded = jsonDecode(data);
      if (decoded is Map && decoded['text'] is String) {
        return decoded['text'] as String;
      }
    } on FormatException {
      // Fall through to the empty string.
    }
    return '';
  }

  Map<String, dynamic> _decode(String data) {
    try {
      return jsonDecode(data) as Map<String, dynamic>;
    } on FormatException {
      throw const ApiException('Unexpected reply from the server.');
    }
  }

  String _errorMessage(String data) {
    try {
      final decoded = jsonDecode(data);
      if (decoded is Map && decoded['message'] is String) {
        return decoded['message'] as String;
      }
    } on FormatException {
      // Fall through to the generic message.
    }
    return 'The weather service could not answer right now.';
  }

  ChatReply _replyFromJson(Map<String, dynamic> json) => ChatReply(
        text: json['text'] as String? ?? '',
        intent: _intentFrom(json['intent'] as String?),
        observation: json['observation'] is Map<String, dynamic>
            ? WeatherObservation.fromJson(
                json['observation'] as Map<String, dynamic>)
            : null,
        forecast: _objects(json['forecast']).map(ForecastDay.fromJson).toList(),
        alerts: _objects(json['alerts']).map(Alert.fromJson).toList(),
        location: json['location'] is Map<String, dynamic>
            ? SelectedLocation.fromCandidate(
                LocationCandidate.fromJson(json['location'] as Map<String, dynamic>))
            : null,
        candidates: _objects(json['candidates'])
            .map(LocationCandidate.fromJson)
            .toList(),
        suggestions:
            json['suggestions'] is List ? json['suggestions']!.whereType<String>().toList() : const [],
        sourceName: json['source_name'] as String?,
      );

  static List<Map<String, dynamic>> _objects(Object? value) => value is List
      ? value.whereType<Map<String, dynamic>>().toList()
      : const [];

  static ChatIntent _intentFrom(String? value) => switch (value) {
        'current_weather' => ChatIntent.currentWeather,
        'forecast' => ChatIntent.forecast,
        'alerts' => ChatIntent.alerts,
        _ => ChatIntent.unknown,
      };

  static String _intentName(ChatIntent intent) => switch (intent) {
        ChatIntent.currentWeather => 'current_weather',
        ChatIntent.forecast => 'forecast',
        ChatIntent.alerts => 'alerts',
        ChatIntent.unknown => 'current_weather',
      };

  static Map<String, dynamic> _locationJson(SelectedLocation l) => {
        'name': l.name,
        'state': l.state,
        'latitude': l.latitude,
        'longitude': l.longitude,
        'source': l.source ?? 'device-gps',
        'confidence': l.confidence ?? 0.9,
      };

  static Map<String, dynamic> _candidateJson(LocationCandidate c) => {
        'name': c.name,
        'state': c.state,
        'country': c.country,
        'country_code': c.countryCode,
        'latitude': c.latitude,
        'longitude': c.longitude,
        'source': c.source,
        'confidence': c.confidence,
      };
}