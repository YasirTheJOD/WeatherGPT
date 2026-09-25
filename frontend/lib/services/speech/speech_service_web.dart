import 'dart:async';
import 'dart:js_interop';
import 'dart:js_interop_unsafe';

import 'package:web/web.dart' as web;

import 'speech_service.dart';

/// Web (Chrome) implementation of [SpeechService] using the browser Web
/// Speech API via package:web typed bindings:
/// `SpeechRecognition` (speech-to-text) + `speechSynthesis` (text-to-speech).
///
/// Zero external keys — the demo's voice story with no paid dependency.
/// Cloud providers replace this behind [SpeechService] later.
class WebSpeechService implements SpeechService {
  /// Speech recognition is a Chrome/Edge feature. Chrome exposes the
  /// constructor both unprefixed and as `webkitSpeechRecognition`.
  @override
  bool get isSupported {
    final global = globalContext;
    return global.has('SpeechRecognition') ||
        global.has('webkitSpeechRecognition');
  }

  @override
  Future<String> listen({required String lang}) async {
    final recognition = _createRecognition();
    if (recognition == null) {
      throw const SpeechUnavailableException(
        'Speech recognition is not available in this browser.',
      );
    }

    final completer = Completer<String>();
    var settled = false;

    void finish(String? text, Object? error) {
      if (settled) return;
      settled = true;
      try {
        recognition.stop();
      } catch (_) {}
      if (error != null) {
        completer.completeError(error);
      } else {
        completer.complete(text ?? '');
      }
    }

    recognition.lang = speechLangFor(lang);
    recognition.continuous = false;
    recognition.interimResults = false;

    recognition.onresult = ((web.Event event) {
      final text = _bestTranscript(event as web.SpeechRecognitionEvent);
      if (text.isNotEmpty) {
        finish(text, null);
      } else {
        finish(null, const SpeechUnavailableException('No speech was heard.'));
      }
    }).toJS;

    recognition.onerror = ((web.Event _) {
      finish(null, const SpeechUnavailableException(
        'Speech recognition failed. Please try again.',
      ));
    }).toJS;

    recognition.onend = ((web.Event _) {
      finish(null, const SpeechUnavailableException(
        'Speech recognition ended without a result.',
      ));
    }).toJS;

    final timer = Timer(const Duration(seconds: 15), () {
      finish(null, const SpeechUnavailableException(
        'Listening timed out. Please try again.',
      ));
    });
    completer.future.whenComplete(timer.cancel);

    try {
      recognition.start();
    } catch (_) {
      finish(null, const SpeechUnavailableException(
        'Could not start speech recognition.',
      ));
    }
    return completer.future;
  }

  @override
  void speak(String text, {required String lang}) {
    if (text.isEmpty) return;
    final synthesis = web.window.speechSynthesis;
    final utterance = web.SpeechSynthesisUtterance(text);
    utterance.lang = speechLangFor(lang);
    utterance.rate = 1.0;
    synthesis.cancel();
    synthesis.speak(utterance);
  }

  @override
  void stop() {
    web.window.speechSynthesis.cancel();
  }

  web.SpeechRecognition? _createRecognition() {
    final global = globalContext;
    if (global.has('SpeechRecognition')) {
      return (global['SpeechRecognition'] as JSFunction)
          .callAsConstructor<web.SpeechRecognition>();
    }
    if (global.has('webkitSpeechRecognition')) {
      return (global['webkitSpeechRecognition'] as JSFunction)
          .callAsConstructor<web.SpeechRecognition>();
    }
    return null;
  }

  static String _bestTranscript(web.SpeechRecognitionEvent event) {
    final results = event.results;
    final buffer = StringBuffer();
    for (var i = 0; i < results.length; i++) {
      final result = results.item(i);
      if (result.length > 0) {
        buffer.write(result.item(0).transcript);
        buffer.write(' ');
      }
    }
    return buffer.toString().trim();
  }
}

/// The factory `speech_service.dart` resolves through its conditional import.
///
/// It has to exist in BOTH branches — `flutter test` only ever compiles the
/// stub, so a missing web factory left the suite green while the release web
/// build stopped compiling (i.e. every deployment was unbuildable).
SpeechService createSpeechService() => WebSpeechService();