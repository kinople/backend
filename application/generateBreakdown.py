from openai import OpenAI
import os
import ast

def generate_scene_breakdown(script_text, characters, counter):
    # Initialize OpenAI client
    client = OpenAI(api_key="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")
    
    # Create the system prompt
    system_prompt = """You are an assistant director, and you're given this scene to break it down into all the elements present in it.
    Analyze this scene, and list the following elements present in it:
    1. Scene Number : Scene number as present in the slugline (scene heading). This should be a number and not 'INT.' or  'EXT.'
    2. Int./Ext. : INT. or EXT. or INT./EXT or EXT./INT. or I/E. or E/I as present in the slugline.
    3. Location : Location as exactly mentioned in the slugline. Do not include INT/EXT here.
    4. Time : Time of the day as mentioned in the slugline (Day/Night/Morning/Evening)
    5. Synopsis : A one-line summary of the scene in not more than 10-15 words.
    6. Characters : All principal characters involved in the scene. Do not include extras here. Return this as a comma separated list and each character should be in full CAPS.
    7. Action Props : Main props that are actively used by characters in the script.
    8. Other Props : Props other than action props
    9. Picture Vehicles : Any type of vehicles to be used in the scene.
    10. Animals : Animals to be used in the scene.
    11. Extras : Background actors to be arranged on shoot day, if any.
    12. Wardrobe: Any costume elements of characters present in the script, if any.
    13. Set Dressing : Elements required to design the set for filming the scene, other than props and vehicles, if any.
    Format the output in TSV (tab-separated values) with the following columns but do not output the heading. Just return the TSV in this exact format and nothing else, not even quotes:
    Scene Number\tInt./Ext.\tLocation\tTime\tSynopsis\tCharacters\tAction Props\tOther Props\tPicture Vehicles\tAnimals\tExtras\tWardrobe\tSet Dressing"""

    # Create the user prompt
    user_prompt = f"Please analyze this script text and provide a scene breakdown:\n{script_text}. Here are the characters present in this script:\n{characters}. If scene number is not there(it is usually lesser than 300), then {counter} is the scene number."

    try:
        # Call the OpenAI API
        response = client.chat.completions.create(
            model="gpt-4.5-preview-2025-02-27", 
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=2000
        )
        
        # Extract and return the breakdown
        breakdown = response.choices[0].message.content
        return breakdown

    except Exception as e:
        print(f"Error generating breakdown: {str(e)}")
        return None
    
def extract_characters_from_script(id):
    characters = []
    if not os.path.exists(f'projects/{id}/breakdown/breakdown.tsv') > 0:
        return []
    with open(f'projects/{id}/breakdown/breakdown.tsv') as scenes_data:
        while True:
            line = scenes_data.readline()
            if not line:
                break
            characters.append(line.split('\t')[6])
    characters = list(set(characters))
    return characters

def extract_characters_from_script_2(script_parsing):
    try:
        # Convert the string representation of scenes back to a list of dictionaries
        scenes = ast.literal_eval(script_parsing)
        
        # Combine all scene content
        all_content = ""
        for scene in scenes:
            all_content += f"{scene['heading']}\n{scene['content']}\n"
        
        # Initialize OpenAI client
        client = OpenAI(api_key="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")
        
        system_prompt = """You are an assistant director. Your job is to extract the characters from the script.
        The script is given line by line. You need to extract all the different characters from the content and return them as a comma separated list.
        Do not include any other text in your response."""
        
        response = client.chat.completions.create(
            model="gpt-4.5-preview-2025-02-27",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": all_content}
            ],
            temperature=0.7,
            max_tokens=2000
        )
        
        characters = response.choices[0].message.content
        characters = characters.split(',')
        characters = [character.strip().upper() for character in characters]
        characters = list(set(characters))
        return characters
    except Exception as e:
        print(f"Error extracting characters: {e}")
        return []

def generate_cast_list(breakdown_path, cast_path):
    cast_dict = {}
    with open(breakdown_path, 'r') as f:
        lines = f.readlines()
        for i, line in enumerate(lines):
            if i == 0:
                continue
            breakdown = line.split('\t')
            characters = breakdown[6].split(',')
            for character in characters:
                character = character.strip()
                character = character.upper()
                if character not in cast_dict:
                    cast_dict[character] = []
                cast_dict[character].append(breakdown[1])
    f.close()
    with open(cast_path, 'w') as f:
        f.write("Cast ID\tCharacter\tNumber of Scenes\tScene Numbers\tLocked\n")
        counter = 0
        cast_list = list(cast_dict.keys())
        n = len(cast_list)
        for i in range(n-1):
            for j in range(n-i-1):
                if len(cast_dict[cast_list[j]]) < len(cast_dict[cast_list[j+1]]):
                    cast_list[j], cast_list[j+1] = cast_list[j+1], cast_list[j]
        for character in cast_list:
            if(character == ""):
                continue
            f.write(f"{counter}\t{character}\t{len(cast_dict[character])}\t{','.join(cast_dict[character])}\tFalse\n")
            counter = counter + 1
        f.close()
    return cast_list

def generate_location_list(breakdown_path, location_path):
    location_dict = {}
    with open(breakdown_path, 'r') as f:
        lines = f.readlines()
        for i, line in enumerate(lines):
            if i == 0:
                continue
            breakdown = line.split('\t')
            location = breakdown[3].strip().upper()
            
            location_exists = False
            existing_key = None
            for key in location_dict.keys():
                if key.upper() == location:
                    location_exists = True
                    existing_key = key
                    break
            
            if not location_exists:
                location_dict[location] = {
                    "Location Group Name": location,
                    "INT": False,
                    "EXT": False,
                    "Scenes": []
                }
            else:
                location = existing_key
                
            location_dict[location]["Scenes"].append(breakdown[1])
            if(breakdown[2].upper() in ['INT.', 'INT/EXT.', 'EXT/INT.', 'I/E.', 'E/I.']):
                location_dict[location]["INT"] = True
            if(breakdown[2].lower() in ['EXT.', 'INT/EXT.', 'EXT/INT.', 'I/E.', 'E/I.']):
                location_dict[location]["EXT"] = True
    f.close()
    with open(location_path, 'w') as f:
        f.write("Location ID\tLocation Group Name\tNumber of Scenes\tINT\tEXT\tScene Numbers\tLocked\n")
        counter = 0
        location_list = list(location_dict.keys())
        n = len(location_list)
        for i in range(n-1):
            for j in range(n-i-1):
                if len(location_dict[location_list[j]]["Scenes"]) < len(location_dict[location_list[j+1]]["Scenes"]):
                    location_list[j], location_list[j+1] = location_list[j+1], location_list[j]
        for location in location_list:
            d = location_dict[location]
            name = d["Location Group Name"]
            l = len(d["Scenes"])
            I = d["INT"]
            E = d["EXT"]
            li = ','.join(d["Scenes"])
            if(l>1):
                f.write(f"{counter+1}\t{name}\t{l}\t{I}\t{E}\t{li}\tFalse\n")
                counter = counter + 1
            else:
                f.write(f"None\t{name}\t{l}\t{I}\t{E}\t{li}\tTrue\n")
            print(location + "\n")
        f.close()
    return location_list

def save_breakdown(breakdown, output_path):
    """Save the breakdown to a TSV file, appending if file exists"""
    try:
        # Check if file exists and is not empty
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            # Append the new content
            with open(output_path, 'a') as f:
                f.write('\n' + breakdown)
        else:
            # If file doesn't exist or is empty, write the full content including header
            with open(output_path, 'w') as f:
                f.write("Scene ID\tScene Number\tInt./Ext.\tLocation\tTime\tSynopsis\tCharacters\tAction Props\tOther Props\tPicture Vehicles\tAnimals\tExtras\tWardrobe\tSet Dressing")
                f.write('\n' + breakdown)
        f.close()
        return True
    except Exception as e:
        print(f"Error saving breakdown: {str(e)}")
        return False