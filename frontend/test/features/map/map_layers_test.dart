import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:weathergpt/features/alerts/severity.dart';
import 'package:weathergpt/features/map/map_layers.dart';
import 'package:weathergpt/models/alert.dart';
import 'package:weathergpt/models/location.dart';
import 'package:weathergpt/models/provenance.dart';

const _provenance = Provenance(
  sourceId: 'sachet',
  sourceName: 'SACHET',
  authoritative: true,
);

Alert _alertWith({
  String severity = 'Severe',
  List<String> circles = const [],
  List<String> polygons = const [],
}) =>
    Alert(
      identifier: 'CAP-1',
      event: 'Heavy Rain',
      severity: severity,
      areas: [CapArea(areaDesc: 'Kolkata', circles: circles, polygons: polygons)],
      provenance: _provenance,
    );

void main() {
  test('buildLocationMarker pins the selected location', () {
    const location = SelectedLocation(
      name: 'Kolkata',
      latitude: 22.57,
      longitude: 88.36,
    );

    final marker = buildLocationMarker(location, const Color(0xFF1565C0));

    expect(marker.point.latitude, 22.57);
    expect(marker.point.longitude, 88.36);
  });

  test('buildAlertCircles converts CAP circles with severity color', () {
    final alerts = [
      _alertWith(severity: 'Extreme', circles: ['22.57,88.36 10']),
      _alertWith(severity: 'Minor', circles: ['23.0,89.0 5']),
    ];

    final circles = buildAlertCircles(alerts);

    expect(circles, hasLength(2));
    final extreme = circles.first;
    expect(extreme.point.latitude, 22.57);
    expect(extreme.radius, 10000);
    expect(extreme.useRadiusInMeter, isTrue);
    expect(extreme.borderColor, severityColor(CapSeverity.extreme));
    expect(circles.last.borderColor, severityColor(CapSeverity.minor));
  });

  test('buildAlertCircles skips invalid circle strings', () {
    final alerts = [_alertWith(circles: ['not-a-circle', '22.57,88.36 10'])];

    expect(buildAlertCircles(alerts), hasLength(1));
  });

  test('buildAlertPolygons converts CAP polygons with severity color', () {
    final alerts = [
      _alertWith(
        severity: 'Severe',
        polygons: ['22.57,88.36 22.58,88.37 22.59,88.35'],
      ),
    ];

    final polygons = buildAlertPolygons(alerts);

    expect(polygons, hasLength(1));
    expect(polygons.first.points, hasLength(3));
    expect(polygons.first.borderColor, severityColor(CapSeverity.severe));
  });

  test('buildAlertPolygons skips invalid polygon strings', () {
    final alerts = [_alertWith(polygons: ['22.57,88.36 22.58,88.37'])];

    expect(buildAlertPolygons(alerts), isEmpty);
  });

  test('no geometry → no layers', () {
    final alerts = [_alertWith()];

    expect(buildAlertCircles(alerts), isEmpty);
    expect(buildAlertPolygons(alerts), isEmpty);
  });
}