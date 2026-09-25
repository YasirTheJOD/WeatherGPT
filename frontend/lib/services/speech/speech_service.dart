import 'speech_service_stub.dart'
    if (dart.library.js_interop) 'speech_service_web.dart' as impl;

/// Failure surfaced when speech input/output is unavailable or fails.
class SpeechUnavailableException implements Exception {
  const SpeechUnavailableException(this.message);

  final String message;

  @override
  String toString() => message;
}

/// Swappable speech provider (STT + TTS), mirroring the project's
/// provider-replaceability rule. Phase 4 uses the browser Web Speech API
/// (zero keys, Chrome); cloud providers plug in behind the same interface.
abstract class SpeechService {
  /// Whether speech input is usable in this environment (web + Chrome).
  bool get isSupported;

  /// One-shot speech-to-text. Resolves with the transcript; throws
  /// [SpeechUnavailableException] on failure/timeout.
  Future<String> listen({required String lang});

  /// Speak [text] aloud (text-to-speech). No-op when unsupported.
  void speak(String text, {required String lang});

  /// Stop any in-flight speech output.
  void stop();
}

/// Maps the app locale code ('en'/'hi') to a Web Speech language tag
/// (region-specific variants improve recognition in Indian English/Hindi).
String speechLangFor(String localeCode) =>
    localeCode == 'hi' ? 'hi-IN' : 'en-IN';

/// Default implementation for the current platform.
SpeechService createSpeechService() => impl.createSpeechService();

/// Graceful no-op implementation for non-web platforms / unsupported browsers.
class UnsupportedSpeechService implements SpeechService {
  const UnsupportedSpeechService();

  @override
  bool get isSupported => false;

  @override
  Future<String> listen({required String lang}) async {
    throw const SpeechUnavailableException(
      'Voice is only available in the web app (Chrome).',
    );
  }

  @override
  void speak(String text, {required String lang}) {}

  @override
  void stop() {}
}