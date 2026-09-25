import 'package:geolocator/geolocator.dart';

/// Failure surfaced to the UI when the device position can't be obtained
/// (permission denied, unavailable, timeout).
class GeolocationException implements Exception {
  const GeolocationException(this.message);

  final String message;

  @override
  String toString() => message;
}

/// Thin wrapper around the geolocator plugin so the browser GPS call is
/// swappable/fakeable and the UI never imports the plugin directly.
///
/// Web: uses the browser geolocation API (works on localhost/HTTPS). The
/// browser may prompt the user for permission on first use.
class GeolocationService {
  Future<({double lat, double lon})> currentPosition() async {
    try {
      final position = await Geolocator.getCurrentPosition(
        locationSettings: const LocationSettings(
          accuracy: LocationAccuracy.high,
          timeLimit: Duration(seconds: 10),
        ),
      );
      return (lat: position.latitude, lon: position.longitude);
    } catch (_) {
      throw const GeolocationException(
        'Could not access device location (permission denied or unavailable).',
      );
    }
  }
}