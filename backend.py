"""
Python AI Runner - Flask Backend
A simple backend server for executing Python code and installing packages
"""

from flask import Flask, render_template
from flask import Flask, request, jsonify
from flask_cors import CORS
import subprocess
import sys
import tempfile
import os
import time
from functools import wraps

app = Flask(__name__)

# Enable CORS for browser access
CORS(app, resources={
    r"/api/*": {
        "origins": "*",
        "methods": ["POST", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})

# Simple in-memory rate limiting (use Redis in production)
rate_limit_cache = {}

def rate_limit(max_requests=20, window=60):
    """
    Simple rate limiting decorator
    max_requests: maximum number of requests per window
    window: time window in seconds
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            client_ip = request.remote_addr
            current_time = time.time()
            
            # Initialize or clean old entries
            if client_ip not in rate_limit_cache:
                rate_limit_cache[client_ip] = []
            
            rate_limit_cache[client_ip] = [
                t for t in rate_limit_cache[client_ip]
                if current_time - t < window
            ]
            
            # Check limit
            if len(rate_limit_cache[client_ip]) >= max_requests:
                return jsonify({
                    'success': False,
                    'output': '',
                    'errors': f'Rate limit exceeded. Maximum {max_requests} requests per {window} seconds.'
                }), 429
            
            # Add current request timestamp
            rate_limit_cache[client_ip].append(current_time)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/run', methods=['POST', 'OPTIONS'])
@rate_limit(max_requests=20, window=60)
def run_code():
    """
    Execute Python code and return output
    
    Request JSON:
    {
        "code": "print('Hello, World!')"
    }
    
    Response JSON:
    {
        "success": true,
        "output": "Hello, World!\n",
        "errors": ""
    }
    """
    if request.method == 'OPTIONS':
        return '', 204
    
    try:
        data = request.get_json()
        code = data.get('code', '')
        
        if not code:
            return jsonify({
                'success': False,
                'output': '',
                'errors': 'No code provided'
            })
        
        # Create temporary file for code execution
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_file = f.name
        
        try:
            # Execute code in subprocess with timeout
            result = subprocess.run(
                [sys.executable, temp_file],
                capture_output=True,
                text=True,
                timeout=30,  # 30 second timeout
                env=os.environ.copy()  # Inherit environment variables
            )
            
            return jsonify({
                'success': result.returncode == 0,
                'output': result.stdout,
                'errors': result.stderr
            })
        
        finally:
            # Clean up temporary file
            if os.path.exists(temp_file):
                os.unlink(temp_file)
    
    except subprocess.TimeoutExpired:
        return jsonify({
            'success': False,
            'output': '',
            'errors': 'Execution timeout: Code took longer than 30 seconds to execute'
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'output': '',
            'errors': f'Server error: {str(e)}'
        })

@app.route('/api/install', methods=['POST', 'OPTIONS'])
@rate_limit(max_requests=10, window=300)  # Stricter limit for package installation
def install_package():
    """
    Install a pip package
    
    Request JSON:
    {
        "package": "openai"
    }
    
    Response JSON:
    {
        "success": true,
        "output": "Successfully installed openai-1.0.0",
        "errors": ""
    }
    """
    if request.method == 'OPTIONS':
        return '', 204
    
    try:
        data = request.get_json()
        package = data.get('package', '').strip()
        
        if not package:
            return jsonify({
                'success': False,
                'output': '',
                'errors': 'No package name provided'
            })
        
        # Basic validation to prevent command injection
        # Only allow alphanumeric, hyphens, underscores, dots, and brackets
        import re
        if not re.match(r'^[a-zA-Z0-9\-_.[\]]+$', package):
            return jsonify({
                'success': False,
                'output': '',
                'errors': 'Invalid package name. Only alphanumeric characters, hyphens, underscores, dots, and brackets are allowed.'
            })
        
        # Execute pip install
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'install', package],
            capture_output=True,
            text=True,
            timeout=120  # 2 minute timeout for installation
        )
        
        return jsonify({
            'success': result.returncode == 0,
            'output': result.stdout,
            'errors': result.stderr
        })
    
    except subprocess.TimeoutExpired:
        return jsonify({
            'success': False,
            'output': '',
            'errors': 'Installation timeout: Package installation took longer than 120 seconds'
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'output': '',
            'errors': f'Server error: {str(e)}'
        })

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'python_version': sys.version,
        'timestamp': time.time()
    })

@app.route('/', methods=['GET'])
def index():
    """Root endpoint with API information"""
    return jsonify({
        'name': 'Python AI Runner Backend',
        'version': '1.0.0',
        'endpoints': {
            '/api/run': 'POST - Execute Python code',
            '/api/install': 'POST - Install pip package',
            '/api/health': 'GET - Health check'
        },
        'documentation': 'See README.md for usage instructions'
    })

if __name__ == '__main__':
    print("=" * 60)
    print("Python AI Runner Backend Server")
    print("=" * 60)
    print(f"Python version: {sys.version}")
    print(f"Server starting on http://0.0.0.0:5000")
    print("=" * 60)
    print("\nEndpoints:")
    print("  POST /api/run      - Execute Python code")
    print("  POST /api/install  - Install pip package")
    print("  GET  /api/health   - Health check")
    print("\nPress Ctrl+C to stop the server")
    print("=" * 60)
    
    # Run development server
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True,
        threaded=True
    )