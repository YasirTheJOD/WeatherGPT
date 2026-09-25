import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:weathergpt/core/api/api_client.dart';
import 'package:weathergpt/features/location/quick_picks.dart';
import 'package:weathergpt/l10n/app_localizations.dart';
import 'package:weathergpt/models/location.dart';
import 'package:weathergpt/services/locations_service.dart';

/// Records every search query so a test can prove what the chips actually send
/// over the wire — the visible label and the query must not be assumed equal.
class _RecordingBackend {
  final List<String> queries = [];

  late final MockClient client = MockClient((request) async {
    final q = request.url.queryParameters['q']!;
    queries.add(q);
    final name = q[0].toUpperCase() + q.substring(1);
    return http.Response(
      jsonEncode({
        'query': q,
        'normalized': q,
        'ambiguous': false,
        'candidates': [
          {
            'name': name,
            'state': 'West Bengal',
            'country': 'India',
            'country_code': 'IN',
            'latitude': 22.57,
            'longitude': 88.36,
            'source': 'open-meteo',
            'confidence': 0.99,
          },
        ],
      }),
      200,
      headers: {'content-type': 'application/json'},
    );
  });
}

Widget buildHarness({
  required Locale locale,
  required LocationsService service,
  required ValueChanged<SelectedLocation> onPicked,
}) =>
    MaterialApp(
      locale: locale,
      supportedLocales: AppLocalizations.supportedLocales,
      localizationsDelegates: const [
        AppLocalizations.delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      home: Scaffold(
        body: QuickPicks(locations: service, onPicked: onPicked),
      ),
    );

void main() {
  testWidgets('English chips show the Latin city names', (tester) async {
    final backend = _RecordingBackend();
    final service = LocationsService(api: ApiClient(client: backend.client));

    await tester.pumpWidget(buildHarness(
      locale: const Locale('en'),
      service: service,
      onPicked: (_) {},
    ));

    expect(find.text('Try:'), findsOneWidget);
    for (final city in ['Kolkata', 'Mumbai', 'Delhi', 'Bengaluru']) {
      expect(find.widgetWithText(ActionChip, city), findsOneWidget);
    }
  });

  testWidgets('Hindi chips show the Devanagari city names', (tester) async {
    final backend = _RecordingBackend();
    final service = LocationsService(api: ApiClient(client: backend.client));

    await tester.pumpWidget(buildHarness(
      locale: const Locale('hi'),
      service: service,
      onPicked: (_) {},
    ));

    expect(find.text('कोशिश करें:'), findsOneWidget);
    for (final city in ['कोलकाता', 'मुंबई', 'दिल्ली', 'बेंगलुरु']) {
      expect(find.widgetWithText(ActionChip, city), findsOneWidget);
    }
    // No Latin leftovers in the localized UI.
    expect(find.widgetWithText(ActionChip, 'Kolkata'), findsNothing);
  });

  testWidgets('a localized chip still searches the canonical Latin name',
      (tester) async {
    final backend = _RecordingBackend();
    final service = LocationsService(api: ApiClient(client: backend.client));
    SelectedLocation? picked;

    await tester.pumpWidget(buildHarness(
      locale: const Locale('hi'),
      service: service,
      onPicked: (location) => picked = location,
    ));

    await tester.tap(find.widgetWithText(ActionChip, 'कोलकाता'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    // The chip is labelled in Devanagari but the geocoder is Latin-only.
    expect(backend.queries, ['Kolkata']);
    expect(picked?.name, 'Kolkata');
  });
}
