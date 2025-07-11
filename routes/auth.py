from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from functools import wraps

bp = Blueprint('auth', __name__, url_prefix='/auth')

# Simple password - in production this should be in environment variables
APP_PASSWORD = "HeyStud"

def login_required(f):
    """Decorator to require authentication for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated'):
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

@bp.route('/login', methods=['GET', 'POST'])
def login():
    """Simple password login page"""
    if request.method == 'POST':
        password = request.form.get('password', '').strip()
        
        if password == APP_PASSWORD:
            session['authenticated'] = True
            session.permanent = True
            
            # Redirect to originally requested page or home
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('index'))
        else:
            flash('Invalid password. Please try again.', 'error')
    
    return render_template('auth/login.html')

@bp.route('/logout')
def logout():
    """Clear session and redirect to login"""
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))