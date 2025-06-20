import os
import google.generativeai as genai

API_KEY = "AIzaSyALM7eX91PsE05qZw57UYusKZbq3OYKBic"

genai.configure(api_key=API_KEY)

# Choose the experimental 2.5 Pro preview model
model = genai.GenerativeModel("gemini-2.5-pro-preview-03-25")

def generate_scene_breakdown_gemini(script_text, characters, counter):
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
        # Call the Gemini API
        response = model.generate_content([system_prompt, user_prompt])
        
        # Extract and return the breakdown
        breakdown = response.text
        return breakdown

    except Exception as e:
        print(f"Error generating breakdown: {str(e)}")
        return None

