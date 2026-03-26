import re
import requests
from bs4 import BeautifulSoup

HEADERS = [
    '公開ステータス', '職種', '受付年月日', '紹介期限日', '求人区分',
    '就業場所', '雇用形態', '求人番号', '基本給', '定額的に支払われる手当',
    '固定残業代', 'その他の手当等付記事項', '月平均労働日数', '賃金形態等', '通勤手当',
]

# 求人の情報を取得する
def get_job_info(data):
    url        = data.get('url')
    cookies    = data.get('cookies')
    open_range = data.get('open_range')

    session = requests.Session()
    for k, v in cookies.items():
        session.cookies.set(k, v)

    result_dict = {header: '' for header in HEADERS}
    result_dict['公開ステータス'] = data.get('status')
    # result_dict['公開範囲'] = data.get('open_range')
    try:
        print(f'getting job info from {url} ...')
        # response = requests.post(url, cookies=cookies)
        response = session.get(url)
        bs = BeautifulSoup(response.content, 'html.parser')
        print(f"html content: {bs.prettify()}")
        # テーブルから必要な情報取得
        # tgt_ele_list = [ele for ele in bs.select('.normal.mb1 th') if re.sub('(.+)（.+）', '\\1', ele.text.strip()) in HEADERS]

        tgt_ele_list = [
            ele for ele in bs.select('table.normal.mb1 th')
            if normalize_header(ele.text) in HEADERS
        ]
        print(f'target element list: {tgt_ele_list}')
        for tgt_ele in tgt_ele_list:
            key    = re.sub('(.+)（.+）', '\\1',tgt_ele.text.strip())
            parent = tgt_ele.parent
            val    = td_list[0].get_text(separator='\n', strip=True) if (td_list:=parent.select('td')) else ''
            result_dict[key] = val
        print(f'取得成功: {url}')

        print(f'detail data : {result_dict}')
        return result_dict

    except Exception as e:
        print(f'取得失敗: {url}\n{e}')
        return {}

def normalize_header(text):
    text = text.strip()
    text = re.sub(r'（.*?）', '', text)  # bỏ ngoặc
    text = text.replace('\u3000', '')   # bỏ full-width space
    text = re.sub(r'\s+', '', text)     # bỏ mọi khoảng trắng
    return text

def get_job_info_with_selenium(chrome, data):
    url = data.get('url')
    result_dict = {header: '' for header in HEADERS}
    result_dict['公開ステータス'] = data.get('status')

    try:
        chrome.open_url(url)
        bs = BeautifulSoup(chrome.driver.page_source, 'html.parser')
        for ele in bs.select('table.normal.mb1 th'):
            key = normalize_header(ele.text)
            if key in HEADERS:
                val = ele.find_next("td").get_text(strip=True)
                result_dict[key] = val
        return result_dict
    except Exception as e:
        print(f"取得失敗 {url}: {e}")
        return {}