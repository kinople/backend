import os
from flask_cors import CORS
from flask import Flask
from application.config import LocalDevelopmentConfig, TestingConfig
from application.database import db

def create_app():
	app = Flask(__name__)
	
	# Use environment variables for configuration
	if os.environ.get('FLASK_ENV') == 'local':
		app.config.from_object(LocalDevelopmentConfig)
	else:
		app.config.from_object(TestingConfig)
	
	# Session cookie configuration for cross-site support
	app.config.update(
		SESSION_COOKIE_SECURE=True,  # Requires HTTPS
		SESSION_COOKIE_SAMESITE='None',  # Allows cross-site cookies
		SESSION_COOKIE_HTTPONLY=True,  # Prevents XSS attacks
		SESSION_COOKIE_DOMAIN=None,  # Let Flask handle domain automatically
		PERMANENT_SESSION_LIFETIME=86400,  # 24 hours in seconds
		SESSION_PERMANENT=False  # Session expires when browser closes
	)
	
	db.init_app(app)
	app.app_context().push()
	
	# Configure CORS with proper credentials support
	cors_origin = os.environ.get('CORS_ALLOWED_ORIGINS', 'https://kinople.github.io')
	CORS(app, 
		supports_credentials=True,
		origins=[cors_origin],
		allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
		expose_headers=["Content-Length", "Content-Range"],
		methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"]
	)
	
	return app

app = create_app()

from application.views import *

if __name__ == "__main__":
	# Get port from environment variable or default to 5000
	port = int(os.environ.get('PORT', 5000))
	# In production, we want to bind to localhost only
	host = '127.0.0.1' if os.environ.get('FLASK_ENV') == 'production' else '0.0.0.0'
	app.run(host=host, port=port)
