import 'package:flutter_test/flutter_test.dart';

import 'package:weathergpt/features/map/cap_geometry.dart';

void main() {
  group('parseCircle', () {
    test('parses "lat,lon radiusKm" with radius converted to meters', () {
      final circle = parseCircle('22.57,88.36 10');

      expect(circle, isNotNull);
      expect(circle!.center.latitude, 22.57);
      expect(circle.center.longitude, 88.36);
      expect(circle.radiusMeters, 10000);
    });

    test('handles extra whitespace between tokens', () {
      final circle = parseCircle('  22.57,88.36   5 ');

      expect(circle, isNotNull);
      expect(circle!.radiusMeters, 5000);
    });

    test('rejects spaces around the comma (not valid CAP format)', () {
      expect(parseCircle('22.57 , 88.36 5'), isNull);
    });

    test('returns null for malformed strings', () {
      expect(parseCircle(''), isNull);
      expect(parseCircle('22.57,88.36'), isNull); // no radius
      expect(parseCircle('22.57,88.36 10 extra'), isNull);
      expect(parseCircle('abc,88.36 10'), isNull);
      expect(parseCircle('22.57,88.36 abc'), isNull);
    });
  });

  group('parsePolygon', () {
    test('parses 3+ "lat,lon" vertex pairs', () {
      final polygon = parsePolygon('22.57,88.36 22.58,88.37 22.59,88.35');

      expect(polygon, isNotNull);
      expect(polygon!.points, hasLength(3));
      expect(polygon.points.first.latitude, 22.57);
      expect(polygon.points.last.longitude, 88.35);
    });

    test('returns null when fewer than 3 vertices', () {
      expect(parsePolygon('22.57,88.36 22.58,88.37'), isNull);
    });

    test('returns null for malformed strings', () {
      expect(parsePolygon(''), isNull);
      expect(parsePolygon('22.57,88.36 22.58 22.59,88.35'), isNull);
      expect(parsePolygon('22.57 88.36 22.58 88.37 22.59 88.35'), isNull);
    });
  });
}