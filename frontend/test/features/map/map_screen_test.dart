import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

import 'package:weathergpt/core/api/api_client.dart';
import 'package:weathergpt/features/map/map_screen.dart';
import 'package:weathergpt/l10n/app_localizations.dart';
import 'package:weathergpt/models/location.dart';
import 'package:weathergpt/services/alerts_service.dart';
import 'package:weathergpt/services/locations_service.dart';
import 'package:weathergpt/services/sources_service.dart';
import 'package:weathergpt/state/app_state.dart';
import 'package:weathergpt/state/sources_controller.dart';

import '../../helpers/mock_backend.dart';

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
        body: MapScreen(
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

    expect(find.text('Explore the map'), findsOneWidget);
    expect(find.text('Kolkata'), findsOneWidget); // quick-pick chip
  });

  testWidgets('renders the map with a pin once a location is set',
      (tester) async {
    final state = AppState()
      ..setLocation(const SelectedLocation(
        name: 'Kolkata',
        latitude: 22.57,
        longitude: 88.36,
      ));

    await tester.pumpWidget(buildHarness(state, TestBackend()));
    await tester.pump(); // post-frame alerts load
    await tester.pump(const Duration(milliseconds: 100));

    expect(find.byType(FlutterMap), findsOneWidget);
    expect(find.byIcon(Icons.location_on), findsWidgets);
  });

  testWidgets('shows the alerts error banner and retries', (tester) async {
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

    expect(find.text('Provider unavailable (test failure).'), findsNothing);
    expect(find.byType(FlutterMap), findsOneWidget);
  });
}