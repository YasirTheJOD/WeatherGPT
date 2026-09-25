// ignore: unused_import
import 'package:intl/intl.dart' as intl;

import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for English (`en`).
class AppLocalizationsEn extends AppLocalizations {
  AppLocalizationsEn([String locale = 'en']) : super(locale);

  @override
  String get appTitle => 'WeatherGPT';

  @override
  String get appTagline =>
      'Conversational weather intelligence — SIH 2026 prototype';

  @override
  String get navChat => 'Chat';

  @override
  String get navWeather => 'Weather';

  @override
  String get navMap => 'Map';

  @override
  String get navAlerts => 'Alerts';

  @override
  String get tabChat => 'Chat';

  @override
  String get tabWeather => 'Weather';

  @override
  String get tabMap => 'Map';

  @override
  String get weatherSearchHint => 'Search for a city…';

  @override
  String get useMyLocation => 'Use my location';

  @override
  String get noPlacesFound => 'No places found.';

  @override
  String get searchFailed => 'Search failed. Please try again.';

  @override
  String get locationUnavailable =>
      'Could not get your location (permission denied or unavailable).';

  @override
  String get weatherEmptyTitle => 'Where are you looking?';

  @override
  String get weatherEmptyBody =>
      'Search for a city or use your current location to see live conditions and the 7-day forecast.';

  @override
  String get quickPicks => 'Try:';

  @override
  String get quickPickKolkata => 'Kolkata';

  @override
  String get quickPickMumbai => 'Mumbai';

  @override
  String get quickPickDelhi => 'Delhi';

  @override
  String get quickPickBengaluru => 'Bengaluru';

  @override
  String get retry => 'Retry';

  @override
  String get humidity => 'Humidity';

  @override
  String get wind => 'Wind';

  @override
  String get pressure => 'Pressure';

  @override
  String get rainfall24h => 'Rain (24h)';

  @override
  String get rainfallNext24h => 'Rain (next 24h)';

  @override
  String get rainfallNow => 'Rain (now)';

  @override
  String get rainfallGeneric => 'Rain';

  @override
  String get observedAt => 'Observed at';

  @override
  String get forecastHeader => '7-day forecast';

  @override
  String get today => 'Today';

  @override
  String asOfTime(Object time) {
    return 'As of $time';
  }

  @override
  String get officialSource => 'Official source';

  @override
  String get sourceHeader => 'Source';

  @override
  String get selectLocationForAlerts =>
      'Select a location to see official warnings for that area.';

  @override
  String get noAlertsNearby =>
      'No official warnings near this location right now.';

  @override
  String get alertsHeader => 'Official warnings';

  @override
  String get officialWarning => 'OFFICIAL WARNING';

  @override
  String get whatToDo => 'What to do';

  @override
  String get affectedAreas => 'Affected areas';

  @override
  String issuedAt(Object time) {
    return 'Issued $time';
  }

  @override
  String expiresAt(Object time) {
    return 'Expires $time';
  }

  @override
  String get severityMinor => 'Minor';

  @override
  String get severityModerate => 'Moderate';

  @override
  String get severitySevere => 'Severe';

  @override
  String get severityExtreme => 'Extreme';

  @override
  String get mapEmptyTitle => 'Explore the map';

  @override
  String get mapEmptyBody =>
      'Pick a location to see it pinned on the map, along with any official warning areas.';

  @override
  String get mapAlertsFailed => 'Couldn\'t load alert areas.';

  @override
  String get chatHint => 'Ask about weather, forecasts or alerts…';

  @override
  String get chatWelcomeTitle => 'Ask WeatherGPT';

  @override
  String get chatWelcomeBody =>
      'Ask in English or Hinglish — answers are grounded in official weather data.';

  @override
  String get typing => 'WeatherGPT is thinking…';

  @override
  String get send => 'Send';

  @override
  String get listening => 'Listening…';

  @override
  String get voiceUnsupported =>
      'Voice needs the web app in Chrome — type your question instead.';

  @override
  String get micTooltip => 'Voice input';

  @override
  String get stopListeningTooltip => 'Stop listening';

  @override
  String get language => 'Language';

  @override
  String get sourcesTitle => 'Data sources';

  @override
  String get sourcesIntro =>
      'Every answer shows who provided the data, when it was fetched, and whether it is an official source.';

  @override
  String get sourceOpenMeteo => 'Live observations & 7-day forecast';

  @override
  String get sourceSachet => 'Official government warnings (CAP feed)';

  @override
  String get sourceBigDataCloud =>
      'Reverse geocoding for your current location';

  @override
  String get sourceOpenStreetMap => 'Map tiles';

  @override
  String get sourcesLive => 'Live registry';

  @override
  String sourcesSummary(Object available, Object total) {
    return '$available of $total available';
  }

  @override
  String get sourcesFallbackNotice =>
      'Showing the built-in list — the live registry is unreachable.';

  @override
  String get sourcesRegistryUnreachable => 'Source registry unreachable.';

  @override
  String get sourceAvailable => 'Available';

  @override
  String get sourceUnavailable => 'Unavailable';

  @override
  String get sourceRequiresAuth => 'Requires authorization';

  @override
  String get sourcePlanned => 'Planned';

  @override
  String get sourceImd =>
      'Official observations, forecasts and district warnings';

  @override
  String get sourceGeocoding => 'Geocoding for city search';

  @override
  String get sourceLlm => 'Explains the data in plain language';

  @override
  String get sourceMosdac => 'Satellite imagery (future scope)';

  @override
  String get sourceGfs => 'Raw model output for future map layers';
}
