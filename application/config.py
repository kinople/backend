import os
import flask_sqlalchemy
basedir = os.path.abspath(os.path.dirname(__file__))

class Config():
    DEBUG = False
    SQLITE_DB_DIR = None
    SQLALCHEMY_DATABASE_URI = None
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

class TestingConfig():
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = "postgresql://kinople_admin:kinople368" + "@test-db.covwckoemdp4.us-east-1.rds.amazonaws.com/kinopletest1"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.environ.get('SECRET_KEY', 'testing-secret-key-12345')

class LocalDevelopmentConfig():
    SQLITE_DB_DIR = os.path.join(basedir, "../db_directory")
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(SQLITE_DB_DIR, "local_testing")
    DEBUG = True
    SECRET_KEY = os.environ.get('SECRET_KEY', 'local-dev-secret-key-67890')