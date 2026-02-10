"""Admin character animator route."""

from __future__ import annotations

import flask
from functions import auth_helpers
from services import firestore
from web.routes import web_bp


@web_bp.route('/admin/character-animator')
@auth_helpers.require_admin
def character_animator() -> str:
  """Render the character animator tool."""
  character_defs = firestore.get_posable_character_defs()
  sequences = firestore.get_posable_character_sequences()
  return flask.render_template(
    'admin/character_animator.html',
    site_name='Snickerdoodle',
    character_defs=character_defs,
    sequences=sequences,
  )


@web_bp.route('/admin/api/character-animator/data', methods=['POST'])
@auth_helpers.require_admin
def character_animator_data() -> flask.Response:
  """Get character definition and sequence data."""
  data = flask.request.get_json()
  def_id = data.get('def_id')
  seq_id = data.get('seq_id')

  if not def_id and not seq_id:
    return flask.jsonify({'error': 'Missing def_id or seq_id'}), 400

  character_def = None
  if def_id:
    character_def = firestore.get_posable_character_def(def_id)
    if not character_def:
      return flask.jsonify({'error': 'Definition not found'}), 404

  sequence = None
  if seq_id:
    sequence = firestore.get_posable_character_sequence(seq_id)
    if not sequence:
      return flask.jsonify({'error': 'Sequence not found'}), 404

  return flask.jsonify({
    'definition': character_def.to_dict(include_key=True) if character_def else None,
    'sequence': sequence.to_dict(include_key=True) if sequence else None,
  })
