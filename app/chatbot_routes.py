from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
from .chatbot import chatbot

chatbot_bp = Blueprint('chatbot', __name__)

@chatbot_bp.route('/chat', methods=['POST'])
def chat():
    try:
        user_message = request.json.get('message', '').strip()
        
        if not user_message:
            return jsonify({'error': 'Пустое сообщение'}), 400
        
        bot_response = chatbot.get_response(user_message)
        
        return jsonify({
            'response': bot_response,
            'timestamp': datetime.now().strftime('%H:%M')
        })
        
    except Exception as e:
        current_app.logger.error(f"Ошибка в чат-боте: {e}")
        return jsonify({
            'error': f'Ошибка: {str(e)}',
            'timestamp': datetime.now().strftime('%H:%M')
        }), 500

@chatbot_bp.route('/clear_chat', methods=['POST'])
def clear_chat():
    chatbot.conversation_history = []
    return jsonify({'success': True})

@chatbot_bp.route('/clear_history', methods=['POST'])
def clear_history():
    try:
        chatbot.conversation_history = []
        return jsonify({'success': True, 'message': 'История очищена'})
    except Exception as e:
        current_app.logger.error(f"Ошибка очистки истории: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500