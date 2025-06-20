from PyPDF2 import PdfReader

def isSceneNumberPresent(pdf_path):
    return False

def isSceneHeading(pdf_path, line):
    if(isSceneNumberPresent(pdf_path)):
        return True
    return False

def extract_text_from_pdf(pdf_path, id):
    reader = PdfReader(pdf_path)
    scenes = []
    heading = ''
    content = ''
    
    for page in reader.pages:
        text = page.extract_text()
        l = text.split('\n')
        for line in l:
            if('INT.' in line or 'EXT.' in line or 'INT./EXT.' in line or 'EXT./INT.' in line or 'I/E.' in line or 'E/I.' in line):
                if(heading != ''):
                    scenes.append({'heading': heading, 'content': content})
                heading = line
                content = ''
                continue
            content += line
    
    # Add the last scene
    if heading != '':
        scenes.append({'heading': heading, 'content': content})
    
    return scenes
   