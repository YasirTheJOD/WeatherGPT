import 'package:flutter/foundation.dart';

import '../models/source.dart';
import '../services/sources_service.dart';

/// Shared, cached view of `GET /api/v1/sources`.
///
/// Three places now care about the registry (the sources drawer, the alerts
/// tab and the map tab), so it is fetched **once** and shared rather than three
/// times — and a retry on any screen refreshes all of them.
///
/// Failure semantics are deliberate: an unreachable registry, or an empty one,
/// leaves [sources] null and sets [failed] so callers show an explicit error
/// state instead of pretending a source is fine. Any previously loaded data is
/// kept out of the way by callers (they render their own fallback), never
/// silently presented as fresh.
class SourcesController extends ChangeNotifier {
  SourcesController({SourcesService? service})
      : _service = service ?? SourcesService();

  final SourcesService _service;

  List<SourceInfo>? _sources;
  bool _loading = false;
  bool _failed = false;
  bool _requested = false;

  List<SourceInfo>? get sources => _sources;
  bool get loading => _loading;
  bool get failed => _failed;
  bool get hasLiveData => _sources != null;

  /// Look up one source in the registry (null when unknown or not loaded).
  SourceInfo? byId(String id) {
    for (final source in _sources ?? const <SourceInfo>[]) {
      if (source.id == id) return source;
    }
    return null;
  }

  /// Fetch the registry. The first call wins; later calls (from other
  /// consumers) are no-ops unless [force] is set — which is what the retry
  /// buttons use.
  ///
  /// Safe to call from a post-frame callback (see the widgets' `initState`):
  /// [failed] is intentionally left untouched while reloading so an error
  /// banner stays on screen with a spinner instead of flickering away.
  Future<void> load({bool force = false}) async {
    if (_loading) return;
    if (_requested && !force) return;
    _requested = true;
    _loading = true;
    notifyListeners();

    try {
      final sources = await _service.fetch();
      // An empty registry is a backend anomaly, not a healthy state.
      _sources = sources.isEmpty ? null : sources;
      _failed = sources.isEmpty;
    } on Exception {
      _sources = null;
      _failed = true;
    }

    _loading = false;
    notifyListeners();
  }

  /// Retry after a failure (used by the error banners).
  Future<void> retry() => load(force: true);
}
