import '../core/api/api_client.dart';
import '../models/source.dart';

/// Client for `/api/v1/sources` — the backend's curated data-source registry
/// with live availability. Powers the sources drawer's transparency story.
///
/// The drawer treats a failure here as non-fatal (it falls back to a built-in
/// list), so this service deliberately lets [ApiException] propagate and let
/// the caller decide.
class SourcesService {
  SourcesService({ApiClient? api}) : _api = api ?? ApiClient();

  final ApiClient _api;

  Future<List<SourceInfo>> fetch() async {
    final json = await _api.getJson('/sources');
    final raw = json['sources'];
    if (raw is! List) return const [];
    return raw
        .whereType<Map<String, dynamic>>()
        .map(SourceInfo.fromJson)
        .toList(growable: false);
  }
}
