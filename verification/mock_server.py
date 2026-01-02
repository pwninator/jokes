
from flask import Flask, render_template, jsonify, request, url_for
import os

# Set the template and static folders relative to the script
app = Flask(__name__,
            template_folder='../py_quill/web/templates',
            static_folder='../py_quill/web/static')

# Mock data
MOCK_BOOK = {
    'id': 'book-123',
    'book_name': 'Test Joke Book',
    'zip_url': None
}

MOCK_JOKES = [
    {
        'id': 'joke-1',
        'sequence': 1,
        'setup_text': 'Why did the chicken cross the road?',
        'punchline_text': 'To get to the other side.',
        'setup_image': None,
        'punchline_image': None,
        'num_views': 100,
        'num_saves': 10,
        'num_shares': 5,
        'popularity_score': 0.8,
        'num_saved_users_fraction': 0.1,
        'total_cost': 0.05,
        'setup_variants': [],
        'punchline_variants': []
    }
]

# Mock endpoints referenced in templates
@app.route('/admin/dashboard', endpoint='web.admin_dashboard')
def web_admin_dashboard(): return ""

@app.route('/admin/joke-books', endpoint='web.admin_joke_books')
def web_admin_joke_books(): return ""

@app.route('/admin/stats', endpoint='web.admin_stats')
def web_admin_stats(): return ""

@app.route('/admin/login', endpoint='web.admin_login')
def web_admin_login(): return ""

@app.route('/admin/joke-books/<book_id>')
def joke_book_detail(book_id):
    return render_template('admin/joke_book_detail.html',
                           book=MOCK_BOOK,
                           jokes=MOCK_JOKES,
                           book_total_cost=0.05,
                           site_name='Test Site',
                           generate_book_page_url='/mock/generate',
                           update_book_page_url='/mock/update',
                           set_main_image_url='/mock/set_main',
                           functions_origin='', # Use relative paths
                           user={'email': 'test@example.com'} # Mock user for base template
                           )

@app.route('/search_jokes')
def search_jokes():
    query = request.args.get('search_query')
    exclude_in_book = request.args.get('exclude_in_book')

    # Verify the param is present
    print(f"DEBUG: search_jokes called with query={query}, exclude_in_book={exclude_in_book}")

    # Return some mock results
    return jsonify({
        'data': {
            'jokes': [
                {
                    'joke_id': 'joke-new-1',
                    'setup_text': 'New Joke 1',
                    'punchline_text': 'Punchline 1',
                    'setup_image_url': 'https://via.placeholder.com/150',
                    'punchline_image_url': 'https://via.placeholder.com/150'
                },
                 {
                    'joke_id': 'joke-1', # This is already in the book (MOCK_JOKES)
                    'setup_text': 'Why did the chicken cross the road?',
                    'punchline_text': 'To get to the other side.',
                }
            ]
        }
    })

@app.route('/admin/joke-books/<book_id>/jokes/add', methods=['POST'])
def add_jokes(book_id):
    return jsonify({'status': 'success'})

@app.route('/admin/joke-books/<book_id>/jokes/<joke_id>/refresh')
def refresh_joke(book_id, joke_id):
     return jsonify({})

if __name__ == '__main__':
    app.run(port=5000)
