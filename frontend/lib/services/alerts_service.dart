import '../core/api/api_client.dart';
import '../models/alert.dart';
import '../models/location.dart';

/// One `/alerts` response: official CAP alerts near a point plus the feed
/// source. Alerts are authoritative government data — passed through as-is.
class NearbyAlertsResult {
  const NearbyAlertsResult({required this.alerts, required this.source});

  final List<Alert> alerts;
  final String source;
}

/// Client for `/api/v1/alerts` — official warnings from the SACHET/NDMA CAP
/// feed, selected by the backend for the given coordinates and radius.
class AlertsService {
  AlertsService({ApiClient? api}) : _api = api ?? ApiClient();

  final ApiClient _api;

  Future<NearbyAlertsResult> nearby(
    SelectedLocation location, {
    int radiusKm = 20,
  }) async {
    final json = await _api.getJson('/alerts', query: {
      'lat': location.latitude.toString(),
      'lon': location.longitude.toString(),
      'radius_km': '$radiusKm',
    });
    return NearbyAlertsResult(
      alerts: json['alerts'] is List
          ? (json['alerts'] as List)
              .whereType<Map<String, dynamic>>()
              .map(Alert.fromJson)
              .toList()
          : const [],
      source: json['source'] as String? ?? 'unknown',
    );
  }
}