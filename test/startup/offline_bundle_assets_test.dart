import 'dart:convert';
import 'dart:io';

import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/core/services/image_service.dart';
import 'package:snickerdoodle/src/startup/offline_bundle_loader.dart';

const _bundleAssetPath = OfflineBundleLoader.bundlePath;
const _imageManifestPath = ImageService.assetImageManifestPath;
const _imageAssetBasePath = ImageService.assetImageBasePath;
const _cdnPrefix = 'https://images.quillsstorybook.com/cdn-cgi/image/';
const _imageFieldNames = <String>[
  'image_url',
  'setup_image_url',
  'punchline_image_url',
];

class _BundleAnalysis {
  int entryCount = 0;
  final Set<String> collections = <String>{};
  bool hasCategoryCache = false;
  final Set<String> imageTails = <String>{};
  final List<String> invalidImageUrls = <String>[];
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('Firestore bundle assets', () {
    test('bundle format is valid and contains expected collections', () async {
      final bundleBytes = await _loadAssetBytes(_bundleAssetPath);
      final analysis = _analyzeBundle(bundleBytes);

      expect(analysis.entryCount, greaterThan(0));
      expect(analysis.collections, contains('joke_feed'));
      expect(analysis.collections, contains('joke_categories'));
      expect(analysis.collections, contains('jokes'));
    });

    test('bundle image URLs match manifest and assets', () async {
      final bundleBytes = await _loadAssetBytes(_bundleAssetPath);
      final analysis = _analyzeBundle(bundleBytes);

      expect(analysis.invalidImageUrls, isEmpty);
      expect(analysis.imageTails, isNotEmpty);

      final manifestJson = await rootBundle.loadString(_imageManifestPath);
      final manifestList =
          (jsonDecode(manifestJson) as List<dynamic>).cast<String>();
      final manifestSet = manifestList.toSet();
      expect(manifestSet.length, manifestList.length);

      final missingInManifest = analysis.imageTails.difference(manifestSet);
      final extraInManifest = manifestSet.difference(analysis.imageTails);
      final missingAssets = manifestSet
          .where(
            (tail) => !File('$_imageAssetBasePath$tail').existsSync(),
          )
          .toList();

      expect(
        missingInManifest,
        isEmpty,
        reason: _formatSample('Missing from image manifest', missingInManifest),
      );
      expect(
        extraInManifest,
        isEmpty,
        reason: _formatSample('Extra in image manifest', extraInManifest),
      );
      expect(
        missingAssets,
        isEmpty,
        reason: _formatSample('Assets missing from bundle', missingAssets),
      );
    });
  });
}

Future<Uint8List> _loadAssetBytes(String assetPath) async {
  final data = await rootBundle.load(assetPath);
  return data.buffer.asUint8List(data.offsetInBytes, data.lengthInBytes);
}

_BundleAnalysis _analyzeBundle(Uint8List bytes) {
  if (_looksLengthDelimited(bytes)) {
    return _analyzeLengthDelimited(bytes);
  }

  return _analyzeJsonText(bytes);
}

_BundleAnalysis _analyzeLengthDelimited(Uint8List bytes) {
  final analysis = _BundleAnalysis();
  var index = 0;

  while (index < bytes.length) {
    if (_isTrailingWhitespace(bytes, index)) {
      break;
    }

    final lengthEnd = _findLengthEnd(bytes, index);
    if (lengthEnd == -1) {
      throw FormatException(
        'Bundle length prefix not found at offset $index.',
      );
    }

    final lengthStr = ascii.decode(bytes.sublist(index, lengthEnd)).trim();
    final length = int.tryParse(lengthStr);
    if (length == null || length <= 0) {
      throw FormatException('Invalid bundle length "$lengthStr" at $index.');
    }

    final jsonStart = _skipLineBreak(bytes, lengthEnd);
    final jsonEnd = jsonStart + length;
    if (jsonEnd > bytes.length) {
      throw FormatException(
        'Bundle entry exceeds file size at offset $index.',
      );
    }

    final jsonBytes = Uint8List.sublistView(bytes, jsonStart, jsonEnd);
    final decoded = jsonDecode(utf8.decode(jsonBytes));
    if (decoded is! Map<String, dynamic>) {
      throw FormatException('Unexpected bundle entry at offset $index.');
    }

    analysis.entryCount += 1;
    _processBundleEntry(decoded, analysis);
    index = jsonEnd;
  }

  return analysis;
}

_BundleAnalysis _analyzeJsonText(Uint8List bytes) {
  final analysis = _BundleAnalysis();
  final decoded = jsonDecode(utf8.decode(bytes, allowMalformed: true));

  if (decoded is List) {
    analysis.entryCount = decoded.length;
  } else {
    analysis.entryCount = 1;
  }

  _scanJson(decoded, analysis);
  return analysis;
}

void _processBundleEntry(Map<String, dynamic> entry, _BundleAnalysis analysis) {
  final name = _extractDocumentName(entry);
  if (name != null) {
    _updateCollections(name, analysis);
  }

  final document = entry['document'];
  if (document is! Map<String, dynamic>) {
    return;
  }

  final fields = document['fields'];
  if (fields is! Map<String, dynamic>) {
    return;
  }

  _collectImageUrlsFromFields(fields, analysis);
}

String? _extractDocumentName(Map<String, dynamic> entry) {
  final metadata = entry['documentMetadata'];
  if (metadata is Map<String, dynamic>) {
    final name = metadata['name'];
    if (name is String) {
      return name;
    }
  }

  final document = entry['document'];
  if (document is Map<String, dynamic>) {
    final name = document['name'];
    if (name is String) {
      return name;
    }
  }

  return null;
}

void _scanJson(Object? value, _BundleAnalysis analysis) {
  if (value is Map<String, dynamic>) {
    final name = value['name'];
    if (name is String) {
      _updateCollections(name, analysis);
    }

    final fields = value['fields'];
    if (fields is Map<String, dynamic>) {
      _collectImageUrlsFromFields(fields, analysis);
    }

    for (final entry in value.values) {
      _scanJson(entry, analysis);
    }
  } else if (value is List) {
    for (final entry in value) {
      _scanJson(entry, analysis);
    }
  }
}

void _collectImageUrlsFromFields(
  Map<String, dynamic> fields,
  _BundleAnalysis analysis,
) {
  for (final fieldName in _imageFieldNames) {
    final fieldValue = fields[fieldName];
    if (fieldValue is! Map<String, dynamic>) {
      continue;
    }
    final url = fieldValue['stringValue'];
    if (url is! String) {
      continue;
    }
    final tail = _extractImageTail(url);
    if (tail == null) {
      analysis.invalidImageUrls.add(url);
    } else {
      analysis.imageTails.add(tail);
    }
  }
}

void _updateCollections(String name, _BundleAnalysis analysis) {
  const marker = '/documents/';
  final markerIndex = name.indexOf(marker);
  if (markerIndex == -1) {
    return;
  }

  final path = name.substring(markerIndex + marker.length);
  final segments = path.split('/');
  if (segments.isEmpty) {
    return;
  }

  analysis.collections.add(segments.first);
  if (path.contains('/category_jokes/cache')) {
    analysis.hasCategoryCache = true;
  }
}

String? _extractImageTail(String url) {
  if (!url.startsWith(_cdnPrefix)) {
    return null;
  }

  final remainder = url.substring(_cdnPrefix.length);
  final slashIndex = remainder.indexOf('/');
  if (slashIndex <= 0 || slashIndex >= remainder.length - 1) {
    return null;
  }

  return remainder.substring(slashIndex + 1);
}

int _findLengthEnd(Uint8List bytes, int start) {
  for (var i = start; i < bytes.length; i += 1) {
    final value = bytes[i];
    if (value < 0x30 || value > 0x39) {
      return i;
    }
  }
  return -1;
}

int _skipLineBreak(Uint8List bytes, int start) {
  if (start >= bytes.length) {
    return start;
  }
  if (bytes[start] == 0x0D) {
    final next = start + 1;
    if (next < bytes.length && bytes[next] == 0x0A) {
      return next + 1;
    }
    return next;
  }
  if (bytes[start] == 0x0A) {
    return start + 1;
  }
  return start;
}

bool _isTrailingWhitespace(Uint8List bytes, int start) {
  for (var i = start; i < bytes.length; i += 1) {
    if (!_isWhitespaceByte(bytes[i])) {
      return false;
    }
  }
  return true;
}

bool _isWhitespaceByte(int value) {
  return value == 0x0A || value == 0x0D || value == 0x20 || value == 0x09;
}

bool _looksLengthDelimited(Uint8List bytes) {
  final start = _firstNonWhitespace(bytes);
  if (start == -1) {
    return false;
  }
  final value = bytes[start];
  final isDigit = value >= 0x30 && value <= 0x39;
  if (!isDigit) {
    return false;
  }
  final lengthEnd = _findLengthEnd(bytes, start);
  if (lengthEnd == -1) {
    return false;
  }
  final jsonStart = _skipLineBreak(bytes, lengthEnd);
  if (jsonStart >= bytes.length) {
    return false;
  }
  final startByte = bytes[jsonStart];
  return startByte == 0x7B || startByte == 0x5B;
}

int _firstNonWhitespace(Uint8List bytes) {
  for (var i = 0; i < bytes.length; i += 1) {
    if (!_isWhitespaceByte(bytes[i])) {
      return i;
    }
  }
  return -1;
}

String _formatSample(String label, Iterable<Object> items) {
  if (items.isEmpty) {
    return label;
  }
  final sample = items.take(10).join(', ');
  return '$label: $sample';
}
