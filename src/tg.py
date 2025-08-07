import requests

# Telegram API 資訊
bot_token = ""
chat_id = ""

class TelegramBot:
    def __init__(self):
        self.token = bot_token
        self.chat_id = int(chat_id)
        # Telegram API URL
        self.api_url = f"https://api.telegram.org/bot{self.token}/"
        self.offset = 0
        self.msg_handlers = []
        
        # 在初始化時，自動設定好 offset
        self.initialize_offset()

    def _call_api(self, api_method, http_method='GET', params=None):
        if self.token == None or self.chat_id == None:
            return 
        
        """一個私有方法，用來處理所有 API 呼叫"""
        url = f"{self.api_url}{api_method}"
        try:
            response = requests.request(http_method, url, params=params, timeout=15)
            response.raise_for_status() # 如果請求失敗，拋出異常
            return response.json().get('result', [])
        except requests.exceptions.RequestException as e:
            # print('tg request fail', e)
            return None

    def initialize_offset(self):
        """
        透過取得大量更新來設定 offset，確保從最新的訊息開始接收。
        """
        # 呼叫 getUpdates，將 limit 設為 1，但 offset 設為 -1 來取得最後一筆訊息
        # 這種方式雖然有效，但有時可能無法取得所有未讀訊息。
        # 更穩健的做法是先取得所有未讀訊息，然後設定 offset
        updates = self._call_api("getUpdates", http_method='get', params={'limit': 1, 'offset': -1})
        
        if updates:
            # 取得最後一筆訊息的 update_id，然後將 offset 設為 update_id + 1
            last_update_id = updates[0]['update_id']
            self.offset = last_update_id + 1

    def check_message_and_chat_id(self, update, message):
        if (update.get('message') and
            update['message'].get('text') and
            self.chat_id == int(update['message']['chat']['id']) ):
            return message == update['message']['text']
        else:
            return False
        
    def get_latest_update(self):
        """
        每次呼叫時，只抓取一筆最新的訊息。
        """
        # 使用目前的 offset，並將 limit 設為 1，只取一筆
        params = {'offset': self.offset, 'limit': 1, 'timeout': 10}
        updates = self._call_api("getUpdates", http_method='get', params=params)
        
        if updates:
            update = updates[0]
            # 更新 offset 為這筆新訊息的 update_id + 1
            self.offset = update['update_id'] + 1
            
            for handler in self.msg_handlers:
                check_fn, action_fn = handler
                if check_fn(update):
                    action_fn()
        
    def send_message(self, message_text): 
        """
        發送訊息
        """
        params = {
            "chat_id": self.chat_id,
            "text": message_text,
            "parse_mode": "HTML" # 可以使用 HTML 或 Markdown 格式
        }
        response = self._call_api("sendMessage", http_method='post', params=params)
        return response
    
    def add_message_handler(self, check_fn, action_fn):
        self.msg_handlers.append((check_fn, action_fn))

# 初始化 Bot
bot = TelegramBot()
