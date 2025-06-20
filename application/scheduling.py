import os
from datetime import datetime
import time
from ortools.sat.python import cp_model

base_dir = os.path.abspath(os.path.dirname(__file__))
PROJECTS_FOLDER = os.path.join(base_dir, './../projects')
UPLOAD_FOLDER = 'uploads'
BREAKDOWN_FOLDER = 'breakdown'
SCHEDULE_FOLDER = 'schedule'

def create_schedule_file(schedule_folder, id, name, location):
    model = cp_model.CpModel()
    schedule_path = os.path.join(schedule_folder, f'{name}.schedule.tsv')
    cast_path = os.path.join(PROJECTS_FOLDER, id, BREAKDOWN_FOLDER, 'cast_list.tsv')
    location_path = os.path.join(PROJECTS_FOLDER, id, BREAKDOWN_FOLDER, 'location_list.tsv')
    location_options_path = os.path.join(PROJECTS_FOLDER, id, SCHEDULE_FOLDER, 'location_options.tsv')
    cast_options_path = os.path.join(PROJECTS_FOLDER, id, SCHEDULE_FOLDER, 'cast_options.tsv')
    scene_data = {}
    location_ids = []
    cast_ids = []
    cast_options_list = []
    with open(cast_options_path, 'r') as f:
        lines = f.readlines()
        for line in lines:
            cast_options_list.append(line.split('\t')[0])
    with open(location_path, 'r') as f:
        location_list = f.readlines()
        for line in location_list:
            if line.split('\t')[1] == location:
                scenes = line.split('\t')[5].split(',')
                location_ids.append(line.split('\t')[0])
                for scene in scenes:
                    scene_data[scene] = {'actors': [], 'location': line.split('\t')[0]}
                break
    with open(cast_path, 'r') as f:
        cast_list = f.readlines()
        for line in cast_list:
            char_scenes = line.split('\t')[3].split(',')
            for scene in scenes:
                if scene in char_scenes and line.split('\t')[0] in cast_options_list:
                    scene_data[scene]['actors'].append(line.split('\t')[0])
                    if line.split('\t')[0] not in cast_ids:
                        cast_ids.append(line.split('\t')[0])
    location_availability = {}
    actor_availability = {}
    start_date = datetime.strptime('4/21/2025', '%m/%d/%Y')
    stop_date = datetime.strptime('4/25/2025', '%m/%d/%Y')
    days = range(1, (stop_date - start_date).days + 2)
    with open(location_options_path, 'r') as f:
        location_options = f.readlines()
        for line in location_options:
            if line.split('\t')[0] in location_ids:
                dates = line.split('\t')[3].split(',')
                days_list = []
                for date in dates:
                    result = convert_date_to_day(date, start_date, stop_date)
                    if isinstance(result, list):
                        days_list.extend(result)  # If it's a list (No Constraint case)
                    else:
                        days_list.append(result)  # If it's a single number
                location_availability[line.split('\t')[0]] = set(days_list)  # Convert to set at the end
    with open(cast_options_path, 'r') as f:
        cast_options = f.readlines()
        for line in cast_options:
            if line.split('\t')[0] in cast_ids:
                dates = line.split('\t')[3].split(',')
                days_list = []
                for date in dates:
                    result = convert_date_to_day(date, start_date, stop_date)
                    if isinstance(result, list):
                        days_list.extend(result)
                    else:
                        days_list.append(result)
                actor_availability[line.split('\t')[0]] = set(days_list)
    max_scenes_per_day = 7

    scene_vars = {}
    for s in scenes:
        scene_vars[s] = model.NewIntVar(1, 5, f"day_{s}")

    for s in scenes:
        allowed_days = set(days)
        for actor in scene_data[s]['actors']:
            allowed_days &= actor_availability[actor]
        model.AddAllowedAssignments([scene_vars[s]], [ [d] for d in allowed_days ])

    for s in scenes:
        loc = scene_data[s]['location']
        allowed_days = location_availability[loc]
        model.AddAllowedAssignments([scene_vars[s]], [ [d] for d in allowed_days ])

    day_used = {}
    for d in days:
        bools = []
        for s in scenes:
            b = model.NewBoolVar(f"{s}_on_day_{d}")
            model.Add(scene_vars[s] == d).OnlyEnforceIf(b)
            model.Add(scene_vars[s] != d).OnlyEnforceIf(b.Not())
            bools.append(b)
        # Limit scenes per day
        model.Add(sum(bools) <= max_scenes_per_day)

        # Create day usage indicator
        y = model.NewBoolVar(f"use_day_{d}")
        model.AddMaxEquality(y, bools)  # y=1 iff any scene on day d
        day_used[d] = y

    model.Minimize(sum(day_used[d] for d in days))

    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        print(f"Total shoot days used: {sum(solver.Value(day_used[d]) for d in days)}")
        # Create dictionary of scene assignments
        scene_assignments = {s: solver.Value(scene_vars[s]) for s in scenes}
        
        # Get actor schedules
        actor_schedule = get_actor_schedule(scene_data, scene_assignments)
        
        # Print actor schedules with actual dates
        print("\nActor Schedules:")
        new_cast_options_lines = []
        with open(cast_options_path, 'r') as f:
            lines = f.readlines()
            new_cast_options_lines = []
            for line in lines:
                if line.split('\t')[0] in actor_schedule.keys():
                    new_dates = ''
                    for actor_id, days in actor_schedule.items():
                        if(actor_id == line.split('\t')[0]):
                            dates = [convert_day_to_date(day, start_date) for day in sorted(days)]
                            print(f"Actor {actor_id} works on: {', '.join(dates)}")
                            new_dates = ', '.join(dates)
                    new_cast_options_lines.append(line.split('\t')[0] + '\t' + line.split('\t')[1] + '\t' + line.split('\t')[2] + '\t' + new_dates + '\n')
                else:
                    new_cast_options_lines.append(line)
            
        with open(cast_options_path, 'w') as f:
            print(new_cast_options_lines)
            for line in new_cast_options_lines:
                f.write(line)
        with open(schedule_path, 'w') as f:
            f.write(f"Location - {location}\n")
            f.write("Date\tScene Number\tINT/EXT\tDay/Night\tLocation\tSynopsis\tCast ID\tPages\n")
            for s in scenes:
                day = solver.Value(scene_vars[s])
                date = convert_day_to_date(day, start_date)
                f.write(f"{date}\t{s}\tINT/EXT\tDAY/NIGHT\t{scene_data[s]['location']}\tSynopsis\t{scene_data[s]['actors']}\t\n")
    
    else:
        print("No feasible schedule found.")
    return True

def convert_date_to_day(date_str, start_date, end_date):
    date_str = date_str.strip()  # Remove whitespace
    difference = end_date - start_date
    if date_str == 'No Constraint':
        # Return a list of numbers instead of a set
        return list(range(1, difference.days + 2))
    else:
        date = datetime.strptime(date_str, '%m/%d/%Y')
        difference = date - start_date
        return difference.days + 1

def convert_day_to_date(day_number, start_date):
    from datetime import timedelta
    result_date = start_date + timedelta(days=day_number - 1)
    return result_date.strftime('%m/%d/%Y')

def get_actor_schedule(scene_data, scene_assignments):
    actor_schedule = {}
    
    # Go through each scene and its assigned day
    for scene, day in scene_assignments.items():
        # Get all actors in this scene
        actors = scene_data[scene]['actors']
        # Add the day to each actor's schedule
        for actor in actors:
            if actor not in actor_schedule:
                actor_schedule[actor] = set()
            actor_schedule[actor].add(day)
    
    return actor_schedule