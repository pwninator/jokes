import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/startup/offline_bundle_loader.dart';

class MockFirestore extends Mock implements FirebaseFirestore {}

class MockAssetBundle extends Mock implements AssetBundle {}

class FakeLoadBundleTaskSnapshot extends Fake
    implements LoadBundleTaskSnapshot {
  @override
  int get bytesLoaded => 0;
  @override
  int get documentsLoaded => 0;
  @override
  LoadBundleTaskState get taskState => LoadBundleTaskState.success;
  @override
  int get totalBytes => 0;
  @override
  int get totalDocuments => 0;
}

class FakeLoadBundleTask extends Fake implements LoadBundleTask {
  FakeLoadBundleTask(this._stream);

  final Stream<LoadBundleTaskSnapshot> _stream;

  @override
  Stream<LoadBundleTaskSnapshot> get stream => _stream;
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUpAll(() {
    registerFallbackValue(Uint8List(0));
  });

  group('OfflineBundleLoader', () {
    late MockFirestore mockFirestore;
    late MockAssetBundle mockAssetBundle;

    setUp(() {
      mockFirestore = MockFirestore();
      mockAssetBundle = MockAssetBundle();
    });

    test('returns false when bundle asset is missing', () async {
      when(() => mockAssetBundle.load(any()))
          .thenThrow(FlutterError('missing bundle'));

      final loader = OfflineBundleLoader(
        firestore: mockFirestore,
        assetBundle: mockAssetBundle,
      );

      final result = await loader.loadLatestBundle();

      expect(result, isFalse);
      verifyNever(() => mockFirestore.loadBundle(any()));
    });

    test('loads the fixed bundle path and waits for completion',
        () async {
      final bundleBytes = Uint8List.fromList([1, 2, 3]);
      when(() => mockAssetBundle.load(any()))
          .thenAnswer((_) async => ByteData.sublistView(bundleBytes));

      final fakeTask = FakeLoadBundleTask(
        Stream<LoadBundleTaskSnapshot>.fromIterable(
          [FakeLoadBundleTaskSnapshot()],
        ),
      );
      when(() => mockFirestore.loadBundle(bundleBytes)).thenReturn(fakeTask);

      final loader = OfflineBundleLoader(
        firestore: mockFirestore,
        assetBundle: mockAssetBundle,
      );

      final result = await loader.loadLatestBundle();

      expect(result, isTrue);
      verify(() => mockAssetBundle.load(any())).called(1);
      verify(() => mockFirestore.loadBundle(bundleBytes)).called(1);
    });
  });
}
