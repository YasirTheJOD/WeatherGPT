import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config/app_config.dart';

/// Error surfaced to the UI. Carries the backend's `detail.message` when the
/// FastAPI layer provided one (e.g. provider outages → 503).
class ApiException implements Exception {
  const ApiException(this.message, {this.statusCode});

  final String message;
  final int? statusCode;

  @override
  String toString() => message;
}

/// One Server-Sent Events frame: an event name plus its payload.
///
/// The `/chat` endpoint streams `meta` / `delta` / `done` / `error` events;
/// `data` is the raw payload string (JSON for this backend), so consumers
/// decode it themselves.
class SseEvent {
  const SseEvent({required this.event, required this.data});

  final String event;
  final String data;
}

/// Typed API client for the WeatherGPT API.
///
/// All calls hit `/api/v1/...`. This stays the single place where transport
/// concerns live (timeout, decoding, error mapping); feature services map the
/// JSON into the typed models in `lib/models/`. JSON GETs use [getJson];
/// the conversational endpoint streams via [postSse].
class ApiClient {
  ApiClient({http.Client? client, String? baseUrl})
      : _client = client ?? http.Client(),
        _baseUrl = baseUrl ?? AppConfig.apiRoot;

  final http.Client _client;
  final String _baseUrl;

  Future<Map<String, dynamic>> getJson(
    String path, {
    Map<String, String>? query,
  }) async {
    final uri = Uri.parse('$_baseUrl$path').replace(queryParameters: query);
    final http.Response response;
    try {
      response = await _client
          .get(uri)
          .timeout(AppConfig.requestTimeout);
    } on TimeoutException {
      throw ApiException('The server took too long to respond. Please retry.');
    } on http.ClientException catch (e) {
      throw ApiException('Could not reach the WeatherGPT API: ${e.message}');
    } on Exception catch (e) {
      throw ApiException('Network error: $e');
    }
    return _decode(response);
  }

  /// POST `path` with a JSON body and consume the response as a
  /// Server-Sent Events stream. Non-200 responses are surfaced as
  /// [ApiException] before the stream starts; mid-stream failures arrive as
  /// an `error` event on the returned stream.
  Future<Stream<SseEvent>> postSse(
    String path, {
    Map<String, dynamic>? json,
  }) async {
    final uri = Uri.parse('$_baseUrl$path');
    final request = http.Request('POST', uri)
      ..headers['content-type'] = 'application/json'
      ..body = jsonEncode(json ?? const {});

    final http.StreamedResponse response;
    try {
      response = await _client.send(request).timeout(AppConfig.requestTimeout);
    } on TimeoutException {
      throw ApiException('The server took too long to respond. Please retry.');
    } on http.ClientException catch (e) {
      throw ApiException('Could not reach the WeatherGPT API: ${e.message}');
    } on Exception catch (e) {
      throw ApiException('Network error: $e');
    }

    if (response.statusCode != 200) {
      final body = await response.stream.bytesToString();
      throw _errorFrom(response.statusCode, body);
    }
    return response.stream
        .transform(utf8.decoder)
        .transform(const LineSplitter())
        .transform(const _SseParser());
  }

  Map<String, dynamic> _decode(http.Response response) {
    if (response.statusCode == 200) {
      try {
        return jsonDecode(response.body) as Map<String, dynamic>;
      } on FormatException {
        throw const ApiException('Unexpected response from the server.');
      } on TypeError {
        throw const ApiException('Unexpected response shape from the server.');
      }
    }
    throw _errorFrom(response.statusCode, response.body);
  }

  /// Surface a backend-provided `detail: {message: ...}` when present.
  ApiException _errorFrom(int statusCode, String body) {
    String detail = 'Request failed (HTTP $statusCode).';
    try {
      final decoded = jsonDecode(body);
      final detailField = (decoded is Map && decoded['detail'] is Map)
          ? decoded['detail']
          : null;
      if (detailField is Map && detailField['message'] is String) {
        detail = detailField['message'] as String;
      }
    } on FormatException {
      // Non-JSON error body — keep the generic message.
    }
    return ApiException(detail, statusCode: statusCode);
  }
}

/// Converts an SSE byte/line stream into frames: `event:` + `data:` lines
/// terminated by a blank line. Multi-line data is joined with `\n` (the
/// spec's behaviour); comment lines (starting with `:`) are ignored.
class _SseParser extends StreamTransformerBase<String, SseEvent> {
  const _SseParser();

  @override
  Stream<SseEvent> bind(Stream<String> source) async* {
    var event = 'message';
    final data = <String>[];
    await for (final rawLine in source) {
      final line =
          rawLine.endsWith('\r') ? rawLine.substring(0, rawLine.length - 1) : rawLine;
      if (line.isEmpty) {
        if (data.isNotEmpty) {
          yield SseEvent(event: event, data: data.join('\n'));
        }
        event = 'message';
        data.clear();
      } else if (line.startsWith('event:')) {
        event = line.substring('event:'.length).trim();
      } else if (line.startsWith('data:')) {
        data.add(line.substring('data:'.length).trimLeft());
      }
      // Comments and unknown fields are ignored per the SSE spec.
    }
    if (data.isNotEmpty) {
      yield SseEvent(event: event, data: data.join('\n'));
    }
  }
}