import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:weathergpt/app.dart';
import 'package:weathergpt/core/api/api_client.dart';
import 'package:weathergpt/core/widgets/source_status.dart';
import 'package:weathergpt/services/sources_service.dart';
import 'package:weathergpt/state/app_state.dart';

void main() {
  testWidgets('shell renders the four nav destinations', (tester) async {
    await tester.pumpWidget(const WeatherGptApp());

    expect(find.byType(NavigationBar), findsOneWidget);
    expect(find.text('Chat'), findsOneWidget);
    expect(find.text('Weather'), findsOneWidget);
    expect(find.text('Alerts'), findsOneWidget);
    expect(find.text('Map'), findsOneWidget);
  });

  testWidgets('switching tabs swaps the visible placeholder', (tester) async {
    await tester.pumpWidget(const WeatherGptApp());

    // Chat tab is default.
    expect(find.text('Ask WeatherGPT'), findsOneWidget);

    await tester.tap(find.text('Weather'));
    await tester.pumpAndSettle();
    expect(find.text('Where are you looking?'), findsOneWidget);

    await tester.tap(find.text('Alerts'));
    await tester.pumpAndSettle();
    expect(find.textContaining('Select a location to see official warnings'),
        findsOneWidget);

    await tester.tap(find.text('Map'));
    await tester.pumpAndSettle();
    expect(find.text('Explore the map'), findsOneWidget);
  });

  testWidgets('Hindi locale renders Hindi nav labels', (tester) async {
    await tester.pumpWidget(WeatherGptApp(state: AppStateTestHelper.hindi()));

    expect(find.text('चैट'), findsOneWidget);
    expect(find.text('मौसम'), findsOneWidget);
    expect(find.text('चेतावनी'), findsOneWidget);
    expect(find.text('नक्शा'), findsOneWidget);
  });

  testWidgets('language selector switches the app to Hindi and back to English',
      (tester) async {
    await tester.pumpWidget(const WeatherGptApp());
    expect(find.text('Chat'), findsOneWidget);

    // Open the selector and pick हिन्दी.
    await tester.tap(find.byIcon(Icons.language));
    await tester.pumpAndSettle();
    await tester.tap(find.text('हिन्दी'));
    await tester.pumpAndSettle();

    expect(find.text('चैट'), findsOneWidget);
    expect(find.text('मौसम'), findsOneWidget);
    expect(find.text('Chat'), findsNothing);

    // Switch back to English.
    await tester.tap(find.byIcon(Icons.language));
    await tester.pumpAndSettle();
    await tester.tap(find.text('English'));
    await tester.pumpAndSettle();

    expect(find.text('Chat'), findsOneWidget);
  });

  testWidgets('Hinglish keeps the English UI (chat-mode flag for Phase 5)',
      (tester) async {
    await tester.pumpWidget(const WeatherGptApp());

    await tester.tap(find.byIcon(Icons.language));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Hinglish'));
    await tester.pumpAndSettle();

    expect(find.text('Chat'), findsOneWidget);
    expect(find.text('Weather'), findsOneWidget);
    expect(find.text('WeatherGPT'), findsOneWidget); // app bar title
  });

  // `const WeatherGptApp()` in the tests above uses the real registry client.
  // In `flutter test` every HTTP call fails (the binding stubs the socket), so
  // these two double as the drawer's built-in-list / error-banner coverage.
  testWidgets('sources drawer lists the data providers', (tester) async {
    await tester.pumpWidget(const WeatherGptApp());

    await tester.tap(find.byIcon(Icons.menu)); // hamburger (locale-independent)
    await tester.pumpAndSettle();

    expect(find.text('Data sources'), findsOneWidget);
    expect(find.text('Open-Meteo'), findsOneWidget);
    expect(find.text('SACHET · NDMA'), findsOneWidget);
    expect(find.text('Official source'), findsOneWidget); // badge on SACHET

    // The remaining tiles sit below the fold of the small test viewport — the
    // error banner (registry unreachable in tests) adds height — so scroll.
    final drawerList = find.descendant(
      of: find.byType(Drawer),
      matching: find.byType(Scrollable),
    );
    await tester.scrollUntilVisible(
      find.text('BigDataCloud'),
      80,
      scrollable: drawerList,
    );
    expect(find.text('BigDataCloud'), findsOneWidget);

    await tester.scrollUntilVisible(
      find.text('OpenStreetMap'),
      80,
      scrollable: drawerList,
    );
    expect(find.text('OpenStreetMap'), findsOneWidget);
  });

  testWidgets('sources drawer localizes to Hindi', (tester) async {
    await tester.pumpWidget(WeatherGptApp(state: AppStateTestHelper.hindi()));

    await tester.tap(find.byIcon(Icons.menu)); // hamburger (locale-independent)
    await tester.pumpAndSettle();

    expect(find.text('डेटा स्रोत'), findsOneWidget);
    expect(find.text('लाइव मौसम अवलोकन और 7-दिन का पूर्वानुमान'), findsOneWidget);
  });

  testWidgets('sources drawer renders the live registry with availability',
      (tester) async {
    await tester.pumpWidget(WeatherGptApp(sourcesService: _liveSourcesService()));

    await tester.tap(find.byIcon(Icons.menu));
    await tester.pumpAndSettle();

    // The summary chip proves the panel is reading GET /api/v1/sources.
    expect(find.text('2 of 3 available'), findsOneWidget);

    // Live names, not the built-in labels.
    expect(find.text('IMD — India Meteorological Department'), findsOneWidget);
    expect(find.text('SACHET · NDMA'), findsNothing);

    // Curated status vs live availability are both surfaced.
    expect(find.text('Requires authorization'), findsOneWidget);
    expect(find.text('IMD_API_KEY not set — using the Open-Meteo fallback'),
        findsOneWidget);

    await tester.scrollUntilVisible(
      find.text('Open-Meteo (GFS-derived)'),
      80,
      scrollable: find.descendant(
        of: find.byType(Drawer),
        matching: find.byType(Scrollable),
      ),
    );
    expect(find.text('Open-Meteo (GFS-derived)'), findsOneWidget);

    // No error banner when the registry answered.
    expect(find.textContaining('Showing the built-in list'), findsNothing);
  });

  testWidgets('alerts tab shows the live status of its warning sources',
      (tester) async {
    await tester.pumpWidget(WeatherGptApp(sourcesService: _liveSourcesService()));

    await tester.tap(find.text('Alerts'));
    await tester.pumpAndSettle();

    final strip = find.byType(SourceStatusStrip);
    expect(strip, findsOneWidget);
    // SACHET is up, IMD is still awaiting its key — the curator's status and the
    // live availability are both visible without opening the drawer.
    expect(find.descendant(of: strip, matching: find.text('SACHET · NDMA')),
        findsOneWidget);
    expect(find.descendant(of: strip, matching: find.text('IMD')),
        findsOneWidget);
    expect(
      find.descendant(of: strip, matching: find.text('Available')),
      findsOneWidget,
    );
    expect(
      find.descendant(of: strip, matching: find.text('Requires authorization')),
      findsOneWidget,
    );
  });

  testWidgets('map tab shows the live status of its map sources',
      (tester) async {
    await tester.pumpWidget(WeatherGptApp(sourcesService: _liveSourcesService()));

    await tester.tap(find.text('Map'));
    await tester.pumpAndSettle();

    final strip = find.byType(SourceStatusStrip);
    expect(strip, findsOneWidget);
    expect(
      find.descendant(of: strip, matching: find.text('OpenStreetMap')),
      findsOneWidget,
    );
    expect(find.descendant(of: strip, matching: find.text('SACHET · NDMA')),
        findsOneWidget);
    // Both map sources are available in this payload.
    expect(find.descendant(of: strip, matching: find.text('Available')),
        findsWidgets);
  });

  testWidgets('tab strips share one registry fetch with the drawer',
      (tester) async {
    var calls = 0;
    final service = _sourcesService((_) async {
      calls += 1;
      return _jsonResponse(_liveRegistryPayload());
    });

    await tester.pumpWidget(WeatherGptApp(sourcesService: service));
    await tester.pumpAndSettle();

    // Switching tabs must not re-fetch: the controller is shared.
    await tester.tap(find.text('Alerts'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Map'));
    await tester.pumpAndSettle();

    expect(calls, 1);
  });

  testWidgets('sources drawer shows an error state and recovers on retry',
      (tester) async {
    await tester.pumpWidget(
      WeatherGptApp(sourcesService: _flakySourcesService()),
    );

    await tester.tap(find.byIcon(Icons.menu));
    await tester.pumpAndSettle();

    // Explicit error state: the notice plus a retry action, with the built-in
    // list still shown underneath rather than replaced by a blank screen.
    expect(find.textContaining('Showing the built-in list'), findsOneWidget);
    expect(find.text('Retry'), findsOneWidget);
    expect(find.text('Open-Meteo'), findsOneWidget);
    expect(find.text('2 of 3 available'), findsNothing);

    await tester.tap(find.text('Retry'));
    await tester.pumpAndSettle();

    // Recovered: the live registry replaces the fallback and the banner is gone.
    expect(find.text('2 of 3 available'), findsOneWidget);
    expect(find.text('IMD — India Meteorological Department'), findsOneWidget);
    expect(find.textContaining('Showing the built-in list'), findsNothing);
  });
}

/// A [SourcesService] whose transport is scripted by [handler]. The payloads
/// have the same shape the backend returns, so the drawer's parsing path is
/// exercised too.
SourcesService _sourcesService(
  Future<http.Response> Function(http.Request request) handler,
) =>
    SourcesService(
      api: ApiClient(client: MockClient(handler), baseUrl: 'http://test'),
    );

http.Response _jsonResponse(Object body) => http.Response(
      jsonEncode(body),
      200,
      headers: {'content-type': 'application/json'},
    );

Map<String, dynamic> _registrySource(
  String id,
  String name, {
  bool official = false,
  bool available = true,
  String status = 'implemented',
  String? availableMessage,
}) =>
    {
      'source_id': id,
      'name': name,
      'role': 'Primary role from the backend',
      'status': status,
      'official': official,
      'auth': 'None (keyless)',
      'url': 'https://example.test',
      'evidence_url': null,
      'available': available,
      'available_message': availableMessage,
      'notes': null,
    };

/// The registry payload the success paths serve: IMD still needs authorization,
/// hence "2 of 3 available".
Map<String, dynamic> _liveRegistryPayload() => {
      'generated_at': '2026-09-19T00:00:00Z',
      'counts': {'total': 3, 'available': 2, 'official': 2},
      'sources': [
        _registrySource(
          'imd',
          'IMD — India Meteorological Department',
          official: true,
          available: false,
          status: 'requires_authorization',
          availableMessage:
              'IMD_API_KEY not set — using the Open-Meteo fallback',
        ),
        _registrySource('open_meteo', 'Open-Meteo (GFS-derived)'),
        _registrySource('sachet', 'SACHET — NDMA', official: true),
      ],
    };

SourcesService _liveSourcesService() =>
    _sourcesService((_) async => _jsonResponse(_liveRegistryPayload()));

/// Fails the first request, then succeeds — the "registry unreachable, retry"
/// drill.
SourcesService _flakySourcesService() {
  var calls = 0;
  return _sourcesService((_) async {
    calls += 1;
    if (calls == 1) {
      return http.Response(
        jsonEncode({
          'detail': {'message': 'Registry unavailable (test).'}
        }),
        503,
        headers: {'content-type': 'application/json'},
      );
    }
    return _jsonResponse(_liveRegistryPayload());
  });
}

/// Test seam: build an AppState with Hindi preselected.
class AppStateTestHelper {
  static AppState hindi() {
    final state = AppState();
    state.setLanguage(AppLanguage.hindi);
    return state;
  }
}
