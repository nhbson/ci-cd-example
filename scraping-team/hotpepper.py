from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import re
import requests
from time import sleep

from chatwork import Chatwork


def site_scraping():
    with GetJobs() as gjs:
        area_dict = gjs. area_dict()
        for area in area_dict:
            area_url = area_dict[area]
            job_links = gjs.get_job_links(area_url)
            jobs = gjs.get_jobs(job_links, area)
            gjs.update_spreadsheet(jobs, area)


class GetJobs():
    def __init__(self):
        # Chatwork
        self.chatwork = Chatwork(
            os.environ['CHATWORK_RID'],
            os.environ['METHOD_NAME'],
            os.environ['CHATWORK_TOKEN']
        )
        # SpreadSheet
        self.gc = gspread.authorize(ServiceAccountCredentials.from_json_keyfile_name(
                'service-account.json',
                [
                    'https://spreadsheets.google.com/feeds',
                    'https://www.googleapis.com/auth/drive'
                ]
            )
        )
        self.sheet_id   = '14OHoOhmtEgTA8U3Y0aQexUm2AtzlHQ8m44SVh0bfnwg'

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        self.driver.close()
        self.driver.quit()
        print('with構文のデストラクターにてchromedriverを終了させました。')

    def area_dict(self):
        return {

            # '札幌'  : 'https://www.hotpepper.jp/SA41/Y505/lst/',
            # '仙台'  : 'https://www.hotpepper.jp/SA53/Y550/lst/',
            # '東京'  : 'https://www.hotpepper.jp/SA11/lst/',
            # '神奈川': 'https://www.hotpepper.jp/SA12/lst/',
            '埼玉'  : 'https://www.hotpepper.jp/SA13/lst/',
            '千葉'  : 'https://www.hotpepper.jp/SA14/lst/',
            '名古屋': 'https://www.hotpepper.jp/SA33/Y200/lst/',
            '大阪'  : 'https://www.hotpepper.jp/SA23/lst/',
            # '京都'  : 'https://www.hotpepper.jp/SA22/lst/',
            # '神戸'  : 'https://www.hotpepper.jp/SA24/Y370/lst/',
            # '姫路'  : 'https://www.hotpepper.jp/SA24/Y850/lst',
            # '広島'  : 'https://www.hotpepper.jp/SA74/lst/',
            # '博多'  : 'https://www.hotpepper.jp/SA91/Y700/lst/',
            # '北九州': 'https://www.hotpepper.jp/SA91/Y730/lst/',
        }

    def get_job_links(self, area_url):
        session = requests.Session()
        response = session.get(area_url)
        soup = BeautifulSoup(response.content, 'html.parser')

        all_nums = int(soup.select_one(".fcLRed.bold.fs18.padLR3").text.replace(',', ''))
        print(all_nums)
        desplay = 20
        click_nums = int(all_nums // desplay) + 1
        print(click_nums)
        job_list_links = [area_url + "bgn" + str(page) for page in range(1, click_nums + 1)]

        session = requests.Session()
        job_links = set()
        with ThreadPoolExecutor(max_workers=30) as executor:
            futures = {executor.submit(self.fetch_page, url, session): url for url in job_list_links}
            count = 0
            for future in as_completed(futures):
                try:
                    page_content = future.result()
                    new_job_links = self.extract_job_links(page_content, job_links)
                    job_links.update(new_job_links)
                    print("current_page:" + str(count))
                    count += 1
                    sleep(0.5)
                except Exception as e:
                    print(e)
                # テスト用
                # if count >= 1:
                #     break
        return list(job_links)

    def fetch_page(self, url, session):
        response = session.get(url)
        return response.content

    def extract_job_links(self, page_content, existing_links):
        soup = BeautifulSoup(page_content, 'html.parser')
        job_urls_elem = soup.select(".shopDetailStoreName > a")
        job_urls = []
        for url_elem in job_urls_elem:
            if 'href' in url_elem.attrs:
                job_url = "https://www.hotpepper.jp/" + url_elem['href']
                if job_url not in existing_links:
                    job_urls.append(job_url)
        return job_urls

    def get_jobs(self, urls, categoly):
        spread_job_urls = self.spread_job_urls(categoly)
        insert_dict = self.header_list()
        def fetch_job_info(url):
            job = []
            if url not in spread_job_urls:
                try:
                    session = requests.Session()
                    response = session.get(url)
                    soup = BeautifulSoup(response.content, 'html.parser')
                    # teble
                    table_list = self.table_list()
                    job = self.add_table_info(soup, table_list)
                except BaseException as e:
                    print(e)
                    print(url)
            if job:
                job.insert(0, url)
            return job

        with ThreadPoolExecutor(max_workers=30) as executor:
            count = 0
            futures = [executor.submit(fetch_job_info, url) for url in urls]
            for future in as_completed(futures):
                job = future.result()
                if job:
                    insert_dict.append(job)
                    sleep(0.5)
                    print("job_cocunt:" + str(count))
                    count += 1
        return insert_dict

    def spread_job_urls(self,categoly):
        sheet_name      = categoly
        worksheet       = self.gc.open_by_key(self.sheet_id).worksheet(sheet_name)
        spread_values   = worksheet.get_all_values()
        spread_job_urls = [row_values[0].replace(' ', '') for row_values in spread_values]
        return spread_job_urls

    def header_list(self):
        return [
            [
                'URL',
                '席数',
                '営業時間',
                '予算',
                '電話番号',
                '店舗名',
                '住所',
            ],
        ]

    def table_list(self):
        return [
            {
                "column_list": ["総席数", "営業時間", "平均予算", "電話", "店名", "住所"],
                "th_selector": "table.infoTable tr th",
                "td_selector": "table.infoTable tr td"
            },
        ]

    def add_table_info(self, soup, table_list: list):
        job = []  # jobをここで初期化する
        for table in table_list:
            th_tags = soup.select(table["th_selector"])
            item_columns = [th_tag.get_text(strip=True) for th_tag in th_tags]
            td_tags = soup.select(table["td_selector"])
            item_names = [td_tag.get_text(strip=True) for td_tag in td_tags]
            for column in table["column_list"]:
                data = ''
                if column in item_columns:
                    idx = item_columns.index(column)
                    data = item_names[idx]
                if column == '総席数':
                    seat = data.split('席')[0].split('（')
                    number = re.findall(r'\d+', seat[0])
                    if number and int(seat[0]) < 15:
                        return []
                elif column == '電話':
                    tel_link = soup.find('a', onclick="customLinkLog('telinfo_disp')")['href']
                    tel_link = 'https://www.hotpepper.jp/' + tel_link
                    tel_response = requests.get(tel_link)
                    sleep(1)
                    tel_soup = BeautifulSoup(tel_response.content, 'html.parser')
                    for element in tel_soup.select('.telephoneNumber'):
                        data = element.get_text(strip=True)
                job.append(data)
        return job

    def update_spreadsheet(self, jobs ,categoly):
        sheet_name      = categoly
        worksheet       = self.gc.open_by_key(self.sheet_id).worksheet(sheet_name)
        spread_values   = worksheet.get_all_values()
        spread_job_urls = [row_values[0].replace(' ', '') for row_values in spread_values]
        spread_row_num  = len(spread_job_urls)

        insert_data = []
        for job in jobs:
            site_job_url = job[0]
            if site_job_url not in spread_job_urls and job[1] != '':
                insert_data.append(job)
        if insert_data:
            print(insert_data)
            worksheet.insert_rows(insert_data, spread_row_num + 1)
            message = sheet_name + 'が更新されました'
            self.chatwork.send_alert(True, message)


if __name__ == '__main__':
    os.environ['CHATWORK_TOKEN'] = "aa07226db4f595140cde0323e30948a7"
    os.environ['CHATWORK_RID']   = "258334146"
    os.environ['METHOD_NAME']    = "hotpepper"
    site_scraping()
