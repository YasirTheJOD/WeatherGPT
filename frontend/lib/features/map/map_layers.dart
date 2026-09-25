import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';

import '../../models/alert.dart';
import '../../models/location.dart';
import '../alerts/severity.dart';
import 'cap_geometry.dart';

/// Location pin for the selected place.
Marker buildLocationMarker(SelectedLocation location, Color color) => Marker(
      point: LatLng(location.latitude, location.longitude),
      width: 44,
      height: 44,
      child: Icon(Icons.location_on, color: color, size: 44),
    );

/// Circle markers for every CAP circle across the official alerts, each
/// colored by that alert's severity. Invalid circle strings are skipped.
List<CircleMarker> buildAlertCircles(List<Alert> alerts) {
  final markers = <CircleMarker>[];
  for (final alert in alerts) {
    final color = severityColor(severityFrom(alert.severity));
    for (final area in alert.areas) {
      for (final raw in area.circles) {
        final circle = parseCircle(raw);
        if (circle == null) continue;
        markers.add(CircleMarker(
          point: circle.center,
          radius: circle.radiusMeters,
          useRadiusInMeter: true,
          color: color.withValues(alpha: 0.18),
          borderColor: color,
          borderStrokeWidth: 2,
        ));
      }
    }
  }
  return markers;
}

/// Polygons for every CAP polygon across the official alerts, colored by
/// severity. Invalid polygon strings are skipped.
List<Polygon> buildAlertPolygons(List<Alert> alerts) {
  final polygons = <Polygon>[];
  for (final alert in alerts) {
    final color = severityColor(severityFrom(alert.severity));
    for (final area in alert.areas) {
      for (final raw in area.polygons) {
        final polygon = parsePolygon(raw);
        if (polygon == null) continue;
        polygons.add(Polygon(
          points: polygon.points,
          color: color.withValues(alpha: 0.18),
          borderColor: color,
          borderStrokeWidth: 2,
        ));
      }
    }
  }
  return polygons;
}