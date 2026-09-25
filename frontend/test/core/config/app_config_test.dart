import 'package:flutter_test/flutter_test.dart';
import 'package:weathergpt/core/config/app_config.dart';

/// The web build is deployed on **one origin**: the backend serves the PWA and
/// `/api` together, and `--dart-define=API_BASE_URL=` (empty) tells the app to
/// call whatever origin served the page. Get this wrong and the deployed bundle
/// silently points at `localhost:8000` — a live URL that answers only inside the
/// machine that built it.
void main() {
  group('AppConfig.resolveApiBaseUrl', () {
    test('an explicit URL always wins', () {
      expect(
        AppConfig.resolveApiBaseUrl('https://api.example.com'),
        'https://api.example.com',
      );
      expect(
        AppConfig.resolveApiBaseUrl('  https://api.example.com  '),
        'https://api.example.com',
      );
    });

    test('an empty define means the page origin on the web', () {
      expect(
        AppConfig.resolveApiBaseUrl('', isWeb: true, origin: 'https://demo.trycloudflare.com'),
        'https://demo.trycloudflare.com',
      );
    });

    test('an empty define falls back to the dev server off the web', () {
      expect(AppConfig.resolveApiBaseUrl('', isWeb: false), AppConfig.devApiBaseUrl);
    });

    test('a file:// page cannot inherit an origin, so it keeps the dev default', () {
      expect(
        AppConfig.resolveApiBaseUrl('', isWeb: true, origin: 'null'),
        AppConfig.devApiBaseUrl,
      );
      expect(
        AppConfig.resolveApiBaseUrl('', isWeb: true, origin: ''),
        AppConfig.devApiBaseUrl,
      );
    });
  });
}
