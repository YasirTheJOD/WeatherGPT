import 'package:flutter_test/flutter_test.dart';

import 'package:weathergpt/services/speech/speech_service.dart';

void main() {
  test('speechLangFor maps app locales to Web Speech tags', () {
    expect(speechLangFor('en'), 'en-IN');
    expect(speechLangFor('hi'), 'hi-IN');
    expect(speechLangFor('unknown'), 'en-IN'); // safe default
  });

  test('UnsupportedSpeechService reports unsupported and fails listen()', () {
    const service = UnsupportedSpeechService();

    expect(service.isSupported, isFalse);

    expect(
      () => service.listen(lang: 'en'),
      throwsA(isA<SpeechUnavailableException>()),
    );

    // TTS and stop are graceful no-ops.
    service.speak('hello', lang: 'en');
    service.stop();
  });
}