import 'package:flutter_test/flutter_test.dart';

import 'package:weathergpt/core/api/api_client.dart';
import 'package:weathergpt/models/location.dart';
import 'package:weathergpt/services/weather_service.dart';

import '../helpers/mock_backend.dart';

void main() {
  const kolkata = SelectedLocation(
    name: 'Kolkata',
    latitude: 22.57,
    longitude: 88.36,
  );

  test('current() parses observation, provenance, provider and validation',
      () async {
    final service = WeatherService(
      api: ApiClient(client: TestBackend().client),
    );

    final result = await service.current(kolkata);

    expect(result.providerUsed, 'open-meteo');
    expect(result.validation, isNotNull);
    expect(result.validation!.valid, isTrue);

    final o = result.observation;
    expect(o.locationName, 'Kolkata');
    expect(o.temperatureC, 29.4);
    expect(o.humidityPct, 78.0);
    expect(o.windSpeedKmph, 12.6);
    expect(o.windDirection, 'S');
    expect(o.pressureHpa, 1008.0);
    expect(o.conditionText, 'Overcast');
    expect(o.rainfall24hMm, 2.3);
    expect(o.observedAt, isNotNull);

    expect(o.provenance.sourceId, 'open-meteo');
    expect(o.provenance.sourceName, 'Open-Meteo');
    expect(o.provenance.authoritative, isFalse);
    expect(o.provenance.fetchedAt, isNotNull);
  });

  test('forecast() parses the day list in order', () async {
    final service = WeatherService(
      api: ApiClient(client: TestBackend().client),
    );

    final result = await service.forecast(kolkata);

    expect(result.days, hasLength(2));
    expect(result.days.first.date, '2026-09-07');
    expect(result.days.first.tmaxC, 32.0);
    expect(result.days.first.tminC, 25.0);
    expect(result.days.first.rainfallMm, 4.5);
    expect(result.days.first.provenance.sourceName, 'Open-Meteo');

    // Second day omits rain — null must stay null, not 0.
    expect(result.days[1].rainfallMm, isNull);
  });

  test('surfaces the backend detail message on provider outage', () async {
    final backend = TestBackend(failWeather: true);
    final service = WeatherService(api: ApiClient(client: backend.client));

    await expectLater(
      service.current(kolkata),
      throwsA(
        isA<ApiException>().having(
          (e) => e.message,
          'message',
          'Provider unavailable (test failure).',
        ),
      ),
    );
  });
}