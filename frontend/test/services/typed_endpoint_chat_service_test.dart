import 'package:flutter_test/flutter_test.dart';

import 'package:weathergpt/core/api/api_client.dart';
import 'package:weathergpt/services/alerts_service.dart';
import 'package:weathergpt/services/chat/chat_service.dart';
import 'package:weathergpt/services/chat/typed_endpoint_chat_service.dart';
import 'package:weathergpt/services/locations_service.dart';
import 'package:weathergpt/services/weather_service.dart';

import '../helpers/mock_backend.dart';

/// The SSE adapter falls back to this service on transport failure, so its
/// multilingual router must mirror the backend parser's vocabulary — in
/// particular Devanagari must survive place extraction.
void main() {
  late TestBackend backend;
  late TypedEndpointChatService service;

  setUp(() {
    backend = TestBackend();
    final api = ApiClient(client: backend.client, baseUrl: 'http://test');
    service = TypedEndpointChatService(
      locations: LocationsService(api: api),
      weather: WeatherService(api: api),
      alerts: AlertsService(api: api),
    );
  });

  test('Devanagari weather query resolves the place instead of asking again',
      () async {
    final reply = await service.ask('आज कोलकाता में मौसम कैसा है');

    expect(reply.text, isNot(contains('Which place are you asking about')));
    expect(reply.text, isNot(contains("couldn't find a place")));
    expect(reply.intent, ChatIntent.currentWeather);
    expect(reply.location, isNotNull);
    expect(reply.observation, isNotNull);
  });

  test('Devanagari "कल बारिश" routes to the forecast path', () async {
    final reply = await service.ask('कल दिल्ली में बारिश होगी क्या');

    expect(reply.intent, ChatIntent.forecast);
    expect(reply.location, isNotNull);
    expect(reply.forecast, isNotEmpty);
  });

  test('the contracted opening prompt still resolves the place', () async {
    // Regression: "What's" must fold to "whats", not leave a stray "s" token in
    // the place name (which is how the scripted demo prompt broke).
    final reply = await service.ask("What's the weather in Kolkata right now?");

    expect(reply.text, isNot(contains('Which place are you asking about')));
    expect(reply.text, isNot(contains("couldn't find a place")));
    expect(reply.location?.name, 'Kolkata');
    expect(reply.observation, isNotNull);
  });

  test('Hinglish forecast still routes to the forecast path', () async {
    final reply = await service.ask('Kal shaam Mumbai mein baarish hogi kya?');

    expect(reply.intent, ChatIntent.forecast);
    expect(reply.location, isNotNull);
  });
}
