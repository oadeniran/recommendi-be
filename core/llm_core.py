from config import OAI_KEY
import openai
from core import prompts
from utils import extract_dictionary_from_string

# Initialize OpenAI client with the API key
llm_model = openai.OpenAI(
    api_key=OAI_KEY,
)

def get_llm_response(sys_prompt, user_prompt=None):
    """
    Get a response from the LLM based on the system and user prompts.
    
    Args:
        sys_prompt (str): The system prompt to guide the LLM.
        user_prompt (str): The user's input prompt.
        max_tokens (int): The maximum number of tokens for the response.
    
    Returns:
        str: The LLM's response.
    """
    messages = [
        {"role": "system", "content": sys_prompt},
    ]
    if user_prompt:
        messages.append({"role": "user", "content": user_prompt})
    try:
        response = llm_model.chat.completions.create(
            messages=messages,
            model="gpt-4o-mini",
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error getting LLM response: {e}")
        return None
    
async def get_system_prompt_for_user_message(selected_recommendation_category):
    """
    Get the system prompt for the specified system.
    
    Args:
        system_name (str): The name of the system to get the prompt for.
        context (str, optional): Additional context to include in the prompt.
    
    Returns:
        str: The system prompt.
    """
    system_prompt = prompts.MESSAGE_DECOMPOSITION_PROMPT.format(
        selected_recommendation_category=selected_recommendation_category
    )
    return system_prompt

async def get_recommendation_data_from_user_message(user_message, selected_recommendation_category):
    """
    Get recommendation data from the user's message.
    
    Args:
        user_message (str): The user's message containing recommendation data.
        selected_recommendation_category (str): The category of recommendations to select.
        all_possible_recommendation_categories (list): All possible recommendation categories.
    
    Returns:
        dict: The recommendation data extracted from the user's message.
    """
    sys_prompt = await get_system_prompt_for_user_message(
        selected_recommendation_category
    )
    
    llm_response = get_llm_response(sys_prompt, user_message)
    
    if llm_response:
        # Extract the dictionary from the LLM response
        recommendation_data = extract_dictionary_from_string(llm_response)
        if recommendation_data:
            return recommendation_data
        else:
            print("No valid recommendation data found in the LLM response.")

def get_context_and_score_for_recommndation_text(recommendation, user_message=None):
    """
    Get the context for the recommendation text.
    
    Args:
        recommendation (dict): The recommendation data.
        user_message (str, optional): The user's message to include in the context.
    
    Returns:
        str: The context for the recommendation text.
    """

    sys_prompt = prompts.RECOMMENDATION_CONTEXT_PROMPT.format(
        recommendation=recommendation,
        user_message=user_message if user_message else "No user message provided."
    )

    llm_response = get_llm_response(sys_prompt)
    score_context_data = extract_dictionary_from_string(llm_response)
    
    if score_context_data:
        return score_context_data
    else:
        print("No valid context data found in the LLM response.")
        return None

    