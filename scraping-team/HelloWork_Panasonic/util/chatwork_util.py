import asyncio
import os
import io
import requests
from functools import wraps
from typing import TypeVar, Union

S   = TypeVar('S', bound=requests.sessions.Session)
RES = TypeVar('RES', bound=requests.models.Response)

class Chatwork_Util:
    # コンストラクタ・デストラクタ ==========================================================================
    def __init__(self, token:str):
        self._token = token
        self._room_mambers_dict = {}
        self._session = requests.session()
        self._message_handlers = []
    
    def __del__(self):
        self._session.close()
    # ====================================================================================================
    
    # プロパティ ===========================================================================================
    # ルームごとのメンバー一覧の辞書
    @property
    def room_mambers_dict(self) -> dict:
        return self._room_mambers_dict
    
    # セッション
    @property
    def session(self) -> S:
        return self._session
    # ====================================================================================================

    # メソッド ============================================================================================
    # トークンセット
    def set_token(self, token:str):
        self._token = token

    # メッセージ取得
    def get_messages(self, room_id:Union[int, str]) -> dict:
        return self.get_messages_request(room_id, self._token, self._session)
    
    # メッセージ単体取得
    def get_message(self, room_id, message_id) -> dict:
        return self.get_message_request(room_id, self._token, message_id, self._session)

    # メッセージ送信
    def send_message(self, room_id:Union[int, str], body:str) -> RES:
        return self.send_message_request(room_id, self._token, body, self._session)
    
    # ファイル送信
    def upload_files(self, room_id:Union[int, str], upload_files_path:str) -> RES:
        return self.upload_files_request(room_id, self._token, upload_files_path, self._session)
    
    # ファイル取得
    def get_file(self, room_id:Union[int, str], file_id:str) -> io.BytesIO:
        return self.get_file_request(room_id, self._token, file_id, self._session)
        
    # ルームのメンバー一覧取得
    def get_room_members(self, room_id:Union[int, str], reload:bool=False) -> dict:
        if (member_dict := self._room_mambers_dict.get(str(room_id))) and not reload:
            return member_dict
        member_dict = self.get_room_members_request(room_id, self._token, self._session)
        self._room_mambers_dict[str(room_id)] = member_dict
        return member_dict
    # ====================================================================================================

    # デーモンプロセス用 ===================================================================================    
    # メッセージ受信時のデコレータ
    def on_message(self, func):
        @wraps(func)
        async def wrapper(message):
            return func(message)
        self._message_handlers.append(wrapper)
        return wrapper
    
    # 新着メッセージ監視用
    async def monitor(self, room_id:Union[int, str], interval:int=10):
        last_message_ids = [msg.get('message_id') for msg in self.get_messages(room_id)]
        while True:
            msg_list = self.get_messages(room_id)
            message_ids = [msg.get('message_id') for msg in msg_list]
            new_msg_index_list = [i for i, msg_id in enumerate(message_ids) if msg_id not in last_message_ids]
            for new_index in new_msg_index_list:
                message = msg_list[new_index]
                await asyncio.gather(*(handler(message) for handler in self._message_handlers))
            # 最終メッセージ更新
            last_message_ids = message_ids
            await asyncio.sleep(interval)
    
    # モニタリング実行
    def monitor_run(self, room_id:Union[int, str], interval:int=10):
        asyncio.run(self.monitor(room_id, interval))
    # ====================================================================================================

    # クラスメソッド =======================================================================================
    # メッセージ取得
    @classmethod
    def get_messages_request(cls, room_id:Union[int, str], token:str, session:S=None) -> dict:
        url = f'https://api.chatwork.com/v2/rooms/{room_id}/messages'
        try:
            headers = {'X-ChatWorkToken': token}
            params  = {'force': 1}
            tgt = session or requests
            res = tgt.get(url, headers=headers, params=params)
            return res.json()
        except Exception as e:
            print(f'メッセージ取得: 失敗\n{e}')
            return {}
    
    # メッセージ単体取得
    @classmethod
    def get_message_request(cls, room_id:Union[int, str], token:str, message_id:str, session:S=None) -> dict:
        url = f'https://api.chatwork.com/v2/rooms/{room_id}/messages/{message_id}'
        try:
            headers = {'X-ChatWorkToken': token}
            tgt = session or requests
            res = tgt.get(url, headers=headers)
            return res.json()
        except Exception as e:
            print(f'メッセージ取得: 失敗\n{e}')
            return {}

    # メッセージ送信
    @classmethod
    def send_message_request(cls, room_id:Union[int, str], token:str, body:str, session:S=None) -> RES:
        url = f'https://api.chatwork.com/v2/rooms/{room_id}/messages'
        try:
            headers = {'X-ChatWorkToken': token}
            data    = {'body': body, 'self_unread': 1}
            tgt = session or requests
            res = tgt.post(url, data=data, headers=headers)
            return res
        except Exception as e:
            print(f'メッセージ送信: 失敗\n{e}')
            return e

    # ファイル送信
    @classmethod
    def upload_files_request(
        cls, room_id:Union[int, str], token:str,
        upload_files_path:Union[str, io.BytesIO], session:S=None
    ) -> RES:
        if not upload_files_path: return False
        url = f'https://api.chatwork.com/v2/rooms/{room_id}/files'
        try:
            headers = {'X-ChatWorkToken': token}
            if type(upload_files_path)==str:
                with open(os.path.abspath(upload_files_path), 'rb') as f:
                    files = {'file': f}
            elif type(upload_files_path)==io.BytesIO:
                upload_files_path.seek(0)
                files = {'file': upload_files_path}
            tgt = session or requests
            res = tgt.post(url, headers=headers, files=files)
            return res
        except Exception as e:
            print(f'ファイル送信: 失敗\n{e}')
            return e
    
    # ファイル取得
    @classmethod
    def get_file_request(
        cls, room_id:Union[int, str], token:str, 
        file_id:str, session:S=None                
    ) -> io.BytesIO:
        url = f'https://api.chatwork.com/v2/rooms/{room_id}/files/{file_id}'
        try:
            headers = {'X-ChatWorkToken': token}
            params  = {'create_download_url': 1}
            tgt = session or requests
            res = tgt.get(url, headers=headers, params=params)
            if res.status_code != 200:
                raise Exception('アイテムURL取得失敗')
            download_url = res.json().get('download_url')
            file_res = tgt.get(download_url)
            if file_res.status_code != 200:
                raise Exception('ファイルDL失敗')
            file_content = io.BytesIO(file_res.content)
            file_content.seek(0)
            return file_content
        except Exception as e:
            print(f'ファイル取得: 失敗\n{e}')
            return None
    
    # ルームのメンバー一覧取得
    @classmethod
    def get_room_members_request(cls, room_id:Union[int, str], token:str, session:S=None) -> dict:
        url = f'https://api.chatwork.com/v2/rooms/{room_id}/members'
        try:
            headers = {'X-ChatWorkToken': token}
            tgt = session or requests
            res = tgt.get(url, headers=headers)
            if res.status_code != 200: raise Exception(f'{res.json()}')
            member_list = res.json()
            member_dict = {f'{mamber.get("account_id")}': mamber.get('name') for mamber in member_list} 
            return member_dict
        except Exception as e:
            print(f'メンバー一覧取得: 失敗\n{e}')
            return {}
    # ====================================================================================================