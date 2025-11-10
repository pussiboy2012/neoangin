import requests
import os
from datetime import datetime
import time
from flask import current_app

class OpenRouterChatBot:
    def __init__(self):
        self.conversation_history = []
        self.last_api_call = 0
        self.api_delay = 2
        
    def get_response(self, user_message):
        current_time = time.time()
        if current_time - self.last_api_call < self.api_delay:
            time.sleep(self.api_delay - (current_time - self.last_api_call))
        
        openrouter_response = self._try_openrouter_api(user_message)
        if openrouter_response:
            self.last_api_call = time.time()
            self._add_to_history(user_message, openrouter_response)
            return openrouter_response
        
        raise Exception("OpenRouter API недоступен. Проверьте API ключ и подключение к интернету.")
    
    def _try_openrouter_api(self, user_message):
        """Используем OpenRouter API для доступа к различным моделям"""
        try:
            url = "https://openrouter.ai/api/v1/chat/completions"
            
            openrouter_key = os.getenv('OPENROUTER_API_KEY')
            if not openrouter_key:
                raise Exception("OPENROUTER_API_KEY не найден в .env файле")
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {openrouter_key}",
                "HTTP-Referer": "http://localhost:5000",
                "X-Title": "Paint Store Assistant"
            }
            
            messages = self._build_messages(user_message)
            
            models_to_try = [
                "meta-llama/llama-3-70b-instruct",
                "google/gemini-pro",
            ]
            
            for model in models_to_try:
                try:
                    current_app.logger.info(f"Пробуем модель: {model}")
                    
                    data = {
                        "model": model,
                        "messages": messages,
                        "max_tokens": 500,
                        "temperature": 0.7,
                        "top_p": 0.9,
                    }
                    
                    response = requests.post(
                        url,
                        headers=headers,
                        json=data,
                        timeout=30
                    )
                    
                    current_app.logger.info(f"Статус ответа для {model}: {response.status_code}")
                    
                    if response.status_code == 200:
                        result = response.json()
                        current_app.logger.info(f"Успешный ответ от {model}")
                        
                        generated_text = self._extract_openrouter_response(result)
                        if generated_text:
                            return generated_text
                            
                    elif response.status_code == 402:
                        current_app.logger.warning(f"Недостаточно средств для модели {model}")
                        continue
                        
                    elif response.status_code == 429:
                        current_app.logger.warning(f"Лимит запросов для {model}")
                        continue
                        
                    else:
                        current_app.logger.error(f"Ошибка {response.status_code} для {model}: {response.text}")
                        continue
                        
                except requests.exceptions.Timeout:
                    current_app.logger.warning(f"Таймаут для модели {model}")
                    continue
                except Exception as e:
                    current_app.logger.error(f"Ошибка для модели {model}: {e}")
                    continue
            
            return None
            
        except Exception as e:
            current_app.logger.error(f"Общая ошибка OpenRouter API: {e}")
            return None
    
    def _build_messages(self, user_message):
        """Строим список сообщений для API"""
        messages = []
        
        # Системный промпт для магазина красок
        system_message = {
            "role": "system",
            "content": """Ты AI-ассистент для магазина красок и отделочных материалов. 
Отвечай вежливо и профессионально на русском языке. 
Помогай пользователям с выбором красок, консультируй по цветам, типам покрытий, расходу материалов.
Предоставляй информацию о наличии товаров, акциях и доставке.
Если вопрос не связан с темой, вежливо предложи перейти к теме красок и ремонта."""
        }
        messages.append(system_message)
        
        for msg in self.conversation_history[-6:]:
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        
        messages.append({
            "role": "user",
            "content": user_message
        })
        
        return messages
    
    def _extract_openrouter_response(self, result):
        """Извлекаем текст из ответа OpenRouter"""
        try:
            if 'choices' in result and len(result['choices']) > 0:
                message = result['choices'][0].get('message', {})
                content = message.get('content', '').strip()
                return content if content else None
            return None
            
        except Exception as e:
            current_app.logger.error(f"Ошибка при извлечении ответа: {e}")
            return None
    
    def _add_to_history(self, user_message, bot_response):
        self.conversation_history.append({"role": "user", "content": user_message})
        self.conversation_history.append({"role": "assistant", "content": bot_response})
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]

# Глобальный экземпляр бота
chatbot = OpenRouterChatBot()