import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/api/api_client.dart';
import '../../core/widgets/error_state.dart';
import '../../core/widgets/source_status.dart';
import '../../l10n/app_localizations.dart';
import '../../models/location.dart';
import '../../services/alerts_service.dart';
import '../../services/locations_service.dart';
import '../../state/app_state.dart';
import '../location/location_bar.dart';
import '../location/quick_picks.dart';
import 'widgets/alert_card.dart';

/// Alerts tab (Phase 4 Step 3).
///
/// Official warnings from the SACHET/NDMA CAP feed for the selected location.
/// Warnings are authoritative government data: rendered as OFFICIAL WARNING
/// blocks with severity/validity/provenance, never re-labelled by the UI.
class AlertsScreen extends StatefulWidget {
  const AlertsScreen({super.key, this.alertsService, this.locationsService});

  final AlertsService? alertsService;
  final LocationsService? locationsService;

  @override
  State<AlertsScreen> createState() => _AlertsScreenState();
}

class _AlertsScreenState extends State<AlertsScreen> {
  late final AlertsService _alerts = widget.alertsService ?? AlertsService();
  late final LocationsService _locations =
      widget.locationsService ?? LocationsService();

  NearbyAlertsResult? _result;
  SelectedLocation? _loadedFor;
  bool _loading = false;
  String? _error;

  @override
  Widget build(BuildContext context) {
    final appState = context.watch<AppState>();
    final location = appState.location;

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
        // Which official warning sources back this tab, and are they up? Shown
        // even when there are no warnings — "clear" is only trustworthy if you
        // can see the feed was actually reachable.
        const SourceStatusStrip(sourceIds: ['sachet', 'imd']),
        Expanded(child: _buildBody(location)),
      ],
    );
  }

  Widget _buildBody(SelectedLocation? location) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);

    if (location == null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.warning_amber_outlined,
                  size: 56, color: theme.colorScheme.error),
              const SizedBox(height: 16),
              Text(
                l10n.selectLocationForAlerts,
                textAlign: TextAlign.center,
                style: theme.textTheme.titleMedium
                    ?.copyWith(fontWeight: FontWeight.w600),
              ),
              const SizedBox(height: 24),
              QuickPicks(
                locations: _locations,
                onPicked: context.read<AppState>().setLocation,
              ),
            ],
          ),
        ),
      );
    }
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_error != null) {
      return ErrorState(message: _error!, onRetry: () => _load(location));
    }

    final alerts = _result?.alerts ?? const [];
    if (alerts.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.verified_outlined,
                  size: 56, color: theme.colorScheme.primary),
              const SizedBox(height: 16),
              Text(
                l10n.noAlertsNearby,
                textAlign: TextAlign.center,
                style: theme.textTheme.bodyLarge,
              ),
            ],
          ),
        ),
      );
    }

    return ListView(
      padding: const EdgeInsets.only(top: 8, bottom: 24),
      children: [
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
          child: Text(
            '${l10n.alertsHeader} · ${location.name}',
            style: theme.textTheme.titleSmall
                ?.copyWith(fontWeight: FontWeight.w600),
          ),
        ),
        for (final alert in alerts) AlertCard(alert: alert),
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
      final result = await _alerts.nearby(location);
      if (!mounted) return;
      setState(() {
        _result = result;
        _loading = false;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.message;
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
}