import 'package:flutter/material.dart';

import '../models/location.dart';

/// UI language options. `hinglish` is a chat-input mode (Hinglish parsing is a
/// backend Phase 5 concern); the UI locale for it remains English until a
/// dedicated dictionary lands.
enum AppLanguage {
  english('en', 'English'),
  hindi('hi', 'हिन्दी'),
  hinglish('en', 'Hinglish');

  const AppLanguage(this.localeCode, this.label);

  final String localeCode;
  final String label;
}

/// App-wide shared state (Phase 4): the selected location and the language.
///
/// Everything screen-level (loading flags, chat history) lives in its own
/// feature state — this stays deliberately small.
class AppState extends ChangeNotifier {
  SelectedLocation? _location;
  AppLanguage _language = AppLanguage.english;

  SelectedLocation? get location => _location;

  AppLanguage get language => _language;

  Locale get locale => Locale(_language.localeCode);

  void setLocation(SelectedLocation location) {
    _location = location;
    notifyListeners();
  }

  void clearLocation() {
    _location = null;
    notifyListeners();
  }

  void setLanguage(AppLanguage language) {
    _language = language;
    notifyListeners();
  }
}