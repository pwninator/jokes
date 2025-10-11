import 'package:drift/backends.dart';
import 'package:drift/wasm.dart';

Future<QueryExecutor> openExecutor() async {
  // Use IndexedDB persistence by default
  final result = await WasmDatabase.open(
    databaseName: 'snickerdoodle',
    sqlite3Uri: Uri.parse('sqlite3.wasm'),
    driftWorkerUri: Uri.parse('drift_worker.dart.js'),
  );
  return result.resolvedExecutor;
}

QueryExecutor inMemoryExecutor() =>
    throw UnimplementedError('Web in-memory executor is not used in VM tests');
