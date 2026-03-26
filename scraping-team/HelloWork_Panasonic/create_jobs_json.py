'''
更新日: 2024/02/27
編集者: 喜田
実行頻度: 月一予定

アカウントごとに求人の[公開ステータス][公開範囲][URL]
をまとめたJSONを出力する
一度JSONに出力するのは数が多すぎるため
すでに取得しているアカウントの情報は更新しない（スプレッドシートに書き込んだ時点でJSONからは消すため）
'''
import json
import math
import os
import re
import sys
from bs4 import BeautifulSoup
from configparser import ConfigParser
from util.chatwork_util import Chatwork_Util
from util.chrome_util import Chrome_Util
from util.google_service_util import GoogleServiceUtil
import gspread
from os import path
from oauth2client.service_account import ServiceAccountCredentials
from selenium.common.exceptions import WebDriverException
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

COOKIES_FILE = "user_cookies.json"

# ログインし、有効求人ページを開くまでの処理
def login_old(chrome, username, password, otp):
    print(f"otp code {otp}")
    sys.exit("Login with get OTP")

    chrome.driver.maximize_window()
    chrome.open_url('https://www.hellowork.mhlw.go.jp/')
    # ログインボタンを特定
    login_button_list = [ele for ele in chrome.find_elements('css_selector', 'a.button.orange.main') if ele.text=='求人者マイページにログイン']
    if not login_button_list:
        print(f'{username}: ログインボタンを特定できませんでした')
        return False
    print(f'{username}: ログインページ遷移完了')
    # ログインページへ移動
    login_button_list[0].js_click()
    chrome.load_wait(sleep_time=1)
    # ログイン情報入力
    chrome.find_element('id', 'ID_loginMailTxt').send_keys(username)
    chrome.find_element('id', 'ID_loginPasswordTxt').send_keys(password)
    chrome.find_element('id', 'ID_loginBtn').click()
    chrome.load_wait(sleep_time=1)

    # 🔑 Input OTP
    # try:
    #     otp_input = chrome.find_element('id', 'ID_txtOtp', timeout=5)
    #     if otp_input:
    #         otp_input.send_keys(otp)
    #         print(f"{username}: OTP nhập thành công -> {otp}")
    #         # Nếu có nút xác nhận OTP thì click
    #         confirm_btn = chrome.find_element('id', 'ID_otpConfirmBtn', timeout=3)
    #         if confirm_btn:
    #             confirm_btn.click()
    #             chrome.load_wait(sleep_time=1)
    # except Exception as e:
    #     print(f"{username}: OTP入力失敗 - {e}")
    #     return False

    # 新規求人登録ボタン取得
    add_new_button = chrome.find_element('id', 'ID_newKyujinBtn', timeout=1)
    if not add_new_button:
        print(f'{username}: ログイン失敗')
        return False
    print(f'{username}: ログイン完了')
    # 新規求人登録ボタン押下
    add_new_button.js_click()
    chrome.load_wait(sleep_time=1)
    if chrome.find_element('class', 'page_title').text != '新規求人登録':
        print(f'{username}: 有効求人表示失敗')
        return False
    # すべての処理がうまく行ったときはTrueを返す
    print(f'{username}: 有効求人表示完了')
    return True

def login_with_cookies(chrome, username, password, cookies_file="user_cookies.json"):
    print(f"{username}: Thực hiện login...")

    # 1. Mở đúng domain kyujin
    chrome.driver.maximize_window()
    chrome.open_url("https://kyujin.hellowork.mhlw.go.jp/kyujin/")

    # 2. Load cookies
    load_cookies_from_file(chrome, cookies_file, username)

    # 3. Sau đó mới đi login bằng user/pass
    chrome.open_url("https://www.hellowork.mhlw.go.jp/")
    login_button_list = [
        ele for ele in chrome.find_elements('css_selector', 'a.button.orange.main')
        if ele.text == '求人者マイページにログイン'
    ]
    if not login_button_list:
        print(f'{username}: ログインボタンを特定できませんでした')
        return False

    login_button_list[0].js_click()
    chrome.load_wait(1)

    chrome.find_element('id', 'ID_loginMailTxt').send_keys(username)
    chrome.find_element('id', 'ID_loginPasswordTxt').send_keys(password)
    chrome.find_element('id', 'ID_loginBtn').click()
    chrome.load_wait(3)

    # Nếu muốn dừng lại debug nhập OTP
    # input("⏸ Dừng lại, nhập OTP thủ công trong Chrome rồi nhấn Enter để tiếp tục...")

    print(f"{username}: Login thành công ✅")
    return True

def load_cookies_from_file(chrome, cookies_file, username=""):
    """
    Load cookies từ file JSON và thêm vào Chrome driver.
    """
    if not os.path.exists(cookies_file):
        print(f"{username}: Không tìm thấy file {cookies_file}")
        return 0, 0

    with open(cookies_file, "r", encoding="utf-8") as f:
        cookies = json.load(f)

    added = 0
    for cookie in cookies:
        cookie_dict = {
            "name": cookie.get("name"),
            "value": cookie.get("value"),
            "domain": cookie.get("domain"),
            "path": cookie.get("path"),
            "secure": cookie.get("secure", False),
        }
        if "expirationDate" in cookie:
            cookie_dict["expiry"] = int(cookie["expirationDate"])

        try:
            chrome.driver.add_cookie(cookie_dict)
            added += 1
        except Exception as e:
            print(f"{username}: Bỏ qua cookie lỗi {cookie.get('name')} -> {e}")

    print(f"{username}: Đã load {added}/{len(cookies)} cookies")
    return added, len(cookies)

# 公開ステータス、公開範囲、URLの情報の辞書
def get_job_dict(ele):
    job_dict = {}
    # 公開ステータス
    job_dict['公開ステータス'] = status_list[0].text.strip() if (status_list := ele.select('div.flex_item_noshrink.m05 span')) else ''
    # 公開範囲
    job_info_table_list = ele.select('tr.border_new td')
    table_ele_list = [i for i, ele in enumerate(job_info_table_list, start=1) if ele.text=='公開範囲']
    if not table_ele_list: return {}
    idx = table_ele_list[0]
    job_dict['公開範囲'] = job_info_table_list[idx].text.strip()
    
    # URL
    url_ele = ele.find(id='ID_dispDetailBtn')
    if not url_ele: return {}
    job_dict['URL'] = f'https://kyujin.hellowork.mhlw.go.jp/kyujin{url_ele.get("href").lstrip(".")}'
    return job_dict


# 大枠の操作
def get_account_datas(username, password, account_name=''):

    # クロームドライバ生成
    options_list = [
        # '--headless',
        # '--no-sandbox',
        # '--disable-gpu',
        # '--single-process',
        # '--disable-dev-shm-usage',
        # '--disable-dev-tools',
    ]
    chrome = Chrome_Util(options_str_list=options_list)
    if not login_with_cookies(chrome, username, password, COOKIES_FILE):
        print(f'{username}: ログイン失敗')
        return False
    # 総件数
    print(f"begin scrap total count")

    try:
        # elems = chrome.driver.find_elements(By.ID, "ID_newKyujinBtn")
        # btn = next(el for el in elems if el.is_displayed())
        # chrome.driver.execute_script("arguments[0].click();", btn)
        # print("Click new button")

        # Chờ parent div render
        parent_div = WebDriverWait(chrome.driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.home_float_button_area"))
        )

        # Lấy tất cả button
        buttons = parent_div.find_elements(By.CSS_SELECTOR, "a#ID_yukoKyujinBtn.button.sub")
        print(f"Tìm thấy {len(buttons)} button(s)")
        for i, b in enumerate(buttons):
            print(f"Button {i}: displayed={b.is_displayed()}, text='{b.text}'")

        if len(buttons) >= 2:
            btn2 = buttons[1]
            WebDriverWait(chrome.driver, 10).until(EC.element_to_be_clickable(btn2))
            chrome.driver.execute_script("arguments[0].click();", btn2)
            print("Click button thứ 2 thành công")
        else:
            print("Không tìm thấy button thứ 2, thử click button đầu tiên nếu có")
            if buttons:
                chrome.driver.execute_script("arguments[0].click();", buttons[0])

    except StopIteration:
        print("Không tìm thấy button hiển thị")
    except Exception as e:
        print("Lỗi khi click:", e)

    # Thử lấy tổng件数 từ span.fb
    # count_ele = chrome.find_element('css_selector', 'span.fb', timeout=2)
    count_ele = chrome.find_element('css_selector', 'span.fb').text
    print('total_count', count_ele)
    if count_ele:
        try:
            # total_count = int(re.sub(r'([0-9]+)件.*', r'\1', count_ele.text))
            total_count = int(re.sub('([0-9])件.*', '\\1', count_ele))
        except:
            total_count = 0
    else:
        # Không có span.fb → chỉ có 1 trang
        print(f"{username}: Không tìm thấy tổng件数, giả định là 1 trang")
        bs = BeautifulSoup(chrome.driver.page_source, 'html.parser')
        job_ele_list = bs.select('table.kyujin.mt1')
        total_count = len(job_ele_list)

    print('total_count', total_count)

    # ページ数
    page_num = math.ceil(total_count/30)
    # 求人情報の辞書
    job_dict_list = []
    for i in range(1, page_num+1):
        html_source = chrome.driver.page_source
        err_count = 0
        while html_source == '<html><head></head><body></body></html>':
            err_count += 1
            if err_count == 10: raise Exception('ページが正常に表示できませんでした')
            chrome.driver.refresh()
            html_source = chrome.driver.page_source
        bs = BeautifulSoup(html_source, 'html.parser')
        job_ele_list = bs.select('table.kyujin.mt1')
        job_dict_list.extend([result for ele in job_ele_list if (result:=get_job_dict(ele))])
        # 次のページへ移動
        try:
            chrome.find_element('name', 'fwListNaviBtnNext').js_click()
            chrome.load_wait(sleep_time=0.3, timeout=60)
        except Exception as e:
            print(f'{username}: {e}')
        print(f'{username}: {i}ページ目取得完了')
    # 辞書のリストを返す
    # print(f'len of job list : {len(job_dict_list)} job list : {job_dict_list}')
    return job_dict_list


def main():
    print(f"start main")
    this_file_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(this_file_dir, 'config.ini')
    # コンフィグファイル読み込み
    config = ConfigParser()
    config.read(config_path, encoding='utf-8')
    # 記録用JSON
    job_info_json_path = config.get('LOCAL', 'job_info_json_path')
    job_info_json_path = os.path.join(this_file_dir, job_info_json_path[2:])
    selected_accounts_json      = config.get('LOCAL', 'selected_accounts_json')
    # スプレッドシートID
    spread_sheet_id      = config.get('GOOGLE', 'spread_sheet_id')
    worksheet_name       = config.get('GOOGLE', 'worksheet_name')

    service_account_json = os.path.join(this_file_dir, config.get('GOOGLE', 'service_account_json'))
    selected_accounts_path = os.path.join(this_file_dir, selected_accounts_json)
    # チャットワーク
    room_id = config.get('CHATWORK', 'room_id')
    token   = config.get('CHATWORK', 'token')
    print('コンフィグ読込完了')

    # 取得するアカウント一覧
    # account_info_path = os.path.join(this_file_dir, 'account_info.json')
    if os.path.exists(selected_accounts_path):
        with open(selected_accounts_path, 'r', encoding='utf-8') as f:
            account_info_dict = json.load(f)
    else:
        print('アカウント情報読込失敗')
        return False

    if os.path.exists(job_info_json_path):
        # JSON読み込み
        with open(job_info_json_path, 'r', encoding='utf-8') as f:
            load_job_dict = json.load(f)
    else:
        load_job_dict = {}

    print(f"on create job json {account_info_dict}")

    #code for debug
    job_dict = {}
    for account in account_info_dict:
        if account.get('id') not in load_job_dict.keys():
            print(f"Processing account {account.get('id')}")
            result = get_account_datas(account.get('id'), account.get('pw'), account.get('hw'))
            if result:
                job_dict[account.get('id')] = {'job_info': result, 'hw': account.get('hw'), 'passwd': account.get('pw')}

    # 読み込んだJSONに情報がなければ追加
    # job_dict = {
    #     account.get('id'): {'job_info': result, 'hw': account.get('hw'), 'passwd': account.get('pw')} for account in account_info_dict 
    #     if account.get('id') not in load_job_dict.keys() and (result:=get_account_datas(account.get('id'), account.get('pw')))
    # }
    new_job_dict = load_job_dict | job_dict
    # print(f"json dict : {new_job_dict}")
    # JSONファイルに出力
    with open(job_info_json_path, 'w', encoding='utf-8') as f:
        json.dump(new_job_dict, f, ensure_ascii=False, indent=4)
    
    # sys.exit("exit for debug create json")

    # 古いスプレッドシートの情報削除
    try:
        gs_util = GoogleServiceUtil(service_account_json)
        workbook = gs_util.get_spread_sheet_workbook(spread_sheet_id)
        worksheet = workbook.worksheet(worksheet_name)
        # worksheet.clear()
        # print('古い情報削除完了')

    except Exception as e:
        print('スプレッドシートの情報削除失敗')
        err_msg = f'【ハローワークスクレイピング】\nスプレッドシートの情報削除失敗\nhttps://docs.google.com/spreadsheets/d/{spread_sheet_id}\n{e}'
        Chatwork_Util.send_message_request(room_id, token, err_msg)
    return True

if __name__ == '__main__':
    main()
