import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

/// `speech_service.dart` picks its implementation with a conditional import:
///
/// ```dart
/// import 'speech_service_stub.dart'
///     if (dart.library.js_interop) 'speech_service_web.dart' as impl;
/// ```
///
/// `flutter test` runs on the VM, so it only ever compiles the **stub**. The web
/// branch was missing the `createSpeechService()` factory entirely, which left
/// the whole suite green while `flutter build web --release` failed to compile —
/// i.e. no deployable web build existed and nothing said so. There is no way to
/// compile the web branch from a VM test, so this pins the contract the two
/// branches must share by inspecting their source.
void main() {
  test('both conditional-import branches expose the speech factory', () {
    for (final name in const [
      'speech_service_stub.dart',
      'speech_service_web.dart',
    ]) {
      final source = File('lib/services/speech/$name').readAsStringSync();
      expect(
        source.contains('SpeechService createSpeechService()'),
        isTrue,
        reason:
            'lib/services/speech/$name must define `SpeechService createSpeechService()`. '
            'The web branch is only compiled by `flutter build web`, so a missing '
            'factory breaks every deployment build while `flutter test` stays green.',
      );
    }
  });
}
