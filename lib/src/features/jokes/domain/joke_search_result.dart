class JokeSearchResult {
  final String id;
  final double vectorDistance;

  const JokeSearchResult({required this.id, required this.vectorDistance});

  factory JokeSearchResult.fromMap(Map<dynamic, dynamic> map) {
    final id = map['joke_id']?.toString() ?? '';
    final raw = map.containsKey('vector_distance')
        ? map['vector_distance']
        : map['score'];
    final distance = (raw is num) ? raw.toDouble() : 0.0;
    return JokeSearchResult(id: id, vectorDistance: distance);
  }
}
