from services.ai_service import AIService

def get_chat_response(prompt, data_context, chat_history=None):
    """
    Public wrapper preserving original get_chat_response interface.
    Delegates to AIService.
    """
    return AIService.get_chat_response(prompt, data_context, chat_history)