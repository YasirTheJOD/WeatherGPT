import 'package:flutter/material.dart';

/// WeatherGPT look & feel — Material 3, seeded from the brand blue.
/// Kept in one place so a future dark theme / rebrand touches one file.
class AppTheme {
  AppTheme._();

  static const Color seed = Color(0xFF1565C0);

  static ThemeData light() => ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: seed),
        useMaterial3: true,
      );
}