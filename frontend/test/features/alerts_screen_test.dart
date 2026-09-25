import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

import 'package:weathergpt/core/api/api_client.dart';
import 'package:weathergpt/features/alerts/alerts_screen.dart';
import 'package:weathergpt/l10n/app_localizations.dart';
import 'package:weathergpt/models/location.dart';
import 'package:weathergpt/services/alerts_service.dart';
import 'package:weathergpt/services/locations_service.dart';
import 'package:weathergpt/services/sources_service.dart';
import 'package:weathergpt/state/app_state.dart';
import 'package:weathergpt/state/sources_controller.dart';

import '../helpers/mock_backend.dart';

Widget buildHarness(AppState state, TestBackend backend) {
  final api = ApiClient(client: backend.client);
  return MultiProvider(
    providers: [
      ChangeNotifierProvider.value(value: state),
      // The screen surfaces the live source registry (its source-status strip).
      ChangeNotifierProvider(
        create: (_) => SourcesController(service: SourcesService(api: api)),
      ),
    ],
    child: MaterialApp(
      locale: state.locale,
      supportedLocales: AppLocalizations.supportedLocales,
      localizationsDelegates: const [
        AppLocalizations.delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      home: Scaffold(
        body: AlertsScreen(
          alertsService: AlertsService(api: api),
          locationsService: LocationsService(api: api),
        ),
      ),
    ),
  );
}

void main() {
  testWidgets('prompts for a location before any location is chosen',
      (tester) async {
    await tester.pumpWidget(buildHarness(AppState(), TestBackend()));

    expect(find.text('Select a location to see official warnings for that area.'),
        findsOneWidget);
    expect(find.text('Kolkata'), findsOneWidget); // quick-pick chip
  });

  testWidgets('search → pick → renders the official warning card',
      (tester) async {
    await tester.pumpWidget(buildHarness(AppState(), TestBackend()));

    await tester.enterText(find.byType(TextField), 'kolkata');
    await tester.pump(const Duration(milliseconds: 400)); // debounce + search
    await tester.pump();

    await tester.tap(find.widgetWithText(ListTile, 'Kolkata'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    expect(find.text('OFFICIAL WARNING'), findsOneWidget);
    expect(find.text('Heavy Rain'), findsOneWidget);
    expect(find.text('Severe'), findsOneWidget);
    expect(find.text('Heavy rain expected over the next 24 hours.'),
        findsOneWidget);
    expect(find.textContaining('What to do'), findsOneWidget);
    expect(find.textContaining('Avoid waterlogged'), findsOneWidget);
    expect(find.textContaining('Kolkata, Howrah'), findsOneWidget);
    expect(find.text('SACHET'), findsOneWidget);
    expect(find.textContaining('Issued '), findsOneWidget);
    expect(find.textContaining('Expires '), findsOneWidget);
  });

  testWidgets('shows a clear message when no alerts are near the location',
      (tester) async {
    final backend = TestBackend(noAlerts: true);
    final state = AppState()
      ..setLocation(const SelectedLocation(
        name: 'Kolkata',
        latitude: 22.57,
        longitude: 88.36,
      ));

    await tester.pumpWidget(buildHarness(state, backend));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    expect(find.text('No official warnings near this location right now.'),
        findsOneWidget);
    expect(find.text('OFFICIAL WARNING'), findsNothing);
  });

  testWidgets('failed fetch shows the backend message, retry recovers',
      (tester) async {
    final backend = TestBackend(failWeather: true);
    final state = AppState()
      ..setLocation(const SelectedLocation(
        name: 'Kolkata',
        latitude: 22.57,
        longitude: 88.36,
      ));

    await tester.pumpWidget(buildHarness(state, backend));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    expect(find.text('Provider unavailable (test failure).'), findsOneWidget);

    backend.failWeather = false;
    await tester.tap(find.text('Retry'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    expect(find.text('OFFICIAL WARNING'), findsOneWidget);
  });
}