import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:weathergpt/core/api/api_client.dart';
import 'package:weathergpt/services/locations_service.dart';

void main() {
  test('search() parses candidates and the ambiguity flag', () async {
    final client = MockClient((request) async {
      expect(request.url.queryParameters['q'], 'ranipur');
      return http.Response(
        jsonEncode({
          'query': 'ranipur',
          'normalized': 'ranipur',
          'ambiguous': true,
          'candidates': [
            {
              'name': 'Ranipur',
              'state': 'Uttarakhand',
              'country': 'India',
              'country_code': 'IN',
              'latitude': 29.5,
              'longitude': 78.5,
              'source': 'aliases',
              'confidence': 0.71,
            },
            {
              'name': 'Ranipur',
              'state': 'Uttar Pradesh',
              'country': 'India',
              'country_code': 'IN',
              'latitude': 28.6,
              'longitude': 77.8,
              'source': 'open-meteo',
              'confidence': 0.68,
            },
          ],
        }),
        200,
        headers: {'content-type': 'application/json'},
      );
    });
    final service = LocationsService(api: ApiClient(client: client));

    final result = await service.search('ranipur');

    expect(result.query, 'ranipur');
    expect(result.ambiguous, isTrue, reason: 'close-confidence candidates');
    expect(result.candidates, hasLength(2));
    expect(result.candidates.first.source, 'aliases');
    expect(result.candidates.first.confidence, 0.71);
  });

  test('reverse() returns the candidate on 200', () async {
    final client = MockClient((request) async {
      return http.Response(
        jsonEncode({
          'name': 'Kolkata',
          'state': 'West Bengal',
          'latitude': 22.57,
          'longitude': 88.36,
          'source': 'bigdatacloud',
          'confidence': 0.9,
        }),
        200,
        headers: {'content-type': 'application/json'},
      );
    });
    final service = LocationsService(api: ApiClient(client: client));

    final candidate = await service.reverse(22.57, 88.36);

    expect(candidate, isNotNull);
    expect(candidate!.name, 'Kolkata');
  });

  test('reverse() returns null on 404 (no known place)', () async {
    final client = MockClient((request) async {
      return http.Response(
        jsonEncode({
          'detail': {'message': 'No known location near those coordinates.'}
        }),
        404,
        headers: {'content-type': 'application/json'},
      );
    });
    final service = LocationsService(api: ApiClient(client: client));

    final candidate = await service.reverse(0, 0);

    expect(candidate, isNull);
  });
}