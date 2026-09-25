import 'package:intl/intl.dart';

import '../../core/api/api_client.dart';
import '../../models/location.dart';
import '../alerts_service.dart';
import '../locations_service.dart';
import '../weather_service.dart';
import 'chat_service.dart';

/// Phase 4 ChatService implementation.
///
/// A deliberately small, honest router: it recognises a handful of demo
/// query shapes ("weather in X", "will it rain tomorrow in X", "alerts in X",
/// some Hinglish) and answers by calling the *real* typed endpoints, so every
/// number in the reply is grounded in fetched data with provenance.
///
/// Phase 5 replaces this with the backend `/chat` (query understanding +
/// orchestrator + LLM) behind the same [ChatService] interface — the UI and
/// this class's contract do not change.
///
/// Extends [ChatService] rather than implementing it, so it inherits the
/// non-streaming default [ChatService.stream]: the typed endpoints answer in
/// one shot, and a single [ChatDone] is the honest representation of that.
class TypedEndpointChatService extends ChatService {
  TypedEndpointChatService({
    ApiClient? api,
    LocationsService? locations,
    WeatherService? weather,
    AlertsService? alerts,
  })  : _locations = locations ?? LocationsService(api: api),
        _weather = weather ?? WeatherService(api: api),
        _alerts = alerts ?? AlertsService(api: api);

  final LocationsService _locations;
  final WeatherService _weather;
  final AlertsService _alerts;

  static const _stopWords = {
    // English
    'what', 'whats', 'is', 'the', 'in', 'at', 'current', 'weather', 'today',
    'now', 'forecast', 'tomorrow', 'will', 'it', 'rain', 'raining', 'rains',
    'alerts', 'alert', 'warning', 'warnings', 'for', 'near', 'me', 'my',
    'area', 'please', 'show', 'give', 'tell', 'about', 'and', 'of', 'here',
    'right', 'currently', 'exactly',
    // Contraction stems (apostrophes are folded away before matching).
    'its', 'thats', 'dont', 'cant', 'wont', 'isnt', 'arent', 'heres', 'theres',
    // Hinglish
    'kya', 'hai', 'kal', 'shaam', 'subah', 'baarish', 'barish', 'mausam',
    'ka', 'ki', 'ke', 'mein', 'hoga', 'hogi', 'ho', 'rahegi', 'rahega',
    'aaj', 'abhi', 'ko', 'se',
    // Romanized question words (never part of a place name)
    'kaisa', 'kaisi', 'kaise', 'kahan', 'kahaan', 'kab', 'kitna', 'kitni',
    'bata', 'batao', 'bataiye', 'degree', 'degrees',
    // Devanagari (mirrors the backend parser's vocabulary)
    'क्या', 'है', 'कल', 'शाम', 'सुबह', 'बारिश', 'मौसम', 'का', 'की', 'के',
    'में', 'होगा', 'होगी', 'हो', 'रहेगी', 'रहेगा', 'आज', 'अभी', 'को', 'से',
    'चेतावनी', 'सुरक्षा', 'रात', 'दोपहर',
    'कैसा', 'कैसी', 'कैसे', 'कहाँ', 'कहां', 'कब', 'कितना', 'कितनी',
    'बताओ', 'बताइए',
  };

  @override
  Future<ChatReply> ask(
    String message, {
    SelectedLocation? currentLocation,
  }) async {
    try {
      final lower = message.toLowerCase();
      final intent = _detectIntent(lower);
      final usesCurrentLocation = _hasAny(
          lower, ['my area', 'near me', 'here', 'yahan', 'यहाँ', 'मेरे आसपास']);

      SelectedLocation? resolved;
      var candidates = const <LocationCandidate>[];

      String? placeQuery;
      if (!usesCurrentLocation) {
        placeQuery = _extractPlace(lower);
      }

      if (placeQuery != null) {
        final search = await _locations.search(placeQuery, limit: 5);
        if (search.candidates.isEmpty) {
          return ChatReply(
            text: 'I couldn\'t find a place called "$placeQuery". '
                'Try a different spelling or pick a starter question below.',
            suggestions: _starterSuggestions(),
          );
        }
        if (search.ambiguous || _closeConfidence(search.candidates)) {
          candidates = search.candidates;
          return ChatReply(
            text: 'I found several places named "${search.normalized}". '
                'Which one do you mean?',
            intent: intent,
            candidates: candidates,
          );
        }
        resolved = SelectedLocation.fromCandidate(search.candidates.first);
      } else if (currentLocation != null && usesCurrentLocation) {
        resolved = currentLocation;
      } else if (currentLocation != null) {
        resolved = currentLocation;
      } else {
        return ChatReply(
          text: 'Which place are you asking about? Try "weather in Kolkata" '
              'or pick a starter question below.',
          suggestions: _starterSuggestions(),
        );
      }

      return await _answer(intent, resolved);
    } on ApiException catch (e) {
      return ChatReply(
        text: 'I couldn\'t reach the weather service right now '
            '(${e.message}). Please try again in a moment.',
      );
    } on Exception catch (e) {
      return ChatReply(text: 'Sorry — something went wrong ($e).');
    }
  }

  @override
  Future<ChatReply> answerForLocation(
    ChatIntent intent,
    LocationCandidate candidate,
  ) async {
    try {
      return await _answer(intent, SelectedLocation.fromCandidate(candidate));
    } on ApiException catch (e) {
      return ChatReply(
        text: 'I couldn\'t reach the weather service right now '
            '(${e.message}). Please try again in a moment.',
      );
    } on Exception catch (e) {
      return ChatReply(text: 'Sorry — something went wrong ($e).');
    }
  }

  // -------------------------------------------------------------------------
  // Intent + location routing
  // -------------------------------------------------------------------------

  ChatIntent _detectIntent(String lower) {
    if (_hasAny(lower, [
      'alert', 'warning', 'चेतावनी', 'should i do', 'what to do', 'kya karun',
    ])) {
      return ChatIntent.alerts;
    }
    if (_hasAny(lower, [
      'forecast', 'tomorrow', 'kal', 'कल', 'predict', 'baarish', 'barish',
      'rain', 'बारिश',
    ])) {
      return ChatIntent.forecast;
    }
    return ChatIntent.currentWeather;
  }

  /// Keep only the words that look like a place name.
  ///
  /// Mirrors the backend cleaner: Devanagari is preserved (stripping it
  /// silently turned every Hindi query into "ask me for a place"), and
  /// apostrophes are removed rather than replaced by a space so "what's"
  /// folds to "whats" (a stop word) instead of leaving a stray "s" in the
  /// place name.
  String? _extractPlace(String lower) {
    final normalized = lower.replaceAll(RegExp("['\u2019\u02bc\u0060]"), '');
    final cleaned =
        normalized.replaceAll(RegExp(r'[^a-z0-9\u0900-\u097F\s]'), ' ');
    final words = cleaned
        .split(RegExp(r'\s+'))
        .where((w) => w.isNotEmpty && !_stopWords.contains(w));
    final place = words.join(' ').trim();
    return place.isEmpty ? null : place;
  }

  static bool _closeConfidence(List<LocationCandidate> candidates) {
    if (candidates.length < 2) return false;
    final top = candidates[0].confidence;
    return candidates.any((c) => top - c.confidence < 0.08);
  }

  static bool _hasAny(String text, List<String> needles) =>
      needles.any(text.contains);

  // -------------------------------------------------------------------------
  // Grounded reply builders (data comes from the real endpoints)
  // -------------------------------------------------------------------------

  Future<ChatReply> _answer(ChatIntent intent, SelectedLocation location) {
    switch (intent) {
      case ChatIntent.alerts:
        return _buildAlertsReply(location);
      case ChatIntent.forecast:
        return _buildForecastReply(location);
      case ChatIntent.currentWeather:
      case ChatIntent.unknown:
        return _buildWeatherReply(location);
    }
  }

  Future<ChatReply> _buildWeatherReply(SelectedLocation location) async {
    final result = await _weather.current(location);
    final o = result.observation;

    final headline = <String>[
      if (o.temperatureC != null) '${o.temperatureC!.round()}°C',
      if (o.conditionText != null) o.conditionText!,
    ];
    final details = <String>[
      if (o.humidityPct != null) 'humidity ${o.humidityPct!.round()}%',
      if (o.windSpeedKmph != null)
        'wind ${o.windSpeedKmph!.round()} km/h'
            '${o.windDirection != null ? ' ${o.windDirection}' : ''}',
      if (o.pressureHpa != null) 'pressure ${o.pressureHpa!.round()} hPa',
      if (o.rainfall24hMm != null) 'rain ${o.rainfall24hMm} mm (24h)',
    ];

    final name = o.locationName ?? location.name;
    final text = headline.isEmpty
        ? 'I don\'t have live observations for $name right now.'
        : 'Right now in $name: ${headline.join(', ')}'
            '${details.isNotEmpty ? ' — ${details.join(', ')}' : ''}.';

    return ChatReply(
      text: text,
      intent: ChatIntent.currentWeather,
      observation: o,
      location: location,
      sourceName: o.provenance.sourceName,
      suggestions: const [
        'Will it rain tomorrow?',
        'Any alerts nearby?',
        '7-day forecast',
      ],
    );
  }

  Future<ChatReply> _buildForecastReply(SelectedLocation location) async {
    final result = await _weather.forecast(location);
    final days = result.days;
    if (days.isEmpty) {
      return ChatReply(
        text: 'No forecast data is available for ${location.name} right now.',
        intent: ChatIntent.forecast,
        location: location,
      );
    }

    final target = days.length > 1 ? days[1] : days.first;
    final when = days.length > 1
        ? 'Tomorrow (${DateFormat('EEE d MMM').format(target.dateTime)})'
        : 'Today';
    final bits = <String>[
      if (target.tmaxC != null) 'high ${target.tmaxC!.round()}°',
      if (target.tminC != null) 'low ${target.tminC!.round()}°',
      if (target.rainfallMm != null) 'rain ${target.rainfallMm} mm',
      if (target.conditionText != null) target.conditionText!,
    ];

    final text = bits.isEmpty
        ? 'No forecast detail is available for ${location.name} $when.'
        : 'In ${location.name} on $when: ${bits.join(', ')}.';

    return ChatReply(
      text: text,
      intent: ChatIntent.forecast,
      forecast: days,
      location: location,
      sourceName: days.first.provenance.sourceName,
      suggestions: const ['What about the 7-day forecast?', 'Alerts nearby'],
    );
  }

  Future<ChatReply> _buildAlertsReply(SelectedLocation location) async {
    final result = await _alerts.nearby(location);
    final alerts = result.alerts;
    if (alerts.isEmpty) {
      return ChatReply(
        text: 'No official warnings near ${location.name} right now. '
            'I\'ll keep checking the official feed.',
        intent: ChatIntent.alerts,
        location: location,
        suggestions: const ['What\'s the weather?', '7-day forecast'],
      );
    }

    final top = alerts.first;
    final text = alerts.length == 1
        ? 'There is an official warning for ${location.name}: '
            '${top.event} (${top.severity}). '
            'Follow the instructions in the official warning below.'
        : 'There are ${alerts.length} official warnings for ${location.name}. '
            'The most severe: ${top.event} (${top.severity}). '
            'Follow the instructions in the official warnings below.';

    return ChatReply(
      text: text,
      intent: ChatIntent.alerts,
      alerts: alerts,
      location: location,
      sourceName: result.source,
      suggestions: const ['What should I do?', 'What\'s the weather?'],
    );
  }

  static List<String> _starterSuggestions() => const [
        "What's the weather in Kolkata?",
        'Will it rain tomorrow in Mumbai?',
        'Alerts near me',
        'Kal shaam Mumbai mein baarish hogi kya?',
      ];
}