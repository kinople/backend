from local_run import app
import os
import boto3
from flask import request, jsonify, send_file, Response, session
from application.database import db
from application.models import Projects, Scripts, Users, Project_Users
from datetime import datetime
from application.generateBreakdown import *
from application.scriptParsing import *
import tempfile
from application.auth import generate_token, login_required, decode_token
from application.generateBreakdownGemini import *

# Add CORS headers to all responses
@app.after_request
def after_request(response):
    origin = request.headers.get('Origin')
    allowed_origins = ["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173", "http://127.0.0.1:3000"]
    
    if origin in allowed_origins:
        response.headers.add('Access-Control-Allow-Origin', origin)
    else:
        response.headers.add('Access-Control-Allow-Origin', 'http://localhost:5173')
    
    response.headers.add('Access-Control-Allow-Credentials', 'true')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization,X-Requested-With,Accept,Origin')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,PUT,DELETE,OPTIONS')
    return response

# Simple test endpoint
@app.route('/api/test', methods=['GET', 'OPTIONS'])
def test_cors():
    if request.method == 'OPTIONS':
        return '', 200
    return jsonify({'message': 'CORS test successful'}), 200

# AWS S3
S3_BUCKET = os.environ.get('S3_BUCKET_NAME', 'kinople-storage-2025')
s3 = boto3.client('s3')

# At the top of the file, add base_dir
base_dir = os.path.abspath(os.path.dirname(__file__))
PROJECTS_FOLDER = os.path.join(base_dir, './../projects')
UPLOAD_FOLDER = 'uploads'
BREAKDOWN_FOLDER = 'breakdown'
SCHEDULE_FOLDER = 'schedule'
CALL_SHEET_FOLDER = 'call-sheets'

ALLOWED_EXTENSIONS = {'pdf'}

# --- Helper Function ---
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/api/user/<user_id>', methods=['GET'])
@login_required
def get_user(user_id):
    user = Users.query.get(user_id)
    if user:
        return jsonify({
            'email': user.username
        })

@app.route('/api/project-name/<id>', methods=['GET'])
@login_required
def get_project_name(id):
    try:
        project = Projects.query.get(id)
        if project:
            return jsonify({
                'projectName': project.projectname,
                'projectType': project.projecttype
            }), 200
        else:
            return jsonify({'message': 'Project not found'}), 404
    except Exception as e:
        print(f"Error fetching project name: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/projects/<user_id>', methods=['GET'])
@login_required
def get_projects(user_id):
    try:
        # Check if the requesting user is aditya@kinople.com
        user = Users.query.get(user_id)
        if user and user.username == 'aditya@kinople.com':
            # Show all projects for aditya@kinople.com
            projects = Projects.query.all()
        else:
            # For other users, get only their associated projects
            projects = db.session.query(Projects)\
                .join(Project_Users, Projects.project_id == Project_Users.project_id)\
                .filter(Project_Users.user_id == user_id)\
                .all()
        
        projects_list = [{
            'id': project.project_id,
            'projectName': project.projectname,
            'projectType': project.projecttype,
            'createTime': project.createtime,
            'deleteTime': project.deletetime
        } for project in projects]
        
        return jsonify(projects_list), 200
    except Exception as e:
        print(f"Error fetching projects: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/<id>/script-list', methods=['GET'])
def script_list(id):
    try:
        # Query all scripts for the given project_id
        scripts = Scripts.query.filter_by(project_id=id).order_by(Scripts.uploadtime.desc()).all()
        
        # Format the response
        script_list = [{
            'name': script.scriptname,
            'version': len(scripts) - i  # Version number based on position in sorted list
        } for i, script in enumerate(scripts)]
        
        return jsonify(script_list), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/<id>/upload-script', methods=['POST'])
def upload_script(id):
    if request.method == 'POST':
        if 'scriptPdf' not in request.files:
            return jsonify({'message': 'No file part in the request'}), 400

        file = request.files['scriptPdf']

        if file.filename == '':
            return jsonify({'message': 'No selected file'}), 400
        
        upload_path = os.path.join(PROJECTS_FOLDER, id, UPLOAD_FOLDER)
        if not os.path.exists(upload_path):
            os.makedirs(upload_path)

        if file and allowed_file(file.filename):
            # Sanitize the filename
            filename = request.form['fileName']
            save_path = os.path.join(PROJECTS_FOLDER, id, UPLOAD_FOLDER, filename)

            try:                
                # Upload to S3
                s3_key = f"{id}/uploads/{filename}"
                s3.upload_fileobj(
                    file,
                    S3_BUCKET,
                    s3_key
                )
                
                # Create new entry in Scripts table
                new_script = Scripts(
                    project_id=id,
                    scriptname=filename,
                    script=s3_key,  # Store the S3 key
                    breakdown={},  # Empty JSONB object for breakdown
                    uploadtime=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    parsing = ""
                )
                
                # Add to database
                db.session.add(new_script)
                db.session.commit()
                
                return jsonify({
                    'message': 'File uploaded successfully',
                    'filename': filename
                }), 200
            except Exception as e:
                db.session.rollback()  # Rollback in case of database error
                print(f"Error saving file or database entry: {e}")
                return jsonify({'message': 'Failed to save file or database entry'}), 500
        else:
            return jsonify({'message': 'Invalid file type. Only PDFs are allowed.'}), 400

@app.route('/api/<id>/script-view/<filename>', methods=['GET'])
def script_view(id, filename):
    try:
        # Query the script from database
        script = Scripts.query.filter_by(
            project_id=id,
            scriptname=filename
        ).first()
        
        if not script:
            print("Script not found in database")
            return jsonify({'message': 'Script not found in database'}), 404
        
        s3_key = script.script  # This is the S3 key stored in the database
        
        try:
            # Generate a presigned URL for the S3 object
            presigned_url = s3.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': S3_BUCKET,
                    'Key': s3_key,
                    'ResponseContentType': 'application/pdf'
                },
                ExpiresIn=3600  # URL expires in 1 hour
            )
            
            # Return the presigned URL
            return jsonify({
                'url': presigned_url,
                'filename': filename
            }), 200
            
        except Exception as e:
            print(f"Error generating presigned URL: {e}")
            return jsonify({'message': 'Error accessing file from S3'}), 500
            
    except Exception as e:
        print(f"Error in script_view: {e}")
        return jsonify({'message': 'Error accessing script'}), 500

@app.route('/api/<id>/generate-breakdown/<filename>', methods=['POST'])
def generate_breakdown(id, filename):
    try:
        # Query the script from database
        script = Scripts.query.filter_by(
            project_id=id,
            scriptname=filename
        ).first()
        
        if not script:
            return jsonify({'message': 'Script not found in database'}), 404
        
        # Get the S3 key from the database
        s3_key = script.script
        
        try:
            # Get the file from S3
            s3_response = s3.get_object(Bucket=S3_BUCKET, Key=s3_key)
            file_content = s3_response['Body'].read()
            
            # Create a temporary file to store the PDF content
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                temp_file.write(file_content)
                temp_file_path = temp_file.name
            
            try:
                # Read the script file and get parsed scenes
                scenes = extract_text_from_pdf(temp_file_path, id)
                
                # Update the script's parsing field in the database
                script.parsing = str(scenes)
                
                # Extract characters from the script using the parsing data
                characters = extract_characters_from_script_2(script.parsing)
                
                # Generate breakdown for each scene
                scene_breakdowns = []
                counter = 1
                for scene in scenes:
                    scene_text = f"{scene['heading']}\n{scene['content']}"
                    breakdown = generate_scene_breakdown_gemini(scene_text, characters, counter)
                    counter = counter + 1
                    if breakdown:
                        scene_breakdowns.append(breakdown)
                
                # Update the breakdown in the database
                script.breakdown = {
                    'scenes': len(scene_breakdowns),
                    'characters': characters,
                    'scene_breakdowns': scene_breakdowns,
                    'last_updated': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                
                # Force truly synchronous database operations
                try:
                    # First flush to send the changes to the database
                    db.session.flush()
                    # Then commit to make the transaction permanent
                    db.session.commit()
                    
                    # Force a new query to verify the data was actually saved
                    # This creates a new database connection and query
                    verification_script = Scripts.query.filter_by(
                        project_id=id,
                        scriptname=filename
                    ).first()
                    
                    # Check if the breakdown was actually saved
                    if (verification_script and 
                        verification_script.breakdown and 
                        isinstance(verification_script.breakdown, dict) and
                        'scene_breakdowns' in verification_script.breakdown and
                        len(verification_script.breakdown['scene_breakdowns']) == len(scene_breakdowns)):
                        
                        print(f"Breakdown successfully committed and verified for script: {script.scriptname}")
                        print(f"Verified {len(verification_script.breakdown['scene_breakdowns'])} scene breakdowns in database")
                        
                        return jsonify({
                            'message': 'Breakdown Generated',
                            'scenes_processed': len(scene_breakdowns),
                            'characters_found': len(characters)
                        }), 200
                    else:
                        print(f"Breakdown commit verification failed for script: {script.scriptname}")
                        print(f"Expected {len(scene_breakdowns)} scenes, found {len(verification_script.breakdown.get('scene_breakdowns', [])) if verification_script and verification_script.breakdown else 0}")
                        return jsonify({'message': 'Error verifying breakdown save to database'}), 500
                        
                except Exception as commit_error:
                    db.session.rollback()
                    print(f"Error committing breakdown to database: {commit_error}")
                    return jsonify({'message': 'Error saving breakdown to database'}), 500
                
                
                
            finally:
                # Clean up the temporary file
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
                    
        except Exception as e:
            print(f"Error reading file from S3: {e}")
            return jsonify({'message': 'Error reading file from S3'}), 500
            
    except Exception as e:
        db.session.rollback()
        print(f"Error generating breakdown: {e}")
        return jsonify({'message': 'Error generating breakdown'}), 500

@app.route('/api/<id>/fetch-breakdown', methods=['GET'])
def fetch_breakdown(id):
    try:
        # Query the script from database
        script = Scripts.query.filter_by(project_id=id).order_by(Scripts.uploadtime.desc()).first()
        
        if not script:
            return jsonify({'message': 'No script found for this project'}), 404
        
        # More specific check for breakdown availability
        if script.breakdown is None:
            return jsonify({'message': 'No breakdown available for this script - breakdown is None'}), 404
        
        if not isinstance(script.breakdown, dict):
            return jsonify({'message': 'Invalid breakdown format in database'}), 404
        
        if 'scene_breakdowns' not in script.breakdown:
            return jsonify({'message': 'No scene breakdowns found in breakdown data'}), 404
        
        scene_breakdowns = script.breakdown.get('scene_breakdowns', [])
        if not scene_breakdowns:
            return jsonify({'message': 'Scene breakdowns list is empty'}), 404
        
        # Create TSV content from the breakdown data
        tsv_content = "Scene Number\tInt./Ext.\tLocation\tTime\tSynopsis\tCharacters\tAction Props\tOther Props\tPicture Vehicles\tAnimals\tExtras\tWardrobe\tSet Dressing\n"
        
        # Add each scene breakdown
        for i, breakdown in enumerate(scene_breakdowns):
            tsv_content += f"{breakdown}\n"
        
        # Return the TSV content directly
        return jsonify({
            'tsv_content': tsv_content,
            'filename': f'breakdown_{script.scriptname}.tsv'
        }), 200
    except Exception as e:
        print(f"Error fetching breakdown: {e}")
        return jsonify({'message': f'Error accessing breakdown: {str(e)}'}), 500

@app.route('/api/<id>/update-breakdown', methods=['POST', 'OPTIONS'])
def update_breakdown(id):
    # Handle OPTIONS request for CORS preflight
    if request.method == 'OPTIONS':
        return '', 200
        
    try:
        data = request.get_json()
        
        if not data or 'tsv_content' not in data:
            return jsonify({'message': 'Missing tsv_content in request'}), 400
        
        tsv_content = data['tsv_content']
        print(f"Received TSV content length: {len(tsv_content)}")
        
        # Query the most recent script for this project
        script = Scripts.query.filter_by(project_id=id).order_by(Scripts.uploadtime.desc()).first()
        
        if not script:
            return jsonify({'message': 'No script found for this project'}), 404
        
        # Parse the TSV content back into breakdown format
        # Split by lines and skip the header
        lines = tsv_content.strip().split('\n')
        if len(lines) < 2:  # Header + at least one data line
            return jsonify({'message': 'Invalid TSV content format'}), 400
        
        # Skip the header line and process the data lines
        scene_breakdowns = []
        for line in lines[1:]:  # Skip header
            if line.strip():  # Skip empty lines
                scene_breakdowns.append(line.strip())
        
        # Preserve existing breakdown structure and only update specific fields
        if script.breakdown is None:
            script.breakdown = {}
        
        # Preserve existing characters and other important data
        existing_characters = script.breakdown.get('characters', [])
        
        # Create a new breakdown dictionary (important for JSONB updates)
        new_breakdown = {
            'scenes': len(scene_breakdowns),
            'characters': existing_characters,  # Preserve existing characters
            'scene_breakdowns': scene_breakdowns,
            'last_updated': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Assign the new breakdown (this ensures SQLAlchemy detects the change)
        script.breakdown = new_breakdown
        
        # Mark the field as modified explicitly (important for JSONB)
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(script, 'breakdown')
        # Commit the changes
        db.session.commit()
        
        # Verify the update
        updated_script = Scripts.query.filter_by(project_id=id).order_by(Scripts.uploadtime.desc()).first()
        
        return jsonify({
            'message': 'Breakdown updated successfully',
            'scenes_updated': len(scene_breakdowns),
            'characters_preserved': len(existing_characters)
        }), 200
        
    except Exception as e:
        db.session.rollback()
        print(f"Error updating breakdown: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'message': 'Error updating breakdown'}), 500

@app.route('/api/login', methods=['POST', 'OPTIONS'])
def login():
    # Handle OPTIONS request for CORS preflight
    if request.method == 'OPTIONS':
        return '', 200
        
    try:
        data = request.get_json()
        
        if not data or 'email' not in data or 'password' not in data:
            return jsonify({'message': 'Missing email or password'}), 400
        
        user = Users.query.filter_by(username=data['email']).first()
        
        if user and user.password == data['password']:
            token = generate_token(user.user_id)
            
            return jsonify({
                'message': 'Login successful',
                'token': token,
                'user': {
                    'id': user.user_id,
                    'username': user.username
                }
            }), 200
        else:
            return jsonify({'message': 'Invalid username or password'}), 401
            
    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({'message': 'Login failed'}), 500

@app.route('/api/logout', methods=['POST'])
def logout():
    try:
        session.clear()  # Clear all data from the session
        return jsonify({'message': 'Logout successful'}), 200
    except Exception as e:
        print(f"Logout error: {e}")
        return jsonify({'message': 'Logout failed'}), 500

@app.route('/api/signup', methods=['POST'])
def signup():
    try:
        data = request.get_json()
        
        if not data or 'email' not in data or 'password' not in data:
            return jsonify({'message': 'Missing email or password'}), 400
        
        email = data['email'].strip()
        password = data['password']
        
        # Validate email format (basic validation)
        if '@' not in email or '.' not in email:
            return jsonify({'message': 'Invalid email format'}), 400
        
        # Check if user already exists
        existing_user = Users.query.filter_by(username=email).first()
        if existing_user:
            return jsonify({'message': 'User with this email already exists'}), 409
        
        
        # Create new user
        new_user = Users(
            username=email,
            password=password
        )
        
        # Add to database
        db.session.add(new_user)
        db.session.commit()
        
        return jsonify({
            'message': 'User created successfully',
            'user': {
                'id': new_user.user_id,
                'username': new_user.username
            }
        }), 201
        
    except Exception as e:
        db.session.rollback()  # Rollback in case of database error
        print(f"Signup error: {e}")
        return jsonify({'message': 'Signup failed'}), 500

@app.route('/api/verify-token', methods=['GET'])
def verify_token():
    try:
        # Get token from Authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'authenticated': False, 'message': 'No token provided'}), 401

        token = auth_header.split(' ')[1]
        decoded = decode_token(token)
        
        if not decoded:
            return jsonify({'authenticated': False, 'message': 'Invalid or expired token'}), 401
        
        # Get user from database to ensure they still exist
        user = Users.query.get(decoded['user_id'])
        if not user:
            return jsonify({'authenticated': False, 'message': 'User not found'}), 401
        
        return jsonify({
            'authenticated': True,
            'user': {
                'id': user.user_id,
                'username': user.username
            }
        }), 200
            
    except Exception as e:
        print(f"Token verification error: {e}")
        return jsonify({'authenticated': False, 'message': 'Token verification failed'}), 500

@app.route('/api/create-project/<user_id>', methods=['POST'])
def create_project(user_id):
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data or 'projectName' not in data or 'projectType' not in data:
            return jsonify({'message': 'Missing required fields'}), 400
        
        project_name = data['projectName'].strip()
        project_type = data['projectType'].strip()
        
        # Check if project name already exists
        existing_project = Projects.query.filter_by(projectname=project_name).first()
        if existing_project:
            return jsonify({'message': 'Project with this name already exists'}), 409
        
        # Create new project
        new_project = Projects(
            projectname=project_name,
            projecttype=project_type,
            createtime=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            deletetime=None,
            castlist={},
            locationlist={},
            schedules={}
        )
        
        # Add project to database
        db.session.add(new_project)
        db.session.flush()  # This will populate the project_id
        
        
        # Create Project_Users association
        project_user = Project_Users(
            user_id=user_id,
            project_id=new_project.project_id
        )
        db.session.add(project_user)
        
        # If the creator is not aditya@kinople.com, also add aditya@kinople.com as a user
        creator = Users.query.get(user_id)
        if creator and creator.username != 'aditya@kinople.com':
            admin_user = Users.query.filter_by(username='aditya@kinople.com').first()
            if admin_user:
                admin_project_user = Project_Users(
                    user_id=admin_user.user_id,
                    project_id=new_project.project_id
                )
                db.session.add(admin_project_user)
        
        # Commit all changes
        db.session.commit()
        
        return jsonify({
            'message': 'Project created successfully',
            'project': {
                'id': new_project.project_id,
                'projectName': new_project.projectname,
                'projectType': new_project.projecttype,
                'createTime': new_project.createtime,
                'deleteTime': new_project.deletetime
            }
        }), 201
        
    except Exception as e:
        db.session.rollback()  # Rollback in case of database error
        print(f"Project creation error: {e}")
        return jsonify({'message': 'Failed to create project'}), 500

@app.route('/api/projects/<id>/team', methods=['GET'])
def get_team(id):
    try:
        project = Projects.query.get(id)
        if not project:
            return jsonify({'message': 'Project not found'}), 404
        
        # Get all users associated with the project
        users = db.session.query(Users)\
            .join(Project_Users, Users.user_id == Project_Users.user_id)\
            .filter(Project_Users.project_id == id)\
            .all()
        
        # Format the response
        team_list = [{
            'id': user.user_id,
            'username': user.username
        } for user in users if user.username != 'aditya@kinople.com']

        if team_list == []:
            return jsonify({'message': 'No team members found', 'users': users}), 404
        
        return jsonify(team_list), 200
    except Exception as e:
        print(f"Error fetching team: {e}")
        return jsonify({'message': 'Error fetching team'}), 500

@app.route('/api/projects/<id>/team/<user_name>', methods=['POST'])
def add_team_member(id, user_name):
    try:
        # Check if the project exists
        project = Projects.query.get(id)
        if not project:
            return jsonify({'message': 'Project not found'}), 404
        
        user = Users.query.filter_by(username=user_name).first()
        if not user:
            return jsonify({'message': 'User not found'}), 404
        
        # Add the user to the project
        project_user = Project_Users(
            user_id=user.user_id,
            project_id=id
        )
        db.session.add(project_user)
        db.session.commit()
        
        return jsonify({'message': 'Team member added successfully'}), 200  
    except Exception as e:
        db.session.rollback()  # Rollback in case of database error
        print(f"Error adding team member: {e}")
        return jsonify({'message': 'Failed to add team member'}), 500
    