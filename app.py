from flask import Flask, render_template, request, send_file, jsonify
from cryptography.fernet import Fernet
import os
import uuid
from datetime import datetime
import threading
import time

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB
app.secret_key = 'your-secret-key-here'

# Create upload folder if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Allowed file extensions
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'docx', 'xlsx', 'pptx', 'mp3', 'mp4', 'zip', 'mkv'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/encrypt')
def encrypt_page():
    return render_template('encrypt.html')

@app.route('/decrypt')
def decrypt_page():
    return render_template('decrypt.html')

@app.route('/generate-key', methods=['POST'])
def generate_key():
    """Generate a new encryption key"""
    try:
        key = Fernet.generate_key()
        key_id = str(uuid.uuid4())[:8]
        
        # Save key info
        key_data = {
            'key': key.decode(),
            'key_id': key_id,
            'created': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        return jsonify({
            'success': True,
            'key': key.decode(),
            'key_id': key_id,
            'message': 'Key generated successfully!'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/encrypt-file', methods=['POST'])
def encrypt_file():
    """Encrypt uploaded file"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file uploaded'})
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'})
        
        # Check file type
        if not allowed_file(file.filename):
            return jsonify({'success': False, 'error': 'File type not allowed'})
        
        # Get key
        key = request.form.get('key')
        if not key:
            return jsonify({'success': False, 'error': 'No encryption key provided'})
        
        # Read file
        file_data = file.read()
        file_size = len(file_data)
        
        if file_size > app.config['MAX_CONTENT_LENGTH']:
            return jsonify({'success': False, 'error': 'File too large (max 50MB)'})
        
        # Encrypt
        fernet = Fernet(key.encode())
        encrypted_data = fernet.encrypt(file_data)
        
        # Save encrypted file
        original_name = file.filename
        encrypted_filename = f"enc_{str(uuid.uuid4())[:8]}_{original_name}.enc"
        encrypted_path = os.path.join(app.config['UPLOAD_FOLDER'], encrypted_filename)
        
        with open(encrypted_path, 'wb') as f:
            f.write(encrypted_data)
        
        return jsonify({
            'success': True,
            'encrypted_file': encrypted_filename,
            'original_name': original_name,
            'file_size': f"{file_size/1024:.2f} KB",
            'message': 'File encrypted successfully!'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'Encryption failed: {str(e)}'})

@app.route('/decrypt-file', methods=['POST'])
def decrypt_file():
    """Decrypt uploaded file"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file uploaded'})
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'})
        
        # Check if it's an encrypted file
        if not file.filename.endswith('.enc'):
            return jsonify({'success': False, 'error': 'Not an encrypted file (.enc expected)'})
        
        # Get key
        key = request.form.get('key')
        if not key:
            return jsonify({'success': False, 'error': 'No decryption key provided'})
        
        # Read encrypted file
        encrypted_data = file.read()
        
        # Decrypt
        try:
            fernet = Fernet(key.encode())
            decrypted_data = fernet.decrypt(encrypted_data)
        except:
            return jsonify({'success': False, 'error': 'Invalid key or corrupted file'})
        
        # Get original filename (remove .enc and enc_ prefix)
        original_name = file.filename.replace('.enc', '')
        if original_name.startswith('enc_'):
            original_name = original_name[4:]  # Remove 'enc_' prefix
        if '_' in original_name:
            # Remove the UUID part
            parts = original_name.split('_', 2)
            if len(parts) > 2:
                original_name = parts[2]
            else:
                original_name = parts[-1]
        
        # Save decrypted file temporarily
        decrypted_filename = f"dec_{str(uuid.uuid4())[:8]}_{original_name}"
        decrypted_path = os.path.join(app.config['UPLOAD_FOLDER'], decrypted_filename)
        
        with open(decrypted_path, 'wb') as f:
            f.write(decrypted_data)
        
        return send_file(
            decrypted_path,
            as_attachment=True,
            download_name=original_name,
            mimetype='application/octet-stream'
        )
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'Decryption failed: {str(e)}'})

@app.route('/download/<filename>')
def download_file(filename):
    """Download a file"""
    try:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        return send_file(file_path, as_attachment=True)
    except:
        return jsonify({'error': 'File not found'})

@app.route('/cleanup', methods=['POST'])
def cleanup():
    """Clean up old files (can be called manually)"""
    try:
        current_time = time.time()
        count = 0
        for filename in os.listdir(app.config['UPLOAD_FOLDER']):
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.getctime(file_path) < current_time - 3600:  # 1 hour
                os.remove(file_path)
                count += 1
        return jsonify({'success': True, 'deleted': count})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def start_scheduled_cleanup():
    """Run cleanup every hour in background"""
    def run():
        while True:
            time.sleep(3600)  # Wait 1 hour
            with app.app_context():
                try:
                    current_time = time.time()
                    deleted = 0
                    for filename in os.listdir(app.config['UPLOAD_FOLDER']):
                        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                        if os.path.getctime(file_path) < current_time - 3600:
                            os.remove(file_path)
                            deleted += 1
                    if deleted > 0:
                        print(f"[Cleanup] Deleted {deleted} old file(s) from uploads folder.")
                except Exception as e:
                    print(f"[Cleanup] Error: {e}")
    
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    print("[System] Automatic cleanup scheduled every 1 hour.")

if __name__ == '__main__':
    start_scheduled_cleanup()
    app.run(debug=True, port=5000)