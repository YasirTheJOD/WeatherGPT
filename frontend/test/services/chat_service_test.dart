import 'package:flutter_test/flutter_test.dart';

import 'package:weathergpt/core/api/api_client.dart';
import 'package:weathergpt/models/location.dart';
import 'package:weathergpt/services/chat/chat_service.dart';
import 'package:weathergpt/services/chat/typed_endpoint_chat_service.dart';

import '../helpers/mock_backend.dart';

void main() {
  const kolkata = SelectedLocation(
    name: 'Kolkata',
    latitude: 22.57,
    longitude: 88.36,
  );

  TypedEndpointChatService service({TestBackend? backend}) =>
      TypedEndpointChatService(
        api: ApiClient(client: (backend ?? TestBackend()).client),
      );

  test('current-weather query resolves location and grounds the reply', () async {
    final reply = await service().ask('What is the weather in Kolkata right now?');

    expect(reply.intent, ChatIntent.currentWeather);
    expect(reply.observation, isNotNull);
    expect(reply.observation!.locationName, 'Kolkata');
    expect(reply.location!.name, 'Kolkata');
    expect(reply.text, contains('Right now in Kolkata'));
    expect(reply.text, contains('29°C'));
    expect(reply.sourceName, 'Open-Meteo');
    expect(reply.suggestions, isNotEmpty);
  });

  test('forecast query (Hinglish) returns the day-2 forecast', () async {
    final reply = await service()
        .ask('Kal shaam Mumbai mein baarish hogi kya?');

    expect(reply.intent, ChatIntent.forecast);
    expect(reply.forecast, isNotEmpty);
    expect(reply.location!.name, 'Mumbai');
    expect(reply.text, contains('Tomorrow'));
    expect(reply.text, contains('high 31°'));
  });

  test('alerts query returns official warnings', () async {
    final reply = await service().ask('alerts in Kolkata');

    expect(reply.intent, ChatIntent.alerts);
    expect(reply.alerts, isNotEmpty);
    expect(reply.alerts.first.event, 'Heavy Rain');
    expect(reply.text, contains('official warning'));
    expect(reply.sourceName, 'sachet');
  });

  test('uses the current location when no place is named', () async {
    final reply = await service().ask('What is the weather?', currentLocation: kolkata);

    expect(reply.observation, isNotNull);
    expect(reply.location!.name, 'Kolkata');
  });

  test('asks for a place when neither message nor context has one', () async {
    final reply = await service().ask('What is the weather?');

    expect(reply.observation, isNull);
    expect(reply.text, contains('Which place'));
    expect(reply.suggestions, isNotEmpty);
  });

  test('asks which place when search is ambiguous', () async {
    final reply = await service(backend: TestBackend(ambiguousSearch: true))
        .ask('weather in Ranipur');

    expect(reply.candidates, hasLength(2));
    expect(reply.text, contains('Which one do you mean'));
    expect(reply.observation, isNull);
  });

  test('says so when a place is not found', () async {
    final reply = await service(backend: TestBackend(noSearchResults: true))
        .ask('weather in xyz');

    expect(reply.text, contains('couldn\'t find'));
  });

  test('answerForLocation answers with the same intent', () async {
    final service = TypedEndpointChatService(
      api: ApiClient(client: TestBackend().client),
    );
    const mumbai = LocationCandidate(
      name: 'Mumbai',
      state: 'Maharashtra',
      latitude: 19.07,
      longitude: 72.87,
      source: 'open-meteo',
      confidence: 0.9,
    );

    final reply = await service.answerForLocation(ChatIntent.forecast, mumbai);

    expect(reply.intent, ChatIntent.forecast);
    expect(reply.forecast, isNotEmpty);
    expect(reply.location!.name, 'Mumbai');
  });

  test('provider outage becomes a graceful reply, not a crash', () async {
    final reply = await service(backend: TestBackend(failWeather: true))
        .ask('weather in Kolkata');

    expect(reply.observation, isNull);
    expect(reply.text, contains('try again'));
  });
}