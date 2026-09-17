from flask import Flask, render_template, request, redirect, url_for
import os
print("Running file from:", os.path.abspath(__file__))
app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # Retrieve form data from the prototype
        file = request.files.get('document')
        filename = file.filename if file and file.filename else "Document.pdf"
        print_type = request.form.get('print_type')
        copies = request.form.get('copies')
        classroom = request.form.get('classroom')
        
        # Pass details to the success confirmation page
        return redirect(url_for('success', filename=filename, print_type=print_type, copies=copies, classroom=classroom))
    
    return render_template('index.html')

@app.route('/success')
def success():
    filename = request.args.get('filename', 'Document.pdf')
    print_type = request.args.get('print_type', 'Black & White')
    copies = request.args.get('copies', '1')
    classroom = request.args.get('classroom', 'Room 101')
    
    return render_template('success.html', filename=filename, print_type=print_type, copies=copies, classroom=classroom)

if __name__ == '__main__':
    app.run(debug=True,port=5001)