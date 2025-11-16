from flask import Blueprint, request, jsonify, current_app, session
from ..utils import USERS, read_json
from datetime import datetime
from app.chatbot import chatbot
from pathlib import Path
from app.utils import get_chat, create_chat, add_message_to_chat, write_json, get_user_chat_file

bp = Blueprint('chatbot', __name__)

@bp.route('/chat', methods=['POST'])
def chat():
    try:
        user_message = request.json.get('message', '').strip()
        user_id = session.get('user', {}).get('id')

        if not user_id:
            return jsonify({'error': 'Пользователь не авторизован'}), 401

        if not user_message:
            return jsonify({'error': 'Пустое сообщение'}), 400

        # Получаем чат пользователя
        chat_data = get_chat(user_id)
        if not chat_data:
            user_data = read_json(Path(USERS) / f"{user_id}.json")
            user_name = user_data.get('full_name', 'Покупатель') if user_data else 'Покупатель'
            company_name = user_data.get('company_name', 'ООО ДАБАТА') if user_data else 'ООО ДАБАТА'
            chat = create_chat(user_id, user_name, company_name)

        # Проверяем, включен ли бот для этого чата
        if not chat_data.get('bot_enabled', True):
            return jsonify({
                'response': 'Бот временно отключен. Ожидайте ответа менеджера.',
                'timestamp': datetime.now().strftime('%H:%M')
            })

        # Получаем ответ от бота
        bot_response = chatbot.get_response(user_id, user_message)

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

@bp.route('/clear_history', methods=['POST'])
def clear_history():
    try:
        user_id = session.get('user', {}).get('id')
        if not user_id:
            return jsonify({'error': 'Пользователь не авторизован'}), 401

        chat_data = get_chat(user_id)
        if chat_data:
            chat_data['messages'] = []
            write_json(get_user_chat_file(user_id), chat_data)

        return jsonify({'success': True, 'message': 'История очищена'})
    except Exception as e:
        current_app.logger.error(f"Ошибка очистки истории: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500