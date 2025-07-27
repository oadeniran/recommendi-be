from db import ragEmbeddingsCollection, extractedDataCollection, reportsCollection, sessionsCollection
from datetime import datetime
from core import chatActions, mental_prediction, big5_personality
import pandas as pd
import re
import json
from azure.storage.blob import BlobServiceClient, ContentSettings
from config import AZURE_BLOB_CONNECTION_STR, EMBEDDINGS_CONTAINER_NAME

POSSIBLE_SELECTIONS = {
    "mindlab": mental_prediction,
    "personality_test": big5_personality
}

VERBOSITY_LEVEL = {
    1: "Direct and concise. Ask straightforward questions with minimal elaboration.",
    2: "Moderate verbosity. Ask questions with some detail and context, providing a bit of expressiveness and guidance.",
    3: "High verbosity and expressiveness. Present scenarios or hypothetical situations and ask questions about how the user would respond to these situations, using their responses to assess and score."
}

def extract_dictionary_from_string(input_string):
    # Regular expression to find dictionary-like structure in the string
    dict_pattern = re.compile(r'\{.*?\}', re.DOTALL)
    
    # Search for the dictionary-like structure
    match = dict_pattern.search(input_string)
    
    if match:
        dict_string = match.group(0)
        
        # Attempt parsing the string to JSON
        dictionary = clean_and_parse_json(dict_string)
        return dictionary
    else:
        print("Error: No dictionary-like structure found in the input string.")
        return None

def clean_and_parse_json(input_string):
    # Step 1: Clean input by removing newline characters and excessive whitespace
    cleaned_string = re.sub(r'[\n\t]', '', input_string).strip()
    
    # Step 2: Convert single quotes to double quotes if needed
    cleaned_string = cleaned_string.replace("'", '"')
    
    # Step 3: Handle any trailing commas inside the dictionary
    cleaned_string = re.sub(r',(\s*[\}\]])', r'\1', cleaned_string)
    
    # Step 4: Try to parse the cleaned string into a JSON object
    try:
        dictionary = json.loads(cleaned_string)
        return dictionary
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
        return None


def extract_list_from_string(input_string):
        print(input_string)
        # Regular expression to find list-like structure in the string
        start = input_string.find('[')
        end = input_string.rfind(']')
        if start != -1 and end != -1:
            list_string = input_string[start:end+1]
            # Attempt parsing the string to JSON
            list_object = clean_and_parse_list_json(list_string)
            return list_object
        else:
            print("Error: No list-like structure found in the input string.")
            return None, None, "No list-like structure found in the input string. Check etrxaction of questions or retry"

def clean_and_parse_list_json(input_string):
  print("INPUT", input_string)
  # Step 1: Clean input by removing newline characters and excessive whitespace
  cleaned_string = input_string.strip()
  print("Cleaned", cleaned_string)
  cleaned_string = cleaned_string.replace("False", "false").replace("True", "true")

  # Step 1: Clean input by removing newline characters and excessive whitespace
  cleaned_string = input_string.strip()
  print("Cleaned", cleaned_string)

  cleaned_string = re.sub(r'\n+', ' ', cleaned_string)  # Replace multiple newlines with a space

  # Fix incorrect double quotes used for apostrophes (e.g., product"s → product's)
  cleaned_string = re.sub(r'(\w)"(\w)', r"\1'\2", cleaned_string)

  # Clean for latex
  cleaned_string = re.sub(r'(?<!\\)\\(?![\\"])', r'\\\\', cleaned_string)

  # Ensure double quotes are properly escaped within text values
  #cleaned_string = re.sub(r'(?<!\\)"', r'\"', cleaned_string)

  """# Remove unnecessary spaces and newlines
  cleaned_string = re.sub(r'\s+', ' ', cleaned_string).strip()

  # Fix trailing commas (JSON does not allow trailing commas)
  cleaned_string = re.sub(r',\s*([\]}])', r'\1', cleaned_string)"""

  # Step 4: Try to parse the cleaned string into a JSON object
#   try:
#       dictionary = json.loads(cleaned_string)
#       return dictionary, None, None
#   except json.JSONDecodeError as e:
#       print(f"Error decoding JSON: {e}")
#       return None, cleaned_string, f"Error decoding JSON: {e}"
  
  try:
    dictionary = json.loads(cleaned_string)
    return dictionary, None, None
  except json.JSONDecodeError as e:
    print(f"Error decoding JSON: {e}")
    if e.pos == len(cleaned_string):
        print("Error happened at end of string, adding another square bracket close and trying again")
        try:
            dictionary = json.loads(cleaned_string+"]")
            return dictionary, None, None
        except json.JSONDecodeError as e:
            print(f"Still ran into error and the error is Error decoding JSON: {e}")
    return None, cleaned_string, f"Still ran into error and the error is Error decoding JSON: {e}"

# Another exists in backgroundTasks.py for serilizing the jdon data to string
def dict_to_string(d, explanations=None, indent=0, normalize_text=False):
    def normalize(s):
        return s.replace('_', ' ').title() if normalize_text else s

    result = []
    prefix = " " * indent

    if explanations and len(explanations) > 0:
        for key, value in d.items():
            key_display = normalize(key)
            if isinstance(value, dict):
                value_str = ', '.join(f'{normalize(k)}: {v}' for k, v in value.items())
                result.append(f'{prefix}{key_display}: {explanations.get(key, "")}: value(numeric) can be {value_str}')
            elif isinstance(value, range):
                value_str = f'{value.start} to {value.stop - 1}'
                result.append(f'{prefix}{key_display}: {explanations.get(key, "")}: score user with a numeric value between {value_str}')
            else:
                result.append(f'{prefix}{key_display}: {value}')
    else:
        for key, value in d.items():
            key_display = normalize(key)
            if isinstance(value, dict):
                result.append(f'{prefix}{key_display}:')
                result.append(dict_to_string(value, explanations=None, indent=indent + 2, normalize_text=normalize_text))
            elif isinstance(value, list):
                result.append(f'{prefix}{key_display}:')
                for item in value:
                    if isinstance(item, dict):
                        result.append(dict_to_string(item, explanations=None, indent=indent + 2, normalize_text=normalize_text))
                    else:
                        item_display = normalize(item) if isinstance(item, str) else item
                        result.append(f'{" " * (indent + 2)}- {item_display}')
            elif isinstance(value, range):
                value_str = f'{value.start} to {value.stop - 1}'
                result.append(f'{prefix}{key_display}: {value_str}')
            else:
                value_display = normalize(value) if isinstance(value, str) else value
                result.append(f'{prefix}{key_display}: {value_display}')
                
    return '\n'.join(result)

def remove_stage_from_message(message):
    pattern = r'CURRENT_STAGE:\s*\d+'

    # Replace the CURRENT_STAGE part with an empty string
    cleaned_message = re.sub(pattern, '', message)

    return cleaned_message

def get_input_format(selection):
    d = POSSIBLE_SELECTIONS[selection].MAPPINGS
    explanations = POSSIBLE_SELECTIONS[selection].EXPLANATIONS
    return dict_to_string(d, explanations)

def get_output_format(selection):
    output_format = dict_to_string(POSSIBLE_SELECTIONS[selection].OUTPUT_FORMAT)
    return output_format

def get_system_template(selection,output_format, required_info_s ,verbosity):

    sys_template = POSSIBLE_SELECTIONS[selection].get_sys_template(output_format, required_info_s, verbosity)

    return sys_template

def convert_dict_to_df(d):
  df = pd.DataFrame(columns=d.keys())
  df.loc[0] = d.values()
  return df

def get_prediction(selection, data):
    return POSSIBLE_SELECTIONS[selection].get_prediction(data)

def add_extracted_data_to_db(uid, session_id:str, data:dict):
    document = {
        "uid":uid,
        "session_id":session_id,
        "data":data,
        "date":datetime.now(),
    }
    extractedDataCollection.insert_one(document)

def remove_embedded_data(session_id:str):
    print("Removing embedded data for session_id:", session_id)
    ragEmbeddingsCollection.delete_many({"current_session_id":session_id})
    print("Removed embedded data for session_id:", session_id)

def upload_file_bytes(blob_name, file_bytes, content_type="application/octet-stream", container_name=EMBEDDINGS_CONTAINER_NAME,):
    try:
        blob_service_client = BlobServiceClient.from_connection_string(
            AZURE_BLOB_CONNECTION_STR
        )
        
        container_client = blob_service_client.get_container_client(
            container_name
        )

        blob_client = container_client.get_blob_client(blob_name)

        # Explicitly delete if exists - comment out to avoid concurency issues where another process might be trying to access the same blob but cannot because it is being deleted
        # if blob_client.exists():
        #     blob_client.delete_blob()

        content_settings = ContentSettings(
            content_type=content_type,
            content_disposition="inline",
        )

        blob_client.upload_blob(
            file_bytes,
            overwrite=True,
            blob_type="BlockBlob",
            content_settings=content_settings,
        )

        print(f"File {blob_name} uploaded successfully.")
        return blob_client.url

    except Exception as ex:
        print(f"Error during file upload: {ex}")
        raise

def download_file_bytes(blob_name, container_name=EMBEDDINGS_CONTAINER_NAME):
    try:
        blob_service_client = BlobServiceClient.from_connection_string(
            AZURE_BLOB_CONNECTION_STR
        )
        
        container_client = blob_service_client.get_container_client(
            container_name
        )

        blob_client = container_client.get_blob_client(blob_name)

        if not blob_client.exists():
            print(f"Blob {blob_name} does not exist.")
            return None

        file_bytes = blob_client.download_blob().readall()
        print(f"File {blob_name} downloaded successfully.")
        return file_bytes

    except Exception as ex:
        print(f"Error during file download: {ex}")
        raise
