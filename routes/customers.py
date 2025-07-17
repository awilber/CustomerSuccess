from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, Customer, Person, EmailThread, FileReference, DirectoryLink
from sqlalchemy import func

bp = Blueprint('customers', __name__, url_prefix='/customers')

@bp.route('/')
def list():
    customers = Customer.query.all()
    return render_template('customers/list.html', customers=customers)

@bp.route('/<int:id>')
def detail(id):
    customer = Customer.query.get_or_404(id)
    
    # Get email statistics
    email_count = customer.email_threads.count()
    
    # Get recent emails
    recent_emails = customer.email_threads.order_by(EmailThread.date.desc()).limit(10).all()
    
    # Get people
    people = customer.people.all()
    
    # Get file references
    files = customer.file_references.order_by(FileReference.last_modified.desc()).limit(10).all()
    
    # Get directories
    directories = customer.directory_links
    
    return render_template('customers/detail.html', 
                         customer=customer,
                         email_count=email_count,
                         recent_emails=recent_emails,
                         people=people,
                         files=files,
                         directories=directories)

@bp.route('/<int:id>/timeline')
def timeline(id):
    customer = Customer.query.get_or_404(id)
    
    # Get all emails for timeline
    emails = customer.email_threads.order_by(EmailThread.date).all()
    
    # Get people for filtering
    people = customer.people.all()
    
    return render_template('customers/timeline.html',
                         customer=customer,
                         emails=emails,
                         people=people)

@bp.route('/add', methods=['GET', 'POST'])
def add():
    if request.method == 'POST':
        customer = Customer(
            name=request.form['name'],
            company=request.form.get('company', '')
        )
        db.session.add(customer)
        db.session.commit()
        
        flash(f'Customer {customer.name} added successfully!', 'success')
        return redirect(url_for('customers.detail', id=customer.id))
    
    return render_template('customers/add.html')