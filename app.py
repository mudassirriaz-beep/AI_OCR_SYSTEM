from flask import Flask, request, jsonify, render_template
import os
from werkzeug.utils import secure_filename
from brain_format import extract_cnic_info
import fitz  # PyMuPDF

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def allowed_file(filename):
    """Allow images and PDFs."""
    allowed_extensions = {'png', 'jpg', 'jpeg', 'bmp', 'tiff', 'pdf'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

def convert_pdf_to_image(pdf_path, output_image_path):
    """Convert first page of PDF to JPEG image."""
    doc = fitz.open(pdf_path)
    if len(doc) == 0:
        raise ValueError("Empty PDF file")
    page = doc[0]  # first page
    pix = page.get_pixmap(dpi=200)  # render at 200 DPI
    pix.save(output_image_path, "jpeg")
    doc.close()
    return output_image_path

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if not allowed_file(file.filename):
        return jsonify({'error': 'File type not allowed. Only images and PDFs.'}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    # If PDF, convert to image first
    ext = filename.rsplit('.', 1)[1].lower()
    if ext == 'pdf':
        try:
            image_path = filepath.replace('.pdf', '_page1.jpg')
            convert_pdf_to_image(filepath, image_path)
            # Use the generated image for extraction
            process_path = image_path
        except Exception as e:
            return jsonify({'error': f'PDF conversion failed: {str(e)}'}), 500
    else:
        process_path = filepath

    try:
        extracted_data = extract_cnic_info(process_path)
        # Optionally delete temporary files (keep original uploads for debugging)
        # os.remove(process_path) if process_path != filepath else None
        return jsonify(extracted_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)