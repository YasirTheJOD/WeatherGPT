import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:weathergpt/core/api/api_client.dart';
import 'package:weathergpt/services/sources_service.dart';
import 'package:weathergpt/state/sources_controller.dart';

/// The registry is shared by the drawer and both tab strips, so it must be
/// fetched once — and a failure must be explicit, never silently healthy.
void main() {
  test('load() fetches once and shares the result across consumers', () async {
    var calls = 0;
    final controller = SourcesController(
      service: _service((_) async {
        calls += 1;
        return _json({'sources': [_imd(available: false)]});
      }),
    );

    await controller.load();
    await controller.load(); // second consumer: no-op
    expect(calls, 1);

    expect(controller.hasLiveData, isTrue);
    expect(controller.failed, isFalse);
    expect(controller.loading, isFalse);
    expect(controller.byId('imd')?.available, isFalse);
    expect(controller.byId('nope'), isNull);

    await controller.load(force: true); // retry: fetches again
    expect(calls, 2);
  });

  test('an unreachable registry fails explicitly instead of throwing', () async {
    final controller = SourcesController(
      service: _service((_) async => _json({'detail': {}}, status: 503)),
    );

    await controller.load();

    expect(controller.failed, isTrue);
    expect(controller.hasLiveData, isFalse);
    expect(controller.sources, isNull);
  });

  test('an empty registry counts as a failure, not a healthy state', () async {
    final controller = SourcesController(
      service: _service((_) async => _json({'sources': <Object>[]})),
    );

    await controller.load();

    expect(controller.failed, isTrue);
    expect(controller.hasLiveData, isFalse);
  });

  test('retry() clears a previous failure once the registry answers', () async {
    var calls = 0;
    final controller = SourcesController(
      service: _service((_) async {
        calls += 1;
        if (calls == 1) return _json({'detail': {}}, status: 503);
        return _json({'sources': [_imd()]});
      }),
    );

    await controller.load();
    expect(controller.failed, isTrue);

    await controller.retry();

    expect(controller.failed, isFalse);
    expect(controller.hasLiveData, isTrue);
    expect(controller.byId('imd'), isNotNull);
    expect(calls, 2);
  });
}

SourcesService _service(
  Future<http.Response> Function(http.Request request) handler,
) =>
    SourcesService(
      api: ApiClient(client: MockClient(handler), baseUrl: 'http://test'),
    );

http.Response _json(Object body, {int status = 200}) => http.Response(
      jsonEncode(body),
      status,
      headers: {'content-type': 'application/json'},
    );

Map<String, dynamic> _imd({bool available = true}) => {
      'source_id': 'imd',
      'name': 'IMD — India Meteorological Department',
      'role': 'Official warnings',
      'status': 'requires_authorization',
      'official': true,
      'auth': 'API key',
      'url': 'https://api.imd.gov.in',
      'evidence_url': null,
      'available': available,
      'available_message': available ? null : 'IMD_API_KEY not set',
      'notes': null,
    };
