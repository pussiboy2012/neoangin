class ChatBot {
    constructor() {
        this.isOpen = false;
        this.isLoading = false;
        this.storageKey = 'chatbot_history';
        this.init();
    }

    init() {
        this.createWidget();
        this.bindEvents();
        this.loadHistory();
    }

    createWidget() {
           const widgetHTML = `
        <div class="chatbot-widget">
            <button class="chatbot-button"><svg xmlns="http://www.w3.org/2000/svg" width="35" height="30" fill="currentColor" class="bi bi-chat-left-dots" viewBox="0 0 16 16">
  <path d="M14 1a1 1 0 0 1 1 1v8a1 1 0 0 1-1 1H4.414A2 2 0 0 0 3 11.586l-2 2V2a1 1 0 0 1 1-1zM2 0a2 2 0 0 0-2 2v12.793a.5.5 0 0 0 .854.353l2.853-2.853A1 1 0 0 1 4.414 12H14a2 2 0 0 0 2-2V2a2 2 0 0 0-2-2z"/>
  <path d="M5 6a1 1 0 1 1-2 0 1 1 0 0 1 2 0m4 0a1 1 0 1 1-2 0 1 1 0 0 1 2 0m4 0a1 1 0 1 1-2 0 1 1 0 0 1 2 0"/>
</svg></button>
            <div class="chatbot-container">
                <div class="chatbot-header">
                    <div class="chatbot-title">🤖 Помощник по краскам</div>
                    <div class="chatbot-actions">
                        <button class="chatbot-clear" title="Очистить историю">🗑️</button>
                        <button class="chatbot-close">×</button>
                    </div>
                </div>
                <div class="chatbot-messages" id="chatbot-messages">
                    <!-- Сообщения будут загружаться из истории -->
                </div>
                <div class="chatbot-input-container">
                    <textarea class="chatbot-input" placeholder="Введите ваш вопрос..." rows="1"></textarea>
                    <button class="chatbot-send">➤</button>
                </div>
            </div>
        </div>
    `;
        
        document.body.insertAdjacentHTML('beforeend', widgetHTML);
        
        this.elements = {
            widget: document.querySelector('.chatbot-widget'),
            button: document.querySelector('.chatbot-button'),
            container: document.querySelector('.chatbot-container'),
            closeBtn: document.querySelector('.chatbot-close'),
            messages: document.getElementById('chatbot-messages'),
            input: document.querySelector('.chatbot-input'),
            sendBtn: document.querySelector('.chatbot-send')
        };
    }

    bindEvents() {
        this.elements.button.addEventListener('click', () => this.toggleChat());
        this.elements.closeBtn.addEventListener('click', () => this.closeChat());
        this.elements.sendBtn.addEventListener('click', () => this.sendMessage());
        this.elements.input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        this.elements.clearBtn = document.querySelector('.chatbot-clear');
    this.elements.clearBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        if (confirm('Очистить всю историю переписки?')) {
            this.clearHistory();
        }
    });
        // Авто-высота textarea
        this.elements.input.addEventListener('input', () => {
            this.elements.input.style.height = 'auto';
            const newHeight = Math.min(this.elements.input.scrollHeight, 120);
            this.elements.input.style.height = newHeight + 'px';
            // Показывать скроллбар только если высота превышает двойную исходную (45px * 2 = 90px)
            if (newHeight > 90) {
                this.elements.input.style.overflowY = 'auto';
                this.elements.input.style.paddingBottom = '50px'; // Отступ для скроллбара выше кнопки
                this.elements.input.style.paddingRight = '70px'; // Дополнительный отступ для скроллбара, чтобы не заходил на бордер радиус
            } else {
                this.elements.input.style.overflowY = 'hidden';
                this.elements.input.style.paddingBottom = '12px'; // Исходный отступ
                this.elements.input.style.paddingRight = '60px'; // Исходный отступ
            }
        });

        // Сохраняем историю при закрытии страницы
        window.addEventListener('beforeunload', () => this.saveHistory());
    }

    loadHistory() {
        try {
            const savedHistory = localStorage.getItem(this.storageKey);
            if (savedHistory) {
                const history = JSON.parse(savedHistory);
                
                // Очищаем сообщения и загружаем историю
                this.elements.messages.innerHTML = '';
                
                history.forEach(msg => {
                    this.addMessageToDOM(msg.text, msg.sender, msg.timestamp, false);
                });
                
                console.log('История чата загружена:', history.length, 'сообщений');
            } else {
                // Показываем приветственное сообщение если истории нет
                this.addMessageToDOM(
                    'Здравствуйте! Я ваш помощник по краскам и отделочным материалам. Помогу с выбором цветов, типов покрытий и отвечу на все вопросы о нашей продукции!', 
                    'bot', 
                    this.getCurrentTime()
                );
                this.saveHistory(); // Сохраняем начальное сообщение
            }
        } catch (error) {
            console.error('Ошибка загрузки истории:', error);
            // Показываем приветственное сообщение при ошибке
            this.addMessageToDOM(
                'Здравствуйте! Я ваш помощник по краскам и отделочным материалам. Помогу с выбором цветов, типов покрытий и отвечу на все вопросы о нашей продукции!', 
                'bot', 
                this.getCurrentTime()
            );
        }
    }

    saveHistory() {
        try {
            const messages = Array.from(this.elements.messages.children).map(messageEl => {
                const bubble = messageEl.querySelector('.message-bubble');
                const time = messageEl.querySelector('.message-time');
                const sender = messageEl.classList.contains('user') ? 'user' : 'bot';
                
                return {
                    text: bubble.textContent.replace(time?.textContent || '', '').trim(),
                    sender: sender,
                    timestamp: time?.textContent || this.getCurrentTime()
                };
            }).filter(msg => msg.text); // Фильтруем пустые сообщения

            localStorage.setItem(this.storageKey, JSON.stringify(messages));
            console.log('История чата сохранена:', messages.length, 'сообщений');
        } catch (error) {
            console.error('Ошибка сохранения истории:', error);
        }
    }

    clearHistory() {
        try {
            localStorage.removeItem(this.storageKey);
            this.elements.messages.innerHTML = '';
            this.addMessageToDOM(
                'История очищена. Чем могу помочь?', 
                'bot', 
                this.getCurrentTime()
            );
            console.log('История чата очищена');
        } catch (error) {
            console.error('Ошибка очистки истории:', error);
        }
    }

    toggleChat() {
        this.isOpen = !this.isOpen;
        this.elements.container.style.display = this.isOpen ? 'flex' : 'none';
        if (this.isOpen) {
            this.elements.input.focus();
            this.scrollToBottom();
        }
    }

    closeChat() {
        this.isOpen = false;
        this.elements.container.style.display = 'none';
        this.saveHistory(); // Сохраняем при закрытии
    }

    async sendMessage() {
        const message = this.elements.input.value.trim();
        if (!message || this.isLoading) return;

        // Добавляем сообщение пользователя
        this.addMessageToDOM(message, 'user', this.getCurrentTime());
        this.elements.input.value = '';
        this.elements.input.style.height = '45px';
        
        // Сохраняем историю после отправки сообщения
        this.saveHistory();
        
        // Показываем индикатор загрузки
        this.showTypingIndicator();
        this.isLoading = true;

        try {
            const response = await fetch('/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ message: message })
            });

            const data = await response.json();
            
            // Убираем индикатор загрузки
            this.hideTypingIndicator();
            
            if (response.ok) {
                this.addMessageToDOM(data.response, 'bot', data.timestamp);
            } else {
                this.addMessageToDOM(`Извините, произошла ошибка: ${data.error}`, 'bot', this.getCurrentTime());
            }
        } catch (error) {
            this.hideTypingIndicator();
            this.addMessageToDOM('Извините, произошла ошибка соединения. Попробуйте позже.', 'bot', this.getCurrentTime());
        }

        this.isLoading = false;
        this.saveHistory(); // Сохраняем после получения ответа
    }

    addMessageToDOM(text, sender, timestamp, scroll = true) {
        const messageHTML = `
            <div class="message ${sender}">
                <div class="message-bubble">
                    ${this.escapeHtml(text)}
                    <div class="message-time">${timestamp}</div>
                </div>
            </div>
        `;
        
        this.elements.messages.insertAdjacentHTML('beforeend', messageHTML);
        if (scroll) {
            this.scrollToBottom();
        }
    }

    showTypingIndicator() {
        const typingHTML = `
            <div class="message bot" id="typing-indicator">
                <div class="message-bubble">
                    <div class="typing-indicator">
                        Печатает
                        <div class="typing-dots">
                            <span></span>
                            <span></span>
                            <span></span>
                        </div>
                    </div>
                </div>
            </div>
        `;
        this.elements.messages.insertAdjacentHTML('beforeend', typingHTML);
        this.scrollToBottom();
    }

    hideTypingIndicator() {
        const typingIndicator = document.getElementById('typing-indicator');
        if (typingIndicator) {
            typingIndicator.remove();
        }
    }

    scrollToBottom() {
        this.elements.messages.scrollTop = this.elements.messages.scrollHeight;
    }

    getCurrentTime() {
        const now = new Date();
        return now.getHours().toString().padStart(2, '0') + ':' + 
               now.getMinutes().toString().padStart(2, '0');
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Инициализация чат-бота когда DOM загружен
document.addEventListener('DOMContentLoaded', function() {
    window.chatBot = new ChatBot();
    
    // Добавляем глобальные методы для управления историей
    window.clearChatHistory = function() {
        if (window.chatBot) {
            window.chatBot.clearHistory();
        }
    };
    
    window.getChatHistory = function() {
        try {
            return JSON.parse(localStorage.getItem('chatbot_history') || '[]');
        } catch (error) {
            return [];
        }
    };
});