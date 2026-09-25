import 'dart:async';

import 'package:flutter/material.dart';

import '../../l10n/app_localizations.dart';
import '../../models/location.dart';
import '../../services/geolocation_service.dart';
import '../../services/locations_service.dart';

/// Shared location picker used by the weather (and later map/alerts) screens.
///
/// Two ways to set a location:
///  * search — debounced forward geocoding via `/locations/search`, with the
///    backend's `ambiguous` flag driving a "pick one" list;
///  * my location — browser GPS via [GeolocationService], reverse-geocoded so
///    the user sees a place name instead of raw coordinates.
///
/// Emits a [SelectedLocation] through [onPicked]; the caller owns where it
/// goes (AppState today).
class LocationBar extends StatefulWidget {
  const LocationBar({
    super.key,
    required this.onPicked,
    this.locationsService,
    this.geolocationService,
  });

  final ValueChanged<SelectedLocation> onPicked;
  final LocationsService? locationsService;
  final GeolocationService? geolocationService;

  @override
  State<LocationBar> createState() => _LocationBarState();
}

class _LocationBarState extends State<LocationBar> {
  late final LocationsService _locations =
      widget.locationsService ?? LocationsService();
  late final GeolocationService _geo =
      widget.geolocationService ?? GeolocationService();

  final TextEditingController _controller = TextEditingController();
  Timer? _debounce;
  List<LocationCandidate> _results = const [];
  bool _searching = false;
  bool _locating = false;
  String? _error;

  @override
  void dispose() {
    _debounce?.cancel();
    _controller.dispose();
    super.dispose();
  }

  void _onQueryChanged(String query) {
    _debounce?.cancel();
    if (query.trim().length < 2) {
      setState(() {
        _results = const [];
        _searching = false;
        _error = null;
      });
      return;
    }
    setState(() => _searching = true);
    _debounce = Timer(const Duration(milliseconds: 350), () async {
      try {
        final result = await _locations.search(query.trim());
        if (!mounted) return;
        setState(() {
          _results = result.candidates;
          _searching = false;
          _error = result.candidates.isEmpty ? _noResults : null;
        });
      } on Exception {
        if (!mounted) return;
        setState(() {
          _results = const [];
          _searching = false;
          _error = _searchFailed;
        });
      }
    });
  }

  String get _noResults =>
      AppLocalizations.of(context).noPlacesFound;

  String get _searchFailed =>
      AppLocalizations.of(context).searchFailed;

  Future<void> _useMyLocation() async {
    setState(() {
      _locating = true;
      _error = null;
    });
    try {
      final position = await _geo.currentPosition();
      final reverse = await _locations.reverse(position.lat, position.lon);
      if (!mounted) return;
      final selected = reverse != null
          ? SelectedLocation.fromCandidate(reverse)
          : SelectedLocation.fromLatLng(
              latitude: position.lat,
              longitude: position.lon,
            );
      _controller.text = selected.name;
      setState(() => _results = const []);
      widget.onPicked(selected);
    } on Exception {
      if (!mounted) return;
      setState(() => _error = AppLocalizations.of(context).locationUnavailable);
    } finally {
      if (mounted) setState(() => _locating = false);
    }
  }

  void _pick(LocationCandidate candidate) {
    _controller.text = candidate.name;
    setState(() => _results = const []);
    widget.onPicked(SelectedLocation.fromCandidate(candidate));
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final l10n = AppLocalizations.of(context);

    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
          child: Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _controller,
                  onChanged: _onQueryChanged,
                  textInputAction: TextInputAction.search,
                  decoration: InputDecoration(
                    hintText: l10n.weatherSearchHint,
                    prefixIcon: const Icon(Icons.search),
                    suffixIcon: _searching
                        ? const Padding(
                            padding: EdgeInsets.all(14),
                            child: SizedBox(
                              width: 16,
                              height: 16,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            ),
                          )
                        : null,
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(28),
                    ),
                    isDense: true,
                  ),
                ),
              ),
              const SizedBox(width: 8),
              IconButton.filledTonal(
                onPressed: _locating ? null : _useMyLocation,
                tooltip: l10n.useMyLocation,
                icon: _locating
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.my_location),
              ),
            ],
          ),
        ),
        if (_error != null)
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
            child: Row(
              children: [
                Icon(Icons.info_outline,
                    size: 16, color: theme.colorScheme.error),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    _error!,
                    style: theme.textTheme.bodySmall
                        ?.copyWith(color: theme.colorScheme.error),
                  ),
                ),
              ],
            ),
          ),
        if (_results.isNotEmpty)
          Card(
            margin: const EdgeInsets.fromLTRB(16, 8, 16, 0),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                for (final candidate in _results)
                  ListTile(
                    dense: true,
                    leading: const Icon(Icons.location_city_outlined, size: 20),
                    title: Text(candidate.name),
                    subtitle: candidate.state != null
                        ? Text(
                            [candidate.state, candidate.country]
                                .whereType<String>()
                                .join(', '),
                          )
                        : null,
                    trailing: candidate.confidence > 0
                        ? Text(
                            '${(candidate.confidence * 100).round()}%',
                            style: theme.textTheme.bodySmall,
                          )
                        : null,
                    onTap: () => _pick(candidate),
                  ),
              ],
            ),
          ),
      ],
    );
  }
}