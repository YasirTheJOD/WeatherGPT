import '../core/api/api_client.dart';
import '../models/location.dart';
import '../models/validation.dart';
import '../models/weather.dart';

/// One `/weather/current` response: the observation plus which provider served
/// it and the validation report for the data.
class CurrentWeatherResult {
  const CurrentWeatherResult({
    required this.observation,
    required this.providerUsed,
    this.validation,
  });

  final WeatherObservation observation;
  final String providerUsed;
  final ValidationReport? validation;
}

/// One `/weather/forecast` response.
class ForecastResult {
  const ForecastResult({
    required this.days,
    required this.providerUsed,
    this.validation,
  });

  final List<ForecastDay> days;
  final String providerUsed;
  final ValidationReport? validation;
}

/// Client for `/api/v1/weather/*`. The backend resolves nearest station and
/// provider fallback internally — the frontend only passes coordinates.
class WeatherService {
  WeatherService({ApiClient? api}) : _api = api ?? ApiClient();

  final ApiClient _api;

  Future<CurrentWeatherResult> current(SelectedLocation location) async {
    final json = await _api.getJson('/weather/current', query: {
      'lat': location.latitude.toString(),
      'lon': location.longitude.toString(),
    });
    return CurrentWeatherResult(
      observation: WeatherObservation.fromJson(
        json['observation'] as Map<String, dynamic>? ?? const {},
      ),
      providerUsed: json['provider_used'] as String? ?? '',
      validation: _validation(json),
    );
  }

  Future<ForecastResult> forecast(SelectedLocation location, {int days = 7}) async {
    final json = await _api.getJson('/weather/forecast', query: {
      'lat': location.latitude.toString(),
      'lon': location.longitude.toString(),
      'days': '$days',
    });
    return ForecastResult(
      days: json['forecast'] is List
          ? (json['forecast'] as List)
              .whereType<Map<String, dynamic>>()
              .map(ForecastDay.fromJson)
              .toList()
          : const [],
      providerUsed: json['provider_used'] as String? ?? '',
      validation: _validation(json),
    );
  }

  static ValidationReport? _validation(Map<String, dynamic> json) =>
      json['validation'] is Map<String, dynamic>
          ? ValidationReport.fromJson(json['validation'] as Map<String, dynamic>)
          : null;
}