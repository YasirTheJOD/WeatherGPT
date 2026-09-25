import 'package:flutter/material.dart';

/// CAP 1.2 severity → visual treatment. This is factual labelling of the
/// official severity field — the UI never derives or invents risk.
enum CapSeverity { extreme, severe, moderate, minor, unknown }

CapSeverity severityFrom(String? value) {
  switch (value?.toLowerCase()) {
    case 'extreme':
      return CapSeverity.extreme;
    case 'severe':
      return CapSeverity.severe;
    case 'moderate':
      return CapSeverity.moderate;
    case 'minor':
      return CapSeverity.minor;
    default:
      return CapSeverity.unknown;
  }
}

Color severityColor(CapSeverity severity) {
  switch (severity) {
    case CapSeverity.extreme:
      return const Color(0xFFB71C1C); // red
    case CapSeverity.severe:
      return const Color(0xFFE65100); // orange
    case CapSeverity.moderate:
      return const Color(0xFFF9A825); // amber
    case CapSeverity.minor:
      return const Color(0xFF558B2F); // green
    case CapSeverity.unknown:
      return const Color(0xFF757575);
  }
}