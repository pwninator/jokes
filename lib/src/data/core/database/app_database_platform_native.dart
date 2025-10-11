import 'dart:io' show Directory, File;

import 'package:drift/backends.dart';
import 'package:drift/native.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';

Future<QueryExecutor> openExecutor() async {
  final Directory appDocDir = await getApplicationDocumentsDirectory();
  final String dbPath = p.join(appDocDir.path, 'snickerdoodle.db');
  return NativeDatabase(File(dbPath));
}

QueryExecutor inMemoryExecutor() {
  return NativeDatabase.memory();
}
