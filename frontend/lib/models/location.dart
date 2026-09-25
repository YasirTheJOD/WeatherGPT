// Location models mirroring backend/app/domain/models.py.

/// Mirrors `LocationCandidate` — one resolved place with a confidence score.
class LocationCandidate {
  const LocationCandidate({
    required this.name,
    this.state,
    this.country,
    this.countryCode,
    required this.latitude,
    required this.longitude,
    required this.source,
    this.confidence = 0.5,
  });

  final String name;
  final String? state;
  final String? country;
  final String? countryCode;
  final double latitude;
  final double longitude;
  final String source; // "aliases" | "open-meteo" | "bigdatacloud"
  final double confidence;

  factory LocationCandidate.fromJson(Map<String, dynamic> json) =>
      LocationCandidate(
        name: json['name'] as String? ?? '',
        state: json['state'] as String?,
        country: json['country'] as String?,
        countryCode: json['country_code'] as String?,
        latitude: (json['latitude'] as num?)?.toDouble() ?? 0,
        longitude: (json['longitude'] as num?)?.toDouble() ?? 0,
        source: json['source'] as String? ?? 'unknown',
        confidence: (json['confidence'] as num?)?.toDouble() ?? 0.5,
      );
}

/// Mirrors `ResolveResult` — search outcome incl. the ambiguity flag that
/// drives the "which one did you mean?" clarifying question in chat.
class ResolveResult {
  const ResolveResult({
    required this.query,
    required this.normalized,
    this.candidates = const [],
    this.ambiguous = false,
  });

  final String query;
  final String normalized;
  final List<LocationCandidate> candidates;
  final bool ambiguous;

  factory ResolveResult.fromJson(Map<String, dynamic> json) => ResolveResult(
        query: json['query'] as String? ?? '',
        normalized: json['normalized'] as String? ?? '',
        candidates: json['candidates'] is List
            ? (json['candidates'] as List)
                .whereType<Map<String, dynamic>>()
                .map(LocationCandidate.fromJson)
                .toList()
            : const [],
        ambiguous: json['ambiguous'] as bool? ?? false,
      );
}

/// Mirrors `Station` — an IMD station for nearest-station lookups.
class Station {
  const Station({
    required this.stationCode,
    required this.name,
    this.state,
    required this.latitude,
    required this.longitude,
  });

  final String stationCode;
  final String name;
  final String? state;
  final double latitude;
  final double longitude;

  factory Station.fromJson(Map<String, dynamic> json) => Station(
        stationCode: json['station_code'] as String? ?? '',
        name: json['name'] as String? ?? '',
        state: json['state'] as String?,
        latitude: (json['latitude'] as num?)?.toDouble() ?? 0,
        longitude: (json['longitude'] as num?)?.toDouble() ?? 0,
      );
}

/// The user's currently selected location — the shared anchor for weather,
/// alerts, map and chat. Produced by picking a `LocationCandidate`.
class SelectedLocation {
  const SelectedLocation({
    required this.name,
    required this.latitude,
    required this.longitude,
    this.state,
    this.source,
    this.confidence,
  });

  final String name;
  final double latitude;
  final double longitude;
  final String? state;
  final String? source;
  final double? confidence;

  factory SelectedLocation.fromCandidate(LocationCandidate c) => SelectedLocation(
        name: c.name,
        latitude: c.latitude,
        longitude: c.longitude,
        state: c.state,
        source: c.source,
        confidence: c.confidence,
      );

  /// From the device's GPS fix (reverse-geocoded later).
  factory SelectedLocation.fromLatLng({
    required double latitude,
    required double longitude,
    String? name,
  }) =>
      SelectedLocation(
        name: name ?? 'My location',
        latitude: latitude,
        longitude: longitude,
        source: 'device-gps',
      );

  @override
  bool operator ==(Object other) =>
      other is SelectedLocation &&
      other.latitude == latitude &&
      other.longitude == longitude &&
      other.name == name;

  @override
  int get hashCode => Object.hash(name, latitude, longitude);
}