import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:weathergpt/core/api/api_client.dart';
import 'package:weathergpt/services/sources_service.dart';

Map<String, dynamic> _source({
  required String id,
  required String name,
  bool official = false,
  bool available = true,
  String status = 'implemented',
  String? availableMessage,
}) =>
    {
      'source_id': id,
      'name': name,
      'role': 'Primary role text',
      'status': status,
      'official': official,
      'auth': 'None (keyless)',
      'url': 'https://example.test',
      'evidence_url': 'https://example.test/docs',
      'available': available,
      'available_message': availableMessage,
      'notes': null,
    };

SourcesService _serviceWith(Object body, {int status = 200}) {
  final client = MockClient((request) async {
    expect(request.url.path, endsWith('/sources'));
    return http.Response(jsonEncode(body), status,
        headers: {'content-type': 'application/json'});
  });
  return SourcesService(api: ApiClient(client: client, baseUrl: 'http://test'));
}

void main() {
  test('fetch() parses the registry including live availability', () async {
    final service = _serviceWith({
      'generated_at': '2026-09-19T00:00:00Z',
      'counts': {'total': 2, 'available': 1, 'official': 1},
      'sources': [
        _source(
          id: 'imd',
          name: 'IMD — India Meteorological Department',
          official: true,
          available: false,
          status: 'requires_authorization',
          availableMessage: 'IMD_API_KEY not set — running on the Open-Meteo fallback',
        ),
        _source(id: 'open_meteo', name: 'Open-Meteo (GFS-derived)'),
      ],
    });

    final sources = await service.fetch();

    expect(sources, hasLength(2));
    final imd = sources.first;
    expect(imd.id, 'imd');
    expect(imd.official, isTrue);
    expect(imd.available, isFalse);
    expect(imd.status, 'requires_authorization');
    expect(imd.availableMessage, contains('IMD_API_KEY'));
    expect(sources.last.available, isTrue);
    expect(sources.last.evidenceUrl, isNotNull);
  });

  test('fetch() tolerates a missing or malformed sources list', () async {
    expect(await _serviceWith({'counts': {}}).fetch(), isEmpty);
    expect(await _serviceWith({'sources': 'nope'}).fetch(), isEmpty);
  });

  test('fetch() surfaces an ApiException when the registry is down', () async {
    final service = _serviceWith(
      {
        'detail': {'message': 'Registry unavailable.'}
      },
      status: 503,
    );

    await expectLater(service.fetch(), throwsA(isA<ApiException>()));
  });
}
