from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import re
from selenium.webdriver.common.by import By
from time import sleep

from common_scraping import CommonScraping


def set_environment_variables():
    os.environ['BASE_URL']       = 'https://job.mynavi.jp'
    os.environ['CHATWORK_RID']   = '258334146'
    os.environ['CHATWORK_TOKEN'] = 'aa07226db4f595140cde0323e30948a7'
    os.environ['SPREAD_ID']      = '14OHoOhmtEgTA8U3Y0aQexUm2AtzlHQ8m44SVh0bfnwg'
    # os.environ['SHEET_NAME']     = 'シート1'
    os.environ['SHEET_NAME']     = 'サンプル'

def site_scraping():
    try:
        with GetJobs() as gjs:
            gjs.search_jobs()
            job_links = gjs.get_job_links()
            if not job_links:
                return
            jobs = gjs.get_jobs(job_links)
            if not jobs:
                return
            gjs.insert_spreadsheet(jobs)
    except BaseException as e:
        gjs.cs.error_catch(e, "GetJobs実行時エラー")


class GetJobs():
    def __init__(self):
        # CommonScraping
        caller_file = os.path.basename(__file__)
        self.cs = CommonScraping(caller_file)

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        self.cs.print_and_log_info('GetJobs()終了')

    def search_jobs(self):
        try:
            self.cs.print_and_log_info("-----search_jobs-----")
            self.cs.driver.get("https://job.mynavi.jp/27/pc/toppage/displayTopPage/index")
            sleep(3)

            self.cs.driver.find_element(By.CSS_SELECTOR, "#srchWord").send_keys("ドライバー")
            sleep(2)

            search_type_trgs = self.cs.driver.find_elements(By.CSS_SELECTOR, "li.searchTopCorpCr")
            for search_type_trg in search_type_trgs:
                search_type_text = search_type_trg.find_element(By.CSS_SELECTOR, "span").text
                print(search_type_text)
                if search_type_text == "エリア":
                    search_type_trg.click()
                    sleep(2)
                    self.set_search_area()
                elif search_type_text == "職種":
                    search_type_trg.click()
                    sleep(2)
                    self.set_search_checkbox()

            search_button = self.cs.driver.find_element(By.CSS_SELECTOR, "#doSearch")
            self.cs.driver.execute_script("arguments[0].scrollIntoView();", search_button)
            sleep(2)
            search_button.click()
            sleep(5)
        except Exception as e:
            self.cs.error_catch(e, "求人検索時エラー")

    def set_search_area(self):
        try:
            area_divs = self.cs.driver.find_elements(By.CSS_SELECTOR, ".list.pre.area .listInner")
            for area_div in area_divs:
                area_button = area_div.find_element(By.CSS_SELECTOR, "h6")
                area_text = area_button.text
                if area_text in ["北海道・東北", "関東", "甲信越・北陸", "東海・中部", "近畿", "中国・四国", "九州・沖縄"]:
                    area_button.click()
                    sleep(2)
                    pref_lis = area_div.find_elements(By.CSS_SELECTOR, ".eachArea")
                    for pref_li in pref_lis:
                        pref_text = pref_li.find_element(By.CSS_SELECTOR, "a").text
                        print(pref_text)
                        if area_text == "北海道・東北":
                            if pref_text in ["北海道", "岩手", "宮城", "山形", "福島"]:
                                self.click_elem(pref_li, ".area")
                        elif area_text == "関東":
                            if pref_text in ["茨城", "栃木", "群馬", "埼玉", "千葉", "東京", "神奈川"]:
                                self.click_elem(pref_li, ".area")
                        elif area_text == "甲信越・北陸":
                            if pref_text in ["山梨"]:
                                self.click_elem(pref_li, ".area")
                        elif area_text == "東海・中部":
                            if pref_text in ["岐阜", "静岡", "愛知", "三重"]:
                                self.click_elem(pref_li, ".area")
                        elif area_text == "近畿":
                            if pref_text in ["滋賀", "滋賀", "大阪", "兵庫", "奈良", "和歌山"]:
                                self.click_elem(pref_li, ".area")
                        elif area_text == "中国・四国":
                            if pref_text in ["島根", "岡山", "広島", "山口", "香川", "愛媛", "高知"]:
                                self.click_elem(pref_li, ".area")
                        elif area_text == "九州・沖縄":
                            if pref_text in ["福岡", "佐賀", "長崎", "熊本", "大分", "宮崎"]:
                                self.click_elem(pref_li, ".area")
        except Exception as e:
            self.cs.error_catch(e, "エリア検索時エラー")

    def click_elem(self, elem, input_selector):
        self.cs.driver.execute_script("arguments[0].scrollIntoView();", elem)
        sleep(2)
        pref_input = elem.find_element(By.CSS_SELECTOR, input_selector)
        pref_input.click()
        sleep(2)

    def set_search_checkbox(self):
        try:
            job_type_divs = self.cs.driver.find_elements(By.CSS_SELECTOR, "#indGroupEx3 .listInner")
            for job_type_div in job_type_divs:
                job_type_button = job_type_div.find_element(By.CSS_SELECTOR, "h6")
                job_type_text = job_type_button.text
                if job_type_text in ["事務・管理系", "販売・サービス系"]:
                    job_type_button.click()
                    sleep(2)
                    job_detail_lis = job_type_div.find_elements(By.CSS_SELECTOR, ".eachOcc")
                    for job_detail_li in job_detail_lis:
                        job_detail_text = job_detail_li.find_element(By.CSS_SELECTOR, "a").text
                        if job_type_text == "事務・管理系":
                            if job_detail_text in ["物流・在庫管理"]:
                                self.click_elem(job_detail_li, ".occ")
                        elif job_type_text == "販売・サービス系":
                            if job_detail_text in ["ドライバー"]:
                                self.click_elem(job_detail_li, ".occ")
                if job_type_text == "販売・サービス系":
                    break
        except Exception as e:
            self.cs.error_catch(e, "職種検索時エラー")

    def get_job_links(self):
        self.cs.print_and_log_info("-----get_job_links-----")
        job_links = []
        try:
            all_num = self.cs.driver.find_element(By.CSS_SELECTOR, "#searchResultkensuu").text
            all_num = all_num.replace("社", "")
            self.cs.print_and_log_info(f"all_num: {all_num}")

            display_num = 100
            joblist_num = int(all_num) // display_num + 1
            self.cs.print_and_log_info(f"joblist_num: {str(joblist_num)}")

            current_page = 1
            while joblist_num + 2 > current_page:
                try:
                    job_url_selector = ".js-add-examination-list-text"
                    job_url_elems = self.cs.driver.find_elements(By.CSS_SELECTOR, job_url_selector)
                    job_urls = [url_elem.get_attribute("href") for url_elem in job_url_elems]
                    job_links += job_urls
                    self.cs.print_and_log_info(f"current_page: {str(current_page)}")
                    # Use below code for test.
                    # if current_page == 1:
                    #     break
                    current_page += 1
                    self.cs.driver.find_element(By.CSS_SELECTOR, "#upperNextPage").click()
                    sleep(5)
                except Exception as e:
                    self.cs.error_catch(e, f"An error occurred: {str(e)}")
                    break
        except Exception as e:
            self.cs.error_catch(e, "求人URL取得時エラー")
        return list(job_links)

    def get_jobs(self, urls: list):
        self.cs.print_and_log_info("-----get_jobs-----")
        jobs = []
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(self.fetch_job_info, url) for url in urls]
            for future in as_completed(futures):
                job = future.result()
                if job:
                    jobs.append(job)
                    self.cs.print_and_log_info(f"job_count: {str(len(jobs))}")
        return jobs

    def fetch_job_info(self, url):
        job = []
        try:
            response = self.cs.fetch_page(url)
            soup = BeautifulSoup(response, 'html.parser')
            # teble以外
            company = self.get_block_info(soup, ".heading1-inner-left h1")
            hp_url = self.get_block_info(soup, "#accessInfoListDescText120")
            job_type = self.get_block_info(soup, "#crpRecruitingTypeCd10")
            title = self.get_block_info(soup, "#courseTitle .title")
            descripiton = self.get_block_info(soup, "#shokushu p")

            company_href = soup.select_one("#headerOutlineTabLink")["href"]
            company_url = os.environ['BASE_URL']  + company_href
            response = self.cs.fetch_page(company_url)
            soup = BeautifulSoup(response, 'html.parser')
            # teble以外
            tel = self.get_block_info(soup, "#corpDescDtoListDescText220")
            address = self.get_block_info(soup, "#corpDescDtoListDescText50")

            job = [company, tel, address, hp_url, job_type , title, descripiton, url]
        except Exception as e:
            self.cs.error_catch(e, f"An error occurred: {str(e)}")
        return job

    def get_block_info(self, soup, selector):
        info = ""
        try:
            info = soup.select_one(selector).get_text(strip=True, separator="\n")
        except:
            pass
        return info

    def insert_spreadsheet(self, jobs):
        self.cs.print_and_log_info("-----insert_spreadsheet-----")
        try:
            self.cs.spread.append_rows(jobs)
            message = "更新されました"
            self.cs.chatwork.send_alert(True, message)
        except Exception as e:
            self.cs.error_catch(e, f"An error occurred: {str(e)}")


if __name__ == '__main__':
    set_environment_variables()
    site_scraping()
