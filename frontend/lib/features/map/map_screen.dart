import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'package:provider/provider.dart';

import '../../core/api/api_client.dart';
import '../../core/widgets/source_status.dart';
import '../../l10n/app_localizations.dart';
import '../../models/location.dart';
import '../../services/alerts_service.dart';
import '../../services/locations_service.dart';
import '../../state/app_state.dart';
import '../location/location_bar.dart';
import '../location/quick_picks.dart';
import 'map_layers.dart';

/// Map tab (Phase 4 Step 4).
///
/// OSM tiles (keyless), a pin on the selected location, and the *actual*
/// official CAP geometry (circles/polygons from SACHET alert areas) drawn
/// with severity colors — the spatial story for the demo.
///
/// Follows the shared AppState.location: pick a city in any tab and the map
/// centres on it and loads that area's alert footprints.
class MapScreen extends StatefulWidget {
  const MapScreen({super.key, this.alertsService, this.locationsService});

  final AlertsService? alertsService;
  final LocationsService? locationsService;

  @override
  State<MapScreen> createState() => _MapScreenState();
}

class _MapScreenState extends State<MapScreen> {
  final MapController _mapController = MapController();
  late final AlertsService _alerts = widget.alertsService ?? AlertsService();
  late final LocationsService _locations =
      widget.locationsService ?? LocationsService();

  NearbyAlertsResult? _alertsResult;
  SelectedLocation? _loadedFor;
  bool _loadingAlerts = false;
  String? _alertsError;
  bool _mapReady = false;

  @override
  Widget build(BuildContext context) {
    final appState = context.watch<AppState>();
    final location = appState.location;

    if (location != null && location != _loadedFor && !_loadingAlerts) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _onLocationChanged(location));
    }

    return Column(
      children: [
        LocationBar(
          locationsService: _locations,
          onPicked: (selected) {
            appState.setLocation(selected);
            _onLocationChanged(selected);
          },
        ),
        // The map's own sources: OSM tiles and the SACHET alert footprints.
        const SourceStatusStrip(sourceIds: ['openstreetmap', 'sachet']),
        Expanded(
          child: location == null
              ? _EmptyMapState(locations: _locations)
              : Stack(
                  children: [
                    FlutterMap(
                      mapController: _mapController,
                      options: MapOptions(
                        initialCenter: LatLng(
                          location.latitude,
                          location.longitude,
                        ),
                        initialZoom: 10,
                        onMapReady: () {
                          _mapReady = true;
                          _centerOn(location);
                        },
                      ),
                      children: [
                        TileLayer(
                          urlTemplate:
                              'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                          userAgentPackageName: 'weathergpt',
                        ),
                        MarkerLayer(
                          markers: [
                            buildLocationMarker(
                              location,
                              Theme.of(context).colorScheme.primary,
                            ),
                          ],
                        ),
                        if (_alertsResult != null &&
                            _alertsResult!.alerts.isNotEmpty) ...[
                          CircleLayer(
                            circles: buildAlertCircles(_alertsResult!.alerts),
                          ),
                          PolygonLayer(
                            polygons:
                                buildAlertPolygons(_alertsResult!.alerts),
                          ),
                        ],
                      ],
                    ),
                    if (_loadingAlerts)
                      const Positioned(
                        top: 0,
                        left: 0,
                        right: 0,
                        child: LinearProgressIndicator(),
                      ),
                    if (_alertsError != null)
                      Positioned(
                        top: 8,
                        left: 16,
                        right: 16,
                        child: _AlertsErrorBanner(
                          message: _alertsError!,
                          onRetry: () => _loadAlerts(location),
                        ),
                      ),
                  ],
                ),
        ),
      ],
    );
  }

  void _onLocationChanged(SelectedLocation location) {
    if (_mapReady) _centerOn(location);
    _loadAlerts(location);
  }

  void _centerOn(SelectedLocation location) {
    _mapController.move(
      LatLng(location.latitude, location.longitude),
      10,
    );
  }

  Future<void> _loadAlerts(SelectedLocation location) async {
    setState(() {
      _loadingAlerts = true;
      _alertsError = null;
    });
    _loadedFor = location;
    try {
      final result = await _alerts.nearby(location);
      if (!mounted) return;
      setState(() {
        _alertsResult = result;
        _loadingAlerts = false;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _alertsError = e.message;
        _loadingAlerts = false;
      });
    } on Exception catch (e) {
      if (!mounted) return;
      setState(() {
        _alertsError = e.toString();
        _loadingAlerts = false;
      });
    }
  }
}

class _EmptyMapState extends StatelessWidget {
  const _EmptyMapState({required this.locations});

  final LocationsService locations;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final l10n = AppLocalizations.of(context);
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.map_outlined, size: 56, color: theme.colorScheme.primary),
            const SizedBox(height: 16),
            Text(
              l10n.mapEmptyTitle,
              style: theme.textTheme.titleMedium
                  ?.copyWith(fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 8),
            Text(
              l10n.mapEmptyBody,
              textAlign: TextAlign.center,
              style: theme.textTheme.bodyMedium,
            ),
            const SizedBox(height: 24),
            QuickPicks(
              locations: locations,
              onPicked: context.read<AppState>().setLocation,
            ),
          ],
        ),
      ),
    );
  }
}

class _AlertsErrorBanner extends StatelessWidget {
  const _AlertsErrorBanner({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final l10n = AppLocalizations.of(context);
    return Material(
      elevation: 3,
      borderRadius: BorderRadius.circular(8),
      color: theme.colorScheme.errorContainer,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        child: Row(
          children: [
            Icon(Icons.cloud_off_outlined,
                size: 18, color: theme.colorScheme.onErrorContainer),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                message,
                style: theme.textTheme.bodySmall
                    ?.copyWith(color: theme.colorScheme.onErrorContainer),
              ),
            ),
            TextButton(onPressed: onRetry, child: Text(l10n.retry)),
          ],
        ),
      ),
    );
  }
}