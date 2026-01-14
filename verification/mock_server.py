
import flask
import datetime
import os
import sys

# Add py_quill to path to import common modules if needed, but I'll try to mock data directly
sys.path.append(os.path.abspath('py_quill'))

try:
    from common import image_generation
except ImportError:
    print("Could not import common.image_generation")
    sys.exit(1)

app = flask.Flask(__name__, template_folder='../py_quill/web/templates', static_folder='../py_quill/web/static')

@app.template_filter('format_image_url')
def format_image_url(url, **kwargs):
    return url

# Mock routes needed by admin_base.html and others
@app.route('/admin/dashboard', endpoint='web.admin_dashboard')
def admin_dashboard(): return "Dashboard"

@app.route('/admin/jokes', endpoint='web.admin_jokes')
def admin_jokes():
    dummy_joke = {
        'key': 'joke-123',
        'setup_text': 'Why did the chicken cross the road?',
        'punchline_text': 'To get to the other side.',
        'setup_image_url': 'https://via.placeholder.com/350',
        'punchline_image_url': 'https://via.placeholder.com/350',
        'state': type('obj', (object,), {'value': 'APPROVED'}),
        'public_timestamp': datetime.datetime.now(),
        'num_viewed_users': 100,
        'num_saved_users': 10,
        'num_shared_users': 5,
        'edit_payload': {}
    }

    entry = {
        'joke': dummy_joke,
        'cursor': 'next-cursor',
        'is_future_daily': False,
        'edit_payload': {}
    }

    image_qualities = list(image_generation.PUN_IMAGE_CLIENTS_BY_QUALITY.keys())

    return flask.render_template(
        'admin/admin_jokes.html',
        site_name='Snickerdoodle',
        joke_creation_url='/joke_creation_process',
        all_states=['APPROVED', 'DRAFT'],
        selected_states=['APPROVED'],
        selected_states_param='APPROVED',
        categories=[],
        selected_category_id=None,
        jokes=[entry],
        next_cursor=None,
        has_more=False,
        image_size=350,
        image_qualities=image_qualities,
        # Mock globals
        now_utc=datetime.datetime.now(datetime.timezone.utc),
        functions_origin='http://localhost:5000'
    )

@app.route('/logout', endpoint='web.auth_logout')
def logout(): return "Logout"
@app.route('/logout-alias', endpoint='web.logout')
def logout_alias(): return "Logout"

@app.route('/admin/books', endpoint='web.admin_books')
def admin_books(): return ""
@app.route('/admin/books-alias', endpoint='web.admin_joke_books')
def admin_joke_books(): return ""

@app.route('/admin/categories', endpoint='web.admin_categories')
def admin_categories(): return ""
@app.route('/admin/categories-alias', endpoint='web.admin_joke_categories')
def admin_joke_categories(): return ""

@app.route('/admin/social', endpoint='web.admin_social')
def admin_social(): return ""

@app.route('/admin/printable-notes', endpoint='web.admin_printable_notes')
def admin_printable_notes(): return ""

@app.route('/admin/redirect-tester', endpoint='web.admin_redirect_tester')
def admin_redirect_tester(): return ""

@app.route('/session-info', endpoint='web.session_info')
def session_info(): return ""

@app.route('/login', endpoint='web.auth_login')
def login(): return "Login"
@app.route('/login-alias', endpoint='web.login')
def login_alias(): return "Login"

if __name__ == '__main__':
    print("Starting mock server on 5000...")
    try:
        app.run(port=5000, debug=True, use_reloader=False)
    except Exception as e:
        print(f"Failed to start server: {e}")
