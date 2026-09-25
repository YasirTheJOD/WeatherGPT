import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

import 'package:weathergpt/core/api/api_client.dart';
import 'package:weathergpt/features/chat/chat_screen.dart';
import 'package:weathergpt/l10n/app_localizations.dart';
import 'package:weathergpt/models/location.dart';
import 'package:weathergpt/models/weather.dart';
import 'package:weathergpt/services/chat/chat_service.dart';
import 'package:weathergpt/services/chat/typed_endpoint_chat_service.dart';
import 'package:weathergpt/services/speech/speech_service.dart';
import 'package:weathergpt/state/app_state.dart';

import '../helpers/mock_backend.dart';

/// Injectable fake so the mic flow is testable without a browser.
class FakeSpeechService implements SpeechService {
  FakeSpeechService({this.transcript = '', this.isSupported = true});

  final String transcript;
  @override
  final bool isSupported;
  final List<String> spoken = [];
  int listenCalls = 0;

  @override
  Future<String> listen({required String lang}) async {
    listenCalls++;
    // A real speech service captures audio for a while. Model that with a
    // fake-async timer so the "Listening…" state is observable between
    // pumps instead of being skipped over in the same microtask cascade.
    await Future<void>.delayed(const Duration(milliseconds: 50));
    if (transcript.isEmpty) {
      throw const SpeechUnavailableException('No speech was heard.');
    }
    return transcript;
  }

  @override
  void speak(String text, {required String lang}) => spoken.add(text);

  @override
  void stop() {}
}

/// A chat service whose answer the test pushes frame by frame, so the UI can
/// be inspected mid-answer — something the buffered services can never expose.
class ManualStreamChatService extends ChatService {
  final _events = StreamController<ChatStreamEvent>();

  void delta(String text) => _events.add(ChatDelta(text));
  void done(ChatReply reply) => _events.add(ChatDone(reply));
  Future<void> dispose() => _events.close();

  @override
  Stream<ChatStreamEvent> stream(
    String message, {
    SelectedLocation? currentLocation,
  }) =>
      _events.stream;

  @override
  Future<ChatReply> ask(String message, {SelectedLocation? currentLocation}) =>
      throw UnimplementedError('the screen goes through stream()');

  @override
  Future<ChatReply> answerForLocation(
    ChatIntent intent,
    LocationCandidate candidate,
  ) =>
      throw UnimplementedError('not part of this harness');
}

Widget buildHarness(
  AppState state,
  TestBackend backend, {
  SpeechService? speech,
  ChatService? chatService,
}) {
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
        body: ChatScreen(
          chatService: chatService ??
              TypedEndpointChatService(api: ApiClient(client: backend.client)),
          speechService: speech,
        ),
      ),
    ),
  );
}

Future<void> sendMessage(WidgetTester tester, String text) async {
  await tester.enterText(find.byType(TextField), text);
  await tester.tap(find.byIcon(Icons.send));
  await tester.pump(); // user message added, request starts
  await tester.pump(const Duration(milliseconds: 100)); // reply futures
}

void main() {
  testWidgets('shows starter prompts when the chat is empty', (tester) async {
    await tester.pumpWidget(buildHarness(AppState(), TestBackend()));

    expect(find.text('Ask WeatherGPT'), findsOneWidget);
    expect(find.text("What's the weather in Kolkata?"), findsOneWidget);
    expect(find.text('Kal shaam Mumbai mein baarish hogi kya?'), findsOneWidget);
  });

  testWidgets('weather query → grounded reply, weather card, location chip',
      (tester) async {
    await tester.pumpWidget(buildHarness(AppState(), TestBackend()));

    await sendMessage(tester, 'weather in Kolkata');

    expect(find.text('weather in Kolkata'), findsOneWidget); // user bubble
    expect(find.textContaining('Right now in Kolkata'), findsOneWidget);
    expect(find.text('29°C'), findsOneWidget); // CurrentConditionsCard
    expect(find.widgetWithText(InputChip, 'Kolkata'), findsOneWidget); // context chip
  });

  testWidgets('forecast query → forecast strip rendered', (tester) async {
    await tester.pumpWidget(buildHarness(AppState(), TestBackend()));

    await sendMessage(tester, 'Will it rain tomorrow in Mumbai?');

    expect(find.textContaining('Tomorrow'), findsOneWidget);
    expect(find.text('7-day forecast'), findsOneWidget);
  });

  testWidgets('alerts query → OFFICIAL WARNING card rendered', (tester) async {
    await tester.pumpWidget(buildHarness(AppState(), TestBackend()));

    await sendMessage(tester, 'alerts in Kolkata');

    expect(find.text('OFFICIAL WARNING'), findsOneWidget);
    expect(find.text('Heavy Rain'), findsOneWidget);
  });

  testWidgets('ambiguous place → choices offered; picking one answers',
      (tester) async {
    final backend = TestBackend(ambiguousSearch: true);
    await tester.pumpWidget(buildHarness(AppState(), backend));

    await sendMessage(tester, 'weather in Ranipur');

    expect(find.textContaining('Which one do you mean'), findsOneWidget);
    expect(find.text('Ranipur, Uttarakhand'), findsOneWidget);
    expect(find.text('Ranipur, Uttar Pradesh'), findsOneWidget);

    await tester.tap(find.text('Ranipur, Uttarakhand'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    expect(find.text('29°C'), findsOneWidget); // grounded answer for the pick
  });

  testWidgets('provider outage → graceful error reply, not a crash',
      (tester) async {
    await tester.pumpWidget(
      buildHarness(AppState(), TestBackend(failWeather: true)),
    );

    await sendMessage(tester, 'weather in Kolkata');

    expect(find.textContaining('try again'), findsOneWidget);
    expect(find.textContaining('Right now in Kolkata'), findsNothing);
  });

  testWidgets('mic → transcript is sent and the answer is spoken back',
      (tester) async {
    final fake = FakeSpeechService(transcript: 'weather in Kolkata');
    await tester.pumpWidget(buildHarness(AppState(), TestBackend(), speech: fake));

    await tester.tap(find.byIcon(Icons.mic_none));
    await tester.pump(); // listening starts
    expect(find.text('Listening…'), findsOneWidget);

    await tester.pump(const Duration(milliseconds: 100)); // listen + reply

    expect(fake.listenCalls, 1);
    expect(find.textContaining('Right now in Kolkata'), findsOneWidget);
    expect(fake.spoken, isNotEmpty);
    expect(fake.spoken.first, contains('Right now in Kolkata'));
  });

  testWidgets('the answer is rendered as it streams, not on done',
      (tester) async {
    final chat = ManualStreamChatService();
    addTearDown(chat.dispose);
    await tester.pumpWidget(
      buildHarness(AppState(), TestBackend(), chatService: chat),
    );

    await tester.enterText(find.byType(TextField), 'weather in Kolkata');
    await tester.tap(find.byIcon(Icons.send));
    await tester.pump();

    // Nothing has been generated yet: the typing indicator is the only signal.
    expect(find.text('WeatherGPT is thinking…'), findsOneWidget);
    expect(find.textContaining('Right now in'), findsNothing);

    chat.delta('Right now in');
    await tester.pump();

    // Mid-stream: the partial answer is already on screen and the spinner has
    // given way to the caret-marked draft bubble.
    expect(find.textContaining('Right now in'), findsOneWidget);
    expect(find.textContaining('▍'), findsOneWidget);
    expect(find.text('WeatherGPT is thinking…'), findsNothing);

    chat.delta('Kolkata: 29°C, Overcast.');
    await tester.pump();
    expect(find.textContaining('Kolkata: 29°C, Overcast.'), findsOneWidget);

    // The `done` reply replaces the draft — same bubble slot, now with the
    // structured cards and the committed (caret-free) text.
    chat.done(ChatReply(
      text: 'Right now in Kolkata: 29°C, Overcast.',
      intent: ChatIntent.currentWeather,
      observation: WeatherObservation.fromJson(observationJson()),
      location: const SelectedLocation(
        name: 'Kolkata',
        latitude: 22.57,
        longitude: 88.36,
      ),
      sourceName: 'Open-Meteo',
      suggestions: const ['Will it rain tomorrow?'],
    ));
    await tester.pump(); // stream delivery
    await tester.pump(); // _send's continuation + rebuild

    expect(find.text('29°C'), findsOneWidget); // CurrentConditionsCard
    expect(find.text('Right now in Kolkata: 29°C, Overcast.'), findsOneWidget);
    expect(find.textContaining('▍'), findsNothing);
    expect(find.widgetWithText(InputChip, 'Kolkata'), findsOneWidget);
  });

  testWidgets('unsupported voice shows a hint instead of listening',
      (tester) async {
    final fake = FakeSpeechService(isSupported: false);
    await tester.pumpWidget(buildHarness(AppState(), TestBackend(), speech: fake));

    await tester.tap(find.byIcon(Icons.mic_none));
    await tester.pump();

    expect(
      find.text('Voice needs the web app in Chrome — type your question instead.'),
      findsOneWidget,
    );
    expect(fake.listenCalls, 0);
  });
}