import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/api/api_client.dart';
import '../../core/widgets/error_state.dart';
import '../../core/widgets/source_card.dart';
import '../../l10n/app_localizations.dart';
import '../../models/location.dart';
import '../../services/locations_service.dart';
import '../../services/weather_service.dart';
import '../../state/app_state.dart';
import '../location/location_bar.dart';
import '../location/quick_picks.dart';
import 'widgets/current_conditions_card.dart';
import 'widgets/forecast_strip.dart';

/// Weather tab (Phase 4 Step 2).
///
/// Location bar on top (search + GPS), then:
///  * empty state — until a location is chosen (with quick picks for the demo);
///  * loading / error states (retry never dies mid-demo);
///  * current-conditions card, validation warnings, 7-day forecast strip and
///    source cards once data arrives.
///
/// Re-fetches automatically whenever AppState.location changes (e.g. when
/// chat sets a location in Step 5), so every tab agrees on one place.
class WeatherScreen extends StatefulWidget {
  const WeatherScreen({super.key, this.weatherService, this.locationsService});

  final WeatherService? weatherService;
  final LocationsService? locationsService;

  @override
  State<WeatherScreen> createState() => _WeatherScreenState();
}

class _WeatherScreenState extends State<WeatherScreen> {
  late final WeatherService _weather =
      widget.weatherService ?? WeatherService();
  late final LocationsService _locations =
      widget.locationsService ?? LocationsService();

  CurrentWeatherResult? _current;
  ForecastResult? _forecast;
  SelectedLocation? _loadedFor;
  bool _loading = false;
  String? _error;

  @override
  Widget build(BuildContext context) {
    final appState = context.watch<AppState>();
    final location = appState.location;

    // Pick up a location set elsewhere (initial load, chat, map) and fetch.
    if (location != null && location != _loadedFor && !_loading) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _load(location));
    }

    return Column(
      children: [
        LocationBar(
          locationsService: _locations,
          onPicked: (selected) {
            appState.setLocation(selected);
            _load(selected);
          },
        ),
        Expanded(child: _buildBody(location)),
      ],
    );
  }

  Widget _buildBody(SelectedLocation? location) {
    if (location == null) return _EmptyState(locations: _locations);
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_error != null) {
      return ErrorState(
        message: _error!,
        onRetry: () => _load(location),
      );
    }
    return _buildContent();
  }

  Widget _buildContent() {
    final l10n = AppLocalizations.of(context);
    final current = _current;
    final forecast = _forecast;

    final warningIssues = [
      ...?current?.validation?.issues.where((i) => i.isWarning),
      ...?forecast?.validation?.issues.where((i) => i.isWarning),
    ];

    return ListView(
      padding: const EdgeInsets.only(bottom: 24),
      children: [
        if (current != null) ...[
          CurrentConditionsCard(observation: current.observation),
          if (warningIssues.isNotEmpty)
            _WarningsBanner(
              messages: warningIssues.map((i) => i.message).toList(),
            ),
        ],
        if (forecast != null && forecast.days.isNotEmpty) ...[
          ForecastStrip(
            days: forecast.days,
            localeCode: Localizations.localeOf(context).languageCode,
          ),
        ],
        if (current != null) ...[
          const SizedBox(height: 8),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
            child: Text(
              '${l10n.sourceHeader} · ${current.providerUsed}',
              style: Theme.of(context).textTheme.titleSmall?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
            ),
          ),
          SourceCard(provenance: current.observation.provenance),
        ],
        if (forecast != null && forecast.days.isNotEmpty)
          SourceCard(provenance: forecast.days.first.provenance),
      ],
    );
  }

  Future<void> _load(SelectedLocation location) async {
    setState(() {
      _loading = true;
      _error = null;
    });
    _loadedFor = location;
    try {
      final (current, forecast) =
          await (_weather.current(location), _weather.forecast(location)).wait;
      if (!mounted) return;
      setState(() {
        _current = current;
        _forecast = forecast;
        _loading = false;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.message;
        _loading = false;
      });
    } on ParallelWaitError catch (e) {
      // The record .wait throws ParallelWaitError (an Error, not Exception)
      // when any of the parallel fetches fail. Surface the first failure.
      if (!mounted) return;
      setState(() {
        _error = _firstFailureMessage(e.errors.$1) ??
            _firstFailureMessage(e.errors.$2) ??
            'Weather data unavailable.';
        _loading = false;
      });
    } on Exception catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  static String? _firstFailureMessage(AsyncError? error) {
    if (error == null) return null;
    final inner = error.error;
    if (inner is ApiException) return inner.message;
    return inner.toString();
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState({required this.locations});

  final LocationsService locations;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final l10n = AppLocalizations.of(context);
    final appState = context.watch<AppState>();

    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.location_searching,
                size: 56, color: theme.colorScheme.primary),
            const SizedBox(height: 16),
            Text(
              l10n.weatherEmptyTitle,
              style: theme.textTheme.titleMedium
                  ?.copyWith(fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 8),
            Text(
              l10n.weatherEmptyBody,
              textAlign: TextAlign.center,
              style: theme.textTheme.bodyMedium,
            ),
            const SizedBox(height: 24),
            QuickPicks(
              locations: locations,
              onPicked: appState.setLocation,
            ),
          ],
        ),
      ),
    );
  }
}

class _WarningsBanner extends StatelessWidget {
  const _WarningsBanner({required this.messages});

  final List<String> messages;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: theme.colorScheme.tertiaryContainer,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(Icons.warning_amber_outlined,
              size: 18, color: theme.colorScheme.onTertiaryContainer),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                for (final message in messages)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 1),
                    child: Text(
                      message,
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: theme.colorScheme.onTertiaryContainer,
                      ),
                    ),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}