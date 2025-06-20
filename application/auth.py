import jwt
import datetime
import os
from flask import request, jsonify, current_app
from functools import wraps

def get_secret_key():
    """Get the secret key from Flask app config or environment variable"""
    if current_app:
        return current_app.config.get('SECRET_KEY')
    return os.environ.get('SECRET_KEY', 'fallback-secret-key')

def generate_token(user_id):
    payload = {
        'user_id': user_id,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    }
    return jwt.encode(payload, get_secret_key(), algorithm='HS256')

def decode_token(token):
    try:
        return jwt.decode(token, get_secret_key(), algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Unauthorized'}), 401

        token = auth_header.split(' ')[1]
        decoded = decode_token(token)
        if not decoded:
            return jsonify({'error': 'Invalid or expired token'}), 401

        request.user_id = decoded['user_id']
        return f(*args, **kwargs)
    return decorated
