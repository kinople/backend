from .database import db
from sqlalchemy.dialects.postgresql import JSONB

class Projects(db.Model):
	__tablename__ = 'projects'
	project_id = db.Column(db.Integer, autoincrement=True, primary_key=True)
	projectname = db.Column(db.String, unique=True)
	projecttype = db.Column(db.String)
	createtime = db.Column(db.String)
	deletetime = db.Column(db.String)
	castlist = db.Column(JSONB)
	locationlist = db.Column(JSONB)
	schedules = db.Column(JSONB)
	users = db.relationship("Users", secondary="project_users", back_populates="projects")
	
class Users(db.Model):
	__tablename__ = 'users'
	user_id = db.Column(db.Integer, autoincrement=True, primary_key=True)
	username = db.Column(db.String, unique=True)
	password = db.Column(db.String)
	projects = db.relationship("Projects", secondary="project_users", back_populates="users")

class Project_Users(db.Model):
	__tablename__ = 'project_users'
	user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), primary_key=True, nullable=False)
	project_id = db.Column(db.Integer, db.ForeignKey("projects.project_id"), primary_key=True, nullable=False)

class Scripts(db.Model):
	__tablename__ = 'scripts'
	script_id = db.Column(db.Integer, autoincrement=True, primary_key=True)
	project_id = db.Column(db.Integer, db.ForeignKey("projects.project_id"), nullable = False)
	scriptname = db.Column(db.String)
	script = db.Column(db.String)
	breakdown = db.Column(JSONB)
	uploadtime = db.Column(db.String)
	parsing = db.Column(db.String)
