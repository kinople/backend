import os
from flask_cors import CORS
from flask import Flask, request, jsonify
from application.config import LocalDevelopmentConfig, TestingConfig
from application.database import db

def create_app():
	app = Flask(__name__)
	app.config.from_object(TestingConfig)
	db.init_app(app)
	app.app_context().push()
	# Simplified CORS - let manual headers handle the details
	CORS(app)
	return app

app = create_app()

from application.views import *

if(__name__ == "__main__"):
    app.run(debug = True, host='0.0.0.0', port=5000)

