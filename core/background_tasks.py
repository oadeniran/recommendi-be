import asyncio
from datetime import datetime
import traceback as tb
from utils import dict_to_string
#Ide
def serialize_dict_to_text(data: dict, indent: int = 0) -> str:
    """
    Serialize a dictionary to a formatted string with indentation.
    
    Args:
        data (dict): The dictionary to serialize.
        indent (int): The number of spaces to use for indentation.
    
    Returns:
        str: A formatted string representation of the dictionary.
    """
    return dict_to_string(data, indent=indent)