#coding: UTF-8
import urllib.parse
from urllib.request import Request


class Chatwork():
    def __init__(self, rid: str, title: str, token: str) -> None:
        self.rid = rid
        self.title = title
        self.token = token

    def send_alert(self, is_toall: bool, message: str) -> None:
        """[Chatworkにアラートを投稿する.]
        Args:
            rid (str)      : [ルームID]
            is_toall (bool): [toallに送信するか]
            message (str)  : [メッセージ]
        """

        url: str = 'https://api.chatwork.com/v2/rooms/' + self.rid + '/messages'

        # body: str = ''
        # if is_toall == True:
        #     body += '[toall] \n'
        #     # body += '[To:7820379]川野 未來太さん \n'
        # body += '[info]'
        # body += '[title]' + self.title + '[/title]\n'
        # body += message + '\n'
        # body += '[/info]'

        # payload = {
        #     'body': body,
        #     'self_unread': 1,
        # }

        # headers = {
        #     'X-ChatWorkToken': self.token,
        #     'Content-Type'   : 'application/x-www-form-urlencoded',
        #     'method'         : 'POST',
        # }

        # query: bytes = urllib.parse.urlencode(payload).encode()
        # request: Request = Request(url=url, data=query, headers=headers)

        # with urllib.request.urlopen(request) as response:
        #     print('Response:%s->%s' % ( response.status, response.read().decode()) )
        #     response_headers = response.headers
        #     print("Response Headers:", response_headers)