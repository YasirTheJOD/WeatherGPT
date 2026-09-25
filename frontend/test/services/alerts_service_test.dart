import 'package:flutter_test/flutter_test.dart';

import 'package:weathergpt/core/api/api_client.dart';
import 'package:weathergpt/models/location.dart';
import 'package:weathergpt/services/alerts_service.dart';

import '../helpers/mock_backend.dart';

void main() {
  const kolkata = SelectedLocation(
    name: 'Kolkata',
    latitude: 22.57,
    longitude: 88.36,
  );

  test('nearby() parses CAP alerts, severity and provenance', () async {
    final service = AlertsService(
      api: ApiClient(client: TestBackend().client),
    );

    final result = await service.nearby(kolkata, radiusKm: 20);

    expect(result.source, 'sachet');
    expect(result.alerts, hasLength(1));

    final alert = result.alerts.first;
    expect(alert.event, 'Heavy Rain');
    expect(alert.severity, 'Severe');
    expect(alert.headline, isNotNull);
    expect(alert.description, 'Heavy rain expected over the next 24 hours.');
    expect(alert.instruction, contains('Avoid waterlogged'));
    expect(alert.effectiveAt, isNotNull);
    expect(alert.expiresAt, isNotNull);
    expect(alert.areas.first.areaDesc, 'Kolkata, Howrah');
    expect(alert.provenance.sourceName, 'SACHET');
  });

  test('nearby() returns an empty list when no alerts exist', () async {
    final service = AlertsService(
      api: ApiClient(client: TestBackend(noAlerts: true).client),
    );

    final result = await service.nearby(kolkata);

    expect(result.alerts, isEmpty);
    expect(result.source, 'sachet');
  });
}