import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

/// Fixtures shaped exactly like the FastAPI responses
/// (backend/app/api/routes/weather.py, locations.py, domain/models.py).

Map<String, dynamic> provenanceJson({
  bool authoritative = false,
  String sourceName = 'Open-Meteo',
}) =>
    {
      'source_id': sourceName.toLowerCase().replaceAll(' ', '-'),
      'source_name': sourceName,
      'authoritative': authoritative,
      'fetched_at': '2026-09-07T08:31:00Z',
      'valid_at': '2026-09-07T09:31:00Z',
      'ttl_seconds': 3600,
      'raw_endpoint': null,
    };

Map<String, dynamic> observationJson() => {
      'latitude': 22.57,
      'longitude': 88.36,
      'location_name': 'Kolkata',
      'temperature_c': 29.4,
      'humidity_pct': 78.0,
      'wind_speed_kmph': 12.6,
      'wind_direction': 'S',
      'pressure_hpa': 1008.0,
      'weather_code': 3,
      'condition_text': 'Overcast',
      'rainfall_24h_mm': 2.3,
      'observed_at': '2026-09-07T08:30:00Z',
      'provenance': provenanceJson(),
    };

Map<String, dynamic> forecastDayJson({
  required String date,
  double tmax = 32,
  double tmin = 25,
  double? rain = 4.5,
}) =>
    {
      'date': date,
      'tmax_c': tmax,
      'tmin_c': tmin,
      'condition_text': 'Overcast',
      'rainfall_mm': rain,
      'humidity_pct': 75.0,
      'wind_speed_kmph': 10.0,
      'provenance': provenanceJson(),
    };

Map<String, dynamic> searchResponseJson({bool ambiguous = false}) => {
      'query': ambiguous ? 'ranipur' : 'kolkata',
      'normalized': ambiguous ? 'ranipur' : 'kolkata',
      'ambiguous': ambiguous,
      'candidates': ambiguous
          ? [
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
            ]
          : [
              {
                'name': 'Kolkata',
                'state': 'West Bengal',
                'country': 'India',
                'country_code': 'IN',
                'latitude': 22.57,
                'longitude': 88.36,
                'source': 'open-meteo',
                'confidence': 0.99,
              },
            ],
    };

Map<String, dynamic> reverseResponseJson() => {
      'name': 'Kolkata',
      'state': 'West Bengal',
      'country': 'India',
      'country_code': 'IN',
      'latitude': 22.57,
      'longitude': 88.36,
      'source': 'bigdatacloud',
      'confidence': 0.9,
    };

Map<String, dynamic> alertJson({String severity = 'Severe'}) => {
      'identifier': 'CAP-20260907-001',
      'sender': 'NDMA',
      'sent_at': '2026-09-07T06:00:00Z',
      'status': 'Actual',
      'msg_type': 'Alert',
      'scope': 'Public',
      'event': 'Heavy Rain',
      'category': 'Met',
      'urgency': 'Expected',
      'severity': severity,
      'certainty': 'Likely',
      'effective_at': '2026-09-07T06:00:00Z',
      'expires_at': '2026-09-08T06:00:00Z',
      'headline': 'Heavy to very heavy rainfall very likely at isolated places',
      'description': 'Heavy rain expected over the next 24 hours.',
      'instruction': 'Avoid waterlogged areas; do not drive through flooded roads.',
      'areas': [
        {'area_desc': 'Kolkata, Howrah', 'circles': <Object>[], 'polygons': <Object>[]},
      ],
      'polygon_url': null,
      'provenance': provenanceJson(sourceName: 'SACHET'),
    };

Map<String, dynamic> alertsResponseJson({bool empty = false}) => {
      'alerts': empty ? <Object>[] : [alertJson()],
      'source': 'sachet',
    };

Map<String, dynamic> sourceJson(
  String id,
  String name, {
  bool official = false,
  bool available = true,
  String status = 'implemented',
  String? availableMessage,
}) =>
    {
      'source_id': id,
      'name': name,
      'role': 'Role text from the backend',
      'status': status,
      'official': official,
      'auth': 'None (keyless)',
      'url': 'https://example.test',
      'evidence_url': null,
      'available': available,
      'available_message': availableMessage,
      'notes': null,
    };

/// The source registry. Note this is served even when `failWeather` is set:
/// a weather/alert outage and a registry outage are different failures, and the
/// screens' retry buttons must stay unambiguous in tests.
Map<String, dynamic> sourcesResponseJson() => {
      'generated_at': '2026-09-19T00:00:00Z',
      'counts': {'total': 4, 'available': 3, 'official': 2},
      'sources': [
        sourceJson(
          'imd',
          'IMD — India Meteorological Department',
          official: true,
          available: false,
          status: 'requires_authorization',
          availableMessage: 'IMD_API_KEY not set',
        ),
        sourceJson('open_meteo', 'Open-Meteo (GFS-derived)'),
        sourceJson(
          'sachet',
          'SACHET — NDMA National Disaster Alert Portal',
          official: true,
        ),
        sourceJson('openstreetmap', 'OpenStreetMap'),
      ],
    };

/// Stateful fake backend. Flip [failWeather] to simulate a provider outage
/// (503 with the FastAPI `detail.message` shape) and recover on retry.
class TestBackend {
  TestBackend({
    this.failWeather = false,
    this.noAlerts = false,
    this.ambiguousSearch = false,
    this.noSearchResults = false,
  });

  bool failWeather;
  bool noAlerts;
  bool ambiguousSearch;
  bool noSearchResults;

  late final MockClient client = MockClient((request) async {
    final path = request.url.path;
    const jsonHeaders = {'content-type': 'application/json'};

    if (path.endsWith('/locations/search')) {
      if (noSearchResults) {
        return http.Response(
          jsonEncode({
            'query': 'xyz',
            'normalized': 'xyz',
            'ambiguous': false,
            'candidates': <Object>[],
          }),
          200,
          headers: jsonHeaders,
        );
      }
      // Like a real geocoder, echo the query back as the candidate name
      // (except the scripted ambiguous case below).
      final q = request.url.queryParameters['q'] ?? 'kolkata';
      final name = q[0].toUpperCase() + q.substring(1);
      return http.Response(
        jsonEncode(ambiguousSearch
            ? searchResponseJson(ambiguous: true)
            : {
                'query': q,
                'normalized': q,
                'ambiguous': false,
                'candidates': [
                  {
                    'name': name,
                    'state': 'Test',
                    'country': 'India',
                    'country_code': 'IN',
                    'latitude': 22.57,
                    'longitude': 88.36,
                    'source': 'open-meteo',
                    'confidence': 0.99,
                  },
                ],
              }),
        200,
        headers: jsonHeaders,
      );
    }
    if (path.endsWith('/sources')) {
      return http.Response(jsonEncode(sourcesResponseJson()), 200,
          headers: jsonHeaders);
    }
    if (path.endsWith('/locations/reverse')) {
      return http.Response(jsonEncode(reverseResponseJson()), 200,
          headers: jsonHeaders);
    }
    if (path.endsWith('/alerts')) {
      if (failWeather) {
        return http.Response(
          jsonEncode({
            'detail': {'message': 'Provider unavailable (test failure).'}
          }),
          503,
          headers: jsonHeaders,
        );
      }
      return http.Response(
        jsonEncode(alertsResponseJson(empty: noAlerts)),
        200,
        headers: jsonHeaders,
      );
    }
    if (path.endsWith('/weather/current')) {
      if (failWeather) {
        return http.Response(
          jsonEncode({
            'detail': {'message': 'Provider unavailable (test failure).'}
          }),
          503,
          headers: jsonHeaders,
        );
      }
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
    if (path.endsWith('/weather/forecast')) {
      if (failWeather) {
        return http.Response(
          jsonEncode({
            'detail': {'message': 'Provider unavailable (test failure).'}
          }),
          503,
          headers: jsonHeaders,
        );
      }
      return http.Response(
        jsonEncode({
          'forecast': [
            forecastDayJson(date: '2026-09-07'),
            forecastDayJson(date: '2026-09-08', tmax: 31, tmin: 24, rain: null),
          ],
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