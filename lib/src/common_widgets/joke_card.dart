import 'package:flutter/material.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/core/theme/app_theme.dart';

class JokeCard extends StatelessWidget {
  final Joke joke;
  final int? index;
  final VoidCallback? onTap;
  final bool showTrailingIcon;

  const JokeCard({
    super.key,
    required this.joke,
    this.index,
    this.onTap,
    this.showTrailingIcon = true,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.symmetric(vertical: 4.0),
      child: ListTile(
        leading: index != null
            ? CircleAvatar(
                backgroundColor: Theme.of(context).colorScheme.primary,
                child: Text(
                  '${index! + 1}',
                  style: TextStyle(
                    color: Theme.of(context).colorScheme.onPrimary,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              )
            : null,
        title: Text(
          joke.setupText,
          style: const TextStyle(
            fontWeight: FontWeight.w500,
          ),
          maxLines: 2,
          overflow: TextOverflow.ellipsis,
        ),
        subtitle: Text(
          joke.punchlineText,
          style: TextStyle(
            color: Theme.of(context).colorScheme.onSurface.withOpacity(0.7),
            fontStyle: FontStyle.italic,
          ),
          maxLines: 2,
          overflow: TextOverflow.ellipsis,
        ),
        trailing: showTrailingIcon
            ? Icon(
                Icons.arrow_forward_ios,
                size: 16,
                color: Theme.of(context).colorScheme.onSurface.withOpacity(0.4),
              )
            : null,
        onTap: onTap,
      ),
    );
  }
} 