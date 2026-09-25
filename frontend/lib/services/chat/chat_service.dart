import '../../models/alert.dart';
import '../../models/location.dart';
import '../../models/weather.dart';

/// What a user is asking about. Detected by the service (Phase 4: a small
/// client-side router; Phase 5: the backend's query understanding).
enum ChatIntent { currentWeather, forecast, alerts, unknown }

/// One assistant reply: a grounded text answer plus the structured cards the
/// UI renders beneath it (weather observation, forecast strip, official
/// alerts) and any follow-up affordances.
///
/// The chat UI is intentionally dumb — it renders whatever the service
/// returns. Swapping the implementation (typed endpoints today, `/chat` SSE in
/// Phase 5) never touches the UI.
class ChatReply {
  const ChatReply({
    required this.text,
    this.intent = ChatIntent.unknown,
    this.observation,
    this.forecast = const [],
    this.alerts = const [],
    this.location,
    this.candidates = const [],
    this.suggestions = const [],
    this.sourceName,
  });

  final String text;

  /// The intent this reply answers (used when the user picks a clarification
  /// candidate so the follow-up answers the same question).
  final ChatIntent intent;

  final WeatherObservation? observation;
  final List<ForecastDay> forecast;
  final List<Alert> alerts;

  /// The location the answer is about — the UI stores it in AppState so all
  /// tabs follow.
  final SelectedLocation? location;

  /// Disambiguation options when the place name was ambiguous.
  final List<LocationCandidate> candidates;

  /// Follow-up question chips offered below the reply.
  final List<String> suggestions;

  /// Source attribution for the reply (e.g. "Open-Meteo", "SACHET").
  final String? sourceName;
}

/// One step of a streaming answer.
///
/// [ChatDelta] carries partial answer text as it arrives; [ChatDone] carries
/// the finished [ChatReply] — cards, location, suggestions and all — and is
/// always the last event on the stream.
sealed class ChatStreamEvent {
  const ChatStreamEvent();
}

/// Partial answer text. Render it into a growing draft bubble; it will be
/// replaced by the [ChatDone] reply when the answer is complete.
class ChatDelta extends ChatStreamEvent {
  const ChatDelta(this.text);

  final String text;
}

/// The completed reply. Replaces whatever draft the deltas built.
class ChatDone extends ChatStreamEvent {
  const ChatDone(this.reply);

  final ChatReply reply;
}

/// The swappable conversational interface.
///
/// Implementations:
///  * [TypedEndpointChatService] — Phase 4: routes simple queries to the
///    existing typed endpoints (works end-to-end today).
///  * `/chat` SSE adapter — Phase 5: real backend query understanding +
///    orchestrator + LLM, streamed.
abstract class ChatService {
  Future<ChatReply> ask(String message, {SelectedLocation? currentLocation});

  /// Streaming variant of [ask]: emits [ChatDelta]s while the answer is being
  /// written, then exactly one [ChatDone].
  ///
  /// The default implementation delegates to [ask] and emits a single
  /// [ChatDone], so a service that cannot stream still drives the progressive
  /// chat UI correctly — it simply never shows a draft.
  Stream<ChatStreamEvent> stream(
    String message, {
    SelectedLocation? currentLocation,
  }) async* {
    yield ChatDone(await ask(message, currentLocation: currentLocation));
  }

  /// Answer for an already-resolved location (used when the user picks one of
  /// the clarification candidates), keeping the same intent.
  Future<ChatReply> answerForLocation(
    ChatIntent intent,
    LocationCandidate candidate,
  );
}