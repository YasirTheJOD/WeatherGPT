import '../core/api/api_client.dart';
import '../models/location.dart';

/// Client for `/api/v1/locations/*` — search (with ambiguity flag) and
/// reverse geocoding. Used by the shared location bar (weather, map, chat).
class LocationsService {
  LocationsService({ApiClient? api}) : _api = api ?? ApiClient();

  final ApiClient _api;

  /// Forward search — `GET /locations/search?q=...`.
  /// `ambiguous: true` in the result means the UI should ask the user to pick.
  Future<ResolveResult> search(String query, {int limit = 8}) async {
    final json = await _api.getJson('/locations/search', query: {
      'q': query,
      'limit': '$limit',
    });
    return ResolveResult.fromJson(json);
  }

  /// Reverse geocode a coordinate — `GET /locations/reverse?lat&lon`.
  /// Returns null when the backend has no known place near the point (404).
  Future<LocationCandidate?> reverse(double latitude, double longitude) async {
    try {
      final json = await _api.getJson('/locations/reverse', query: {
        'lat': latitude.toString(),
        'lon': longitude.toString(),
      });
      return LocationCandidate.fromJson(json);
    } on ApiException catch (e) {
      if (e.statusCode == 404) return null;
      rethrow;
    }
  }
}