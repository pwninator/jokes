"""Admin route for rhyming word lookup."""

from flask import render_template, request

from functions import auth_helpers
from services import phonetics
from web.routes.admin.dashboard import web_bp


@web_bp.route('/admin/rhyming-words', methods=['GET', 'POST'])
@auth_helpers.require_admin
def admin_rhyming_words():
  """Render rhyming word tool and optional phonetic matches."""
  word = None
  homophones = []
  rhymes = []

  if request.method == 'POST':
    word = request.form.get('word')
    if word:
      homophones, rhymes = phonetics.get_phonetic_matches(word)

  return render_template(
    'admin/rhyming_words.html',
    site_name='Snickerdoodle',
    word=word,
    homophones=homophones,
    rhymes=rhymes,
  )
