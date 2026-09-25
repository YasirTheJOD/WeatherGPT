import 'speech_service.dart';

/// Non-web platforms (VM tests, mobile builds): voice is a web-only feature
/// in the prototype, so the factory returns the graceful no-op.
SpeechService createSpeechService() => const UnsupportedSpeechService();