import 'provenance.dart';

/// Mirrors `backend/app/domain/models.py` — `WeatherObservation`.
///
/// All fields are nullable exactly like the backend: the UI only shows
/// parameters the connected source actually provided. `null` ≠ 0.
class WeatherObservation {
  const WeatherObservation({
    required this.latitude,
    required this.longitude,
    this.locationName,
    this.temperatureC,
    this.humidityPct,
    this.windSpeedKmph,
    this.windDirection,
    this.pressureHpa,
    this.weatherCode,
    this.conditionText,
    this.rainfall24hMm,
    this.observedAt,
    required this.provenance,
  });

  final double latitude;
  final double longitude;
  final String? locationName;
  final double? temperatureC;
  final double? humidityPct;
  final double? windSpeedKmph;
  final String? windDirection;
  final double? pressureHpa;
  final int? weatherCode;
  final String? conditionText;
  final double? rainfall24hMm;
  final DateTime? observedAt;
  final Provenance provenance;

  factory WeatherObservation.fromJson(Map<String, dynamic> json) =>
      WeatherObservation(
        latitude: (json['latitude'] as num?)?.toDouble() ?? 0,
        longitude: (json['longitude'] as num?)?.toDouble() ?? 0,
        locationName: json['location_name'] as String?,
        temperatureC: (json['temperature_c'] as num?)?.toDouble(),
        humidityPct: (json['humidity_pct'] as num?)?.toDouble(),
        windSpeedKmph: (json['wind_speed_kmph'] as num?)?.toDouble(),
        windDirection: json['wind_direction'] as String?,
        pressureHpa: (json['pressure_hpa'] as num?)?.toDouble(),
        weatherCode: json['weather_code'] as int?,
        conditionText: json['condition_text'] as String?,
        rainfall24hMm: (json['rainfall_24h_mm'] as num?)?.toDouble(),
        observedAt: json['observed_at'] is String
            ? DateTime.tryParse(json['observed_at'] as String)
            : null,
        provenance: Provenance.fromJson(
          json['provenance'] as Map<String, dynamic>? ?? const {},
        ),
      );
}

/// Mirrors `backend/app/domain/models.py` — `ForecastDay`.
class ForecastDay {
  const ForecastDay({
    required this.date,
    this.tmaxC,
    this.tminC,
    this.conditionText,
    this.rainfallMm,
    this.humidityPct,
    this.windSpeedKmph,
    required this.provenance,
  });

  final String date; // ISO yyyy-MM-dd
  final double? tmaxC;
  final double? tminC;
  final String? conditionText;
  final double? rainfallMm;
  final double? humidityPct;
  final double? windSpeedKmph;
  final Provenance provenance;

  DateTime get dateTime => DateTime.parse(date);

  factory ForecastDay.fromJson(Map<String, dynamic> json) => ForecastDay(
        date: json['date'] as String? ?? '',
        tmaxC: (json['tmax_c'] as num?)?.toDouble(),
        tminC: (json['tmin_c'] as num?)?.toDouble(),
        conditionText: json['condition_text'] as String?,
        rainfallMm: (json['rainfall_mm'] as num?)?.toDouble(),
        humidityPct: (json['humidity_pct'] as num?)?.toDouble(),
        windSpeedKmph: (json['wind_speed_kmph'] as num?)?.toDouble(),
        provenance: Provenance.fromJson(
          json['provenance'] as Map<String, dynamic>? ?? const {},
        ),
      );
}