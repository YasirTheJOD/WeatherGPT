import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

import 'package:weathergpt/core/api/api_client.dart';
import 'package:weathergpt/features/weather/weather_screen.dart';
import 'package:weathergpt/l10n/app_localizations.dart';
import 'package:weathergpt/models/location.dart';
import 'package:weathergpt/services/locations_service.dart';
import 'package:weathergpt/services/weather_service.dart';
import 'package:weathergpt/state/app_state.dart';

import '../helpers/mock_backend.dart';

Widget buildHarness(AppState state, TestBackend backend) {
  final api = ApiClient(client: backend.client);
  return ChangeNotifierProvider.value(
    value: state,
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
        body: WeatherScreen(
          weatherService: WeatherService(api: api),
          locationsService: LocationsService(api: api),
        ),
      ),
    ),
  );
}

void main() {
  testWidgets('shows the empty state before a location is chosen',
      (tester) async {
    await tester.pumpWidget(buildHarness(AppState(), TestBackend()));

    expect(find.text('Where are you looking?'), findsOneWidget);
    expect(find.text('Kolkata'), findsOneWidget); // quick-pick chip
    expect(find.text('Mumbai'), findsOneWidget);
  });

  testWidgets('search → pick → renders conditions, forecast and source',
      (tester) async {
    await tester.pumpWidget(buildHarness(AppState(), TestBackend()));

    await tester.enterText(find.byType(TextField), 'kolkata');
    await tester.pump(const Duration(milliseconds: 400)); // debounce + search
    await tester.pump();

    final resultTile = find.widgetWithText(ListTile, 'Kolkata');
    expect(resultTile, findsOneWidget);

    await tester.tap(resultTile);
    await tester.pump(); // start fetch
    await tester.pump(const Duration(milliseconds: 100)); // resolve futures

    // Current conditions — only fields the source provided.
    expect(find.text('29°C'), findsOneWidget);
    expect(find.text('78%'), findsOneWidget);
    expect(find.text('13 km/h S'), findsOneWidget);
    expect(find.text('1008 hPa'), findsOneWidget);
    expect(find.text('2.3 mm'), findsOneWidget);

    // Forecast strip.
    expect(find.text('7-day forecast'), findsOneWidget);
    expect(find.text('32° / 25°'), findsOneWidget);
    expect(find.text('🌧 4.5 mm'), findsOneWidget);

    // Source transparency.
    expect(find.text('Open-Meteo'), findsWidgets);
    expect(find.textContaining('As of'), findsWidgets);
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
    await tester.pump(); // post-frame auto-load
    await tester.pump(const Duration(milliseconds: 100));

    expect(find.text('Provider unavailable (test failure).'), findsOneWidget);
    expect(find.text('Retry'), findsOneWidget);

    // Backend recovers; retry should render data.
    backend.failWeather = false;
    await tester.tap(find.text('Retry'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    expect(find.text('29°C'), findsOneWidget);
    expect(find.text('Provider unavailable (test failure).'), findsNothing);
  });
}