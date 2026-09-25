import 'package:latlong2/latlong.dart';

/// Parsers for CAP 1.2 `<circle>` / `<polygon>` area strings, as they appear
/// in SACHET alert payloads (`CapArea.circles` / `CapArea.polygons`):
///
///  * circle:  `"lat,lon radius"`      (radius in km, per CAP spec)
///  * polygon: `"lat,lon lat,lon ..."` (3+ vertex pairs, "lat,lon" order)
///
/// Invalid entries return null and are skipped by the map layer builder.

class CapCircle {
  const CapCircle({required this.center, required this.radiusMeters});

  final LatLng center;
  final double radiusMeters;
}

class CapPolygon {
  const CapPolygon({required this.points});

  final List<LatLng> points;
}

CapCircle? parseCircle(String raw) {
  final parts = raw.trim().split(RegExp(r'\s+'));
  if (parts.length != 2) return null;
  final coords = parts[0].split(',');
  if (coords.length != 2) return null;
  final lat = double.tryParse(coords[0].trim());
  final lon = double.tryParse(coords[1].trim());
  final radiusKm = double.tryParse(parts[1].trim());
  if (lat == null || lon == null || radiusKm == null) return null;
  return CapCircle(center: LatLng(lat, lon), radiusMeters: radiusKm * 1000);
}

CapPolygon? parsePolygon(String raw) {
  final points = <LatLng>[];
  for (final pair in raw.trim().split(RegExp(r'\s+'))) {
    final coords = pair.split(',');
    if (coords.length != 2) return null;
    final lat = double.tryParse(coords[0].trim());
    final lon = double.tryParse(coords[1].trim());
    if (lat == null || lon == null) return null;
    points.add(LatLng(lat, lon));
  }
  if (points.length < 3) return null;
  return CapPolygon(points: points);
}