import 'package:flutter/foundation.dart';

/// App-level configuration.
///
/// The API base URL is set at build/run time via
/// `--dart-define=API_BASE_URL=http://...` so the same codebase can point at a
/// local backend, a LAN box, or a deployed instance without edits. Defaults to
/// the local FastAPI dev server, which is in the backend CORS allowlist.
class AppConfig {
  AppConfig._();

  /// The dev default: the local FastAPI server (`flutter run` for the web dev
  /// server on :5173 talks to :8000, so the two ports are deliberately
  /// different origins).
  static const String devApiBaseUrl = 'http://localhost:8000';

  static const String _configuredApiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: devApiBaseUrl,
  );

  /// Empty `--dart-define=API_BASE_URL=` means **same origin as the page**.
  ///
  /// That is how a single-URL deployment works: the backend serves the built
  /// PWA and `/api` together (see `WEB_DIR` in the backend), so the browser
  /// makes no cross-origin request, nothing is CORS-dependent, and no API host
  /// is baked into the bundle — the same artefact works behind a tunnel, a
  /// LAN address or a real domain. Outside the browser there is no origin to
  /// inherit, so the dev default still applies.
  static String get apiBaseUrl => resolveApiBaseUrl(_configuredApiBaseUrl);

  @visibleForTesting
  static String resolveApiBaseUrl(String configured, {bool? isWeb, String? origin}) {
    final trimmed = configured.trim();
    if (trimmed.isNotEmpty) return trimmed;
    if (isWeb ?? kIsWeb) {
      // `file://` pages have the origin `null`, and a relative base URL would
      // fail in the HTTP client — fall back to the dev default, which is at
      // least a real, diagnosable URL.
      final pageOrigin = origin ?? Uri.base.origin;
      if (pageOrigin.isEmpty || pageOrigin == 'null') return devApiBaseUrl;
      return pageOrigin;
    }
    return devApiBaseUrl;
  }

  static const String apiPrefix = '/api/v1';

  /// Full API root, e.g. `http://localhost:8000/api/v1` — or `/api/v1`, a
  /// relative path, in the same-origin deployment.
  static String get apiRoot => '$apiBaseUrl$apiPrefix';

  static const Duration requestTimeout = Duration(seconds: 15);
}
