import base64
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.ui import WebDriverWait
from time import sleep
from typing import TypeVar, Union

AL = TypeVar('AL', bound='selenium.webdriver.common.alert.Alert')
CE = TypeVar('CE', bound='CustomElement')
WD = TypeVar('WD', bound=webdriver.chrome.webdriver.WebDriver)

# 機能を追加したWebElementクラス
class CustomElement(WebElement):
    # セレニウムのWebElementクラスを継承
    def __init__(self, driver:WD, element_id:str):
        super().__init__(driver, element_id)
    
    @property
    def web_element(self) -> WebElement:
        # アッパーキャストして返却
        return WebElement(self._parent, self.id)
    
    @property
    def select(self) -> Select:
        # セレクトボックスのクラスを返却する
        return Select(self.web_element)
        
    @property
    def value(self) -> str:
        return self.get_attribute('value')
    
    @property
    def parent_ele(self):
        return self.find_element('xpath', '..')
    
    # 値セット
    def set_attribute(self, attribute:str, value:str):
        self._parent.execute_script(f'arguments[0].{attribute} = arguments[1]', self, value)
    
    # JSを使ってクリック
    def js_click(self):
        self._parent.execute_script('arguments[0].click();', self)
    
    # このエレメントまでスクロール
    def scroll(self):
        self._parent.execute_script("arguments[0].scrollIntoView({ behavior: 'auto', block: 'center' });", self.web_element)
        
    # エレメント検索
    # オーバーライドしているので元のを使いたい場合はweb_elementを取得してから実行してください
    def find_element(self, mode:str, word:str) -> CE:
        elements = self.find_elements(mode, word, 1) or []
        return elements[0] if len(elements) > 0 else None

    # エレメント検索
    # オーバーライドしているので元のを使いたい場合はweb_elementを取得してから実行してください
    def find_elements(self, mode:str, word:str, max_ele_num:int=-1) -> list:
        tgt_mode = {
            'id'          : By.ID,
            'class'       : By.CLASS_NAME,
            'tag'         : By.TAG_NAME,
            'name'        : By.NAME,
            'xpath'       : By.XPATH,
            'css_selector': By.CSS_SELECTOR,
            'link_text'   : By.LINK_TEXT,
        }.get(mode)
        try:
            ele_list = super().find_elements(tgt_mode, word)
            if max_ele_num != -1:
                ele_list = ele_list[:max_ele_num]
            return [CustomElement(self._parent, ele.id) for ele in ele_list]
        except Exception as e:
            return []


class Chrome_Util:
    # コンストラクタ
    def __init__(self, driver_path:str=None, options_str_list:list=[], binary_location:str=None):
        # ChromeDriverの起動
        options = webdriver.ChromeOptions()
        if binary_location:
            options.binary_location = binary_location
        for option_str in options_str_list:
            options.add_argument(option_str)
        if driver_path:
            self._driver = webdriver.Chrome(service=Service(executable_path=driver_path), options=options)
        else:
            self._driver = webdriver.Chrome(options=options)
        self.load_wait()
    
    # デストラクタ
    def __del__(self):
        self._driver.quit()

    # ドライバ取得
    @property
    def driver(self) -> WD:
        return self._driver
    
    # URL取得
    @property
    def current_url(self) -> str:
        return self._driver.current_url
    
    @property
    def alert(self) -> AL:
        try:
            # OK → alert.accept() キャンセル → alert.dismiss()
            return WebDriverWait(self._driver, 1).until(EC.alert_is_present())
        except:
            return None

    # ドライバクローズ
    def close_driver(self):
        self._driver.close()
        self._driver.quit()
    
    # URLを開く
    def open_url(self, url:str, timeout:int=20) -> bool:
        try:
            # ポップアップ無効
            self._driver.execute_script('window.onbeforeunload = function() {};')
            self._driver.get(url)
            self.load_wait(timeout)
            return True
        except:
            return False
    
    # ページ遷移
    def location_href(self, url:str):
        # ポップアップ無効
        self._driver.execute_script('window.onbeforeunload = function() {};')
        self._driver.execute_script(f'window.location.href = "{url}";')
        self.load_wait()
    
    # ベーシック認証の設定
    def set_basic_auth_header(self, user_name:str=None, password:str=None, clear_mode:bool=False) -> bool:
        try:
            if clear_mode:
                auth_header = {}
            elif all([user_name, password]):
                # Authorizationヘッダを作成
                b64 = base64.b64encode(f'{user_name}:{password}'.encode('utf-8')).decode('utf-8')
                auth_header = {'Authorization': f'Basic {b64}'}
            else:
                raise Exception('設定するユーザ名・パスワードがありません')
            # Authorizationヘッダを適用
            self.driver.execute_cdp_cmd('Network.enable', {})
            self.driver.execute_cdp_cmd('Network.setExtraHTTPHeaders', {'headers': auth_header})
            return True
        except Exception as e:
            print(f'[ベーシック認証の設定]: 失敗\n{e}')
            return False


    # コンテンツが読み込まれるまで待機
    def load_wait(self, timeout:int=20, sleep_time:int=0):
        try:
            sleep(sleep_time)
            WebDriverWait(self._driver, timeout).until(EC.presence_of_all_elements_located)
        except Exception as e:
            print('タイムアウトしました')
            print(e)
    
    # 要素が使用可能になるまで待つlogin
    def implicitly_wait(self, timeout:int=20):
        self._driver.implicitly_wait(timeout)
    
    # 画面サイズ変更
    def set_window_size(self, width:Union[int, str], height:Union[int, str]):
        self._driver.set_window_size(f'{width}', f'{height}')

    # javascript実行
    def exe_js(self, method_str:str, *args, timeout:int=20):
        result = self._driver.execute_script(f'return {method_str}', *args)
        self.load_wait(timeout)
        return result
    
    # リードオンリーのエレメントのリードオンリーを消す
    def remove_read_only(self, ele:CE) -> CE:
        self.exe_js("arguments[0].removeAttribute('readonly');", ele)
        return ele
    
    # エレメント削除
    def del_element(self, ele:CE):
        self.exe_js('arguments[0].remove();', ele)
    
    # エレメントのValue変更
    def set_ele_value(self, ele:CE, val):
        self.exe_js('arguments[0].value = arguments[1]', ele, val)
    
    # エレメント検索
    def find_element(self, mode:str, word:str, timeout:int=20) -> CE:
        elements = self.find_elements(mode, word, timeout, 1) or []
        return elements[0] if len(elements) > 0 else None

    # エレメント検索(複数)
    def find_elements(self, mode:str, word:str, timeout:int=20, max_ele_num:int=-1) -> list:
        tgt_mode = {
            'id'          : By.ID,
            'class'       : By.CLASS_NAME,
            'tag'         : By.TAG_NAME,
            'name'        : By.NAME,
            'xpath'       : By.XPATH,
            'css_selector': By.CSS_SELECTOR,
            'link_text'   : By.LINK_TEXT,
        }.get(mode)
        try:
            ele_list = WebDriverWait(self._driver, timeout).until(
                EC.presence_of_all_elements_located((tgt_mode, word))
            )
            if max_ele_num != -1:
                ele_list = ele_list[:max_ele_num]
            return [CustomElement(self._driver, ele.id) for ele in ele_list]
        except Exception as e:
            return []
       
    # フレーム変更
    def switch_frame(self, iframe_ele:CE) -> WD:
        try:
            self._driver.switch_to.frame(iframe_ele)
            return self._driver
        except Exception as e:
            return None
    
    # セレクター取得
    @classmethod
    def get_select(self, ele:CE) -> Select:
        return Select(ele.web_element)