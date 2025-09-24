import 'package:flutter/material.dart';

class SpecialTile {
  const SpecialTile({required this.title, required this.onTap});
  final String title;
  final void Function(BuildContext context) onTap;
}

class SpecialTileWidget extends StatelessWidget {
  const SpecialTileWidget({super.key, required this.tile});
  final SpecialTile tile;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: InkWell(
        onTap: () => tile.onTap(context),
        child: Center(
          child: Padding(
            padding: const EdgeInsets.all(16.0),
            child: Text(tile.title, style: Theme.of(context).textTheme.headlineSmall),
          ),
        ),
      ),
    );
  }
}
