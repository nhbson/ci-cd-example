import gc
import sys
import wx
import wx.adv
import re
import threading
from oauth2client.service_account import ServiceAccountCredentials
from plyer import notification
from os import path, remove, system
import json
from configparser import ConfigParser
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from configparser import ConfigParser
from create_jobs_json import login_with_cookies, COOKIES_FILE
from get_job_info import get_job_info, get_job_info_with_selenium
from util.chrome_util import Chrome_Util
from util.google_service_util import GoogleServiceUtil
from create_jobs_json import main
from time import sleep
from threading import Lock


USERNAME = 'vietnam-bpo'
PASSWORD = 'bpo1234!'

ACCOUNTS = []
scope = [
    'https://spreadsheets.google.com/feeds',
    'https://www.googleapis.com/auth/drive',
]
# GET information in config
dir_path = path.dirname(path.abspath(__file__) )
# Get accounts
account_info_path = path.join(dir_path, 'account_info.json')
if path.exists(account_info_path):
    with open(account_info_path, 'r', encoding='utf-8') as f:
        ACCOUNTS = json.load(f)

config_path = path.join(dir_path, 'config.ini')
# コンフィグファイル読み込み
config = ConfigParser()
config.read(config_path, encoding='utf-8')
worksheet_name       = config.get('GOOGLE', 'worksheet_name')
spread_sheet_id      = config.get('GOOGLE', 'spread_sheet_id')
service_account_path    = config.get('GOOGLE', 'service_account_json')
selected_accounts_path = path.join(dir_path, config.get('LOCAL', 'selected_accounts_json'))
SERVICEACCOUNT_JSON = path.join(dir_path, service_account_path)

credentials = ServiceAccountCredentials.from_json_keyfile_name(SERVICEACCOUNT_JSON, scope)

def push_Noti(msg):
    notification.notify(
    title= 'HelloWork_Panasonic_Age',
    message= msg,
    timeout= 30
)

class SuccessDialog(wx.Dialog):
    def __init__(self, parent, message, title):
        super(SuccessDialog, self).__init__(parent, title=title, size=(250, 150))

        self.panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        if(title == 'Error'):
            self.icon = wx.StaticBitmap(self.panel, bitmap=wx.ArtProvider.GetBitmap(wx.ART_ERROR, wx.ART_OTHER, (20, 20)))
        else:
            self.icon = wx.StaticBitmap(self.panel, bitmap=wx.ArtProvider.GetBitmap(wx.ART_INFORMATION, wx.ART_OTHER, (20, 20)))
        sizer.Add(self.icon, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

        self.label = wx.StaticText(self.panel, label=message)
        sizer.Add(self.label, 1, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

        self.ok_button = wx.Button(self.panel, wx.ID_OK, label="OK", pos=(150, 80))

        self.Bind(wx.EVT_BUTTON, self.on_ok, self.ok_button)
        self.panel.SetSizerAndFit(sizer)

        self.Center()
        self.ShowModal()

    def on_ok(self, event):
        self.EndModal(wx.ID_OK)

class MyFrame(wx.Frame):
    def __init__(self, parent, title):
        super(MyFrame, self).__init__(parent, title=title, size=(400, 650))
        self.SetIcon(wx.Icon("DYM.ico", wx.BITMAP_TYPE_ICO))
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        # Select Box for status
        hbox_status = wx.BoxSizer(wx.HORIZONTAL)
        status_label = wx.StaticText(panel, label="Select Status: ")
        font = status_label.GetFont()
        status_label.SetFont(font)  # dùng lại font in đậm từ trên
        status_label.SetForegroundColour(wx.Colour(0, 102, 204))

        status_choices = ["有効中 - public", "無効 - hidden", "all"]
        self.status_choice = wx.Choice(panel, choices=status_choices)
        self.status_choice.SetSelection(0)
        self.status_choice.Bind(wx.EVT_CHOICE, self.on_status_change)

        # Add vào hbox
        hbox_status.Add(status_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        hbox_status.Add(self.status_choice, 0, wx.ALIGN_CENTER_VERTICAL)

        # Thêm vào layout chính
        vbox.Add(hbox_status, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # Check box
        self.checkboxes = {}
        acc_label = wx.StaticText(panel, pos=(0,15),size=(100, 15), label="Select accounts:")
        font = acc_label.GetFont()
        font.MakeBold()
        acc_label.SetFont(font)
        acc_label.SetForegroundColour(wx.Colour(0, 102, 204))

        vbox.Add(acc_label, 0, wx.ALIGN_LEFT | wx.ALL, 10)

        # GridSizer cho checkbox: 0 hàng, 2 cột (auto chia dòng)
        grid_cb = wx.GridSizer(cols=2, hgap=5, vgap=5)

        for obj in ACCOUNTS:
            cb = wx.CheckBox(panel, label=obj['hw'])
            grid_cb.Add(cb, 0, wx.ALL, 5)
            self.checkboxes[cb] = obj
            # cb.Bind(wx.EVT_CHECKBOX, self.on_checkbox_click)  # bind event

        vbox.Add(grid_cb, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 5)

        line1 = wx.StaticLine(panel)
        vbox.Add(line1, 0, wx.EXPAND | wx.ALL, 5)

        # Buttons
        hbox_buttons = wx.BoxSizer(wx.HORIZONTAL)
        # self.btn_run = wx.Button(panel, label='Run by year')
        self.select_all_acc = wx.Button(panel, label="Select All")
        self.unselect_all_acc = wx.Button(panel, label="Unselect All")

        hbox_buttons.Add(self.select_all_acc, 0, wx.ALIGN_CENTER | wx.ALL, 5)
        hbox_buttons.Add(self.unselect_all_acc, 0, wx.ALIGN_CENTER | wx.ALL, 5)

        vbox.Add(hbox_buttons, 0, wx.ALIGN_CENTER | wx.ALL, 5)

        # Button to clear sheet
        # self.btn_clear_sheet = wx.Button(panel, label='Clear sheet')
        # vbox.Add(self.btn_clear_sheet, 0, wx.ALIGN_CENTER | wx.ALL, 5)
        # Button to run step 1 (Create job json file)
        self.btn_run_step_1 = wx.Button(panel, label='Run')
        self.btn_continue = wx.Button(panel, label='  Run Remaining  ')
        # self.btn_continue = wx.Button(panel, label='  Continue  ')

        hbox_buttons_2 = wx.BoxSizer(wx.HORIZONTAL)
        hbox_buttons_2.Add(self.btn_run_step_1, 0, wx.ALIGN_CENTER | wx.ALL, 5)
        hbox_buttons_2.Add(self.btn_continue, 0, wx.ALIGN_CENTER | wx.ALL, 5)

        vbox.Add(hbox_buttons_2, 0, wx.ALIGN_CENTER | wx.ALL, 5)

        # vbox.Add(self.btn_run_step_1, 0, wx.ALIGN_CENTER | wx.ALL, 5)

        panel.SetSizer(vbox)
        # Button to run step 2 (Update sheets)
        # self.btn_run_step_2 = wx.Button(panel, label='Run step 2 to complete')
        # vbox.Add(self.btn_run_step_2, 0, wx.ALIGN_CENTER | wx.ALL, 5)

        panel.SetSizer(vbox)
        # self.btn_run_step_2.Disable()
        # Progress Status
        hbox_progress = wx.BoxSizer(wx.HORIZONTAL)

        # Text
        running_text = wx.StaticText(panel, label="Running:")
        font = running_text.GetFont()
        font.MakeBold()
        running_text.SetFont(font)
        running_text.SetForegroundColour(wx.Colour(0, 128, 0))

        hbox_progress.Add(running_text, 0, wx.ALIGN_LEFT | wx.ALL, 5)
        self.done_ev = wx.StaticText(panel, label="0    ")
        hbox_progress.Add(self.done_ev, 0, wx.ALIGN_LEFT | wx.ALL, 5)
        char_text = wx.StaticText(panel, label="/")
        hbox_progress.Add(char_text, 0, wx.ALIGN_LEFT | wx.ALL, 5)
        self.total_ev = wx.StaticText(panel, label="    0")
        hbox_progress.Add(self.total_ev, 0, wx.ALIGN_LEFT | wx.ALL, 5)

        # hbox_progress.Add(self.selected_user, 0, wx.ALIGN_LEFT | wx.ALL, 5)
        vbox.Add(hbox_progress, 0, wx.ALIGN_LEFT | wx.ALL, 5)
        panel.SetSizer(vbox)

        # ========== Hiển thị trạng thái ==========
        hbox_progress = wx.BoxSizer(wx.HORIZONTAL)
        self.status_job = wx.StaticText(panel, size=(200, 20), label="")
        font = self.status_job.GetFont()
        font.MakeBold()
        self.status_job.SetFont(font)
        self.status_job.SetForegroundColour(wx.Colour(255, 0, 0))
        hbox_progress.Add(self.status_job, 0, wx.ALIGN_CENTER | wx.ALL, 5)
        vbox.Add(hbox_progress, 0, wx.ALIGN_LEFT | wx.ALL, 5)
        panel.SetSizer(vbox)

        # Binding
        self.select_all_acc.Bind(wx.EVT_BUTTON, self.on_select_all)
        self.unselect_all_acc.Bind(wx.EVT_BUTTON, self.on_unselect_all)
        self.btn_run_step_1.Bind(wx.EVT_BUTTON, self.on_run)
        self.btn_continue.Bind(wx.EVT_BUTTON, self.on_run_remaining)
        # self.btn_clear_sheet.Bind(wx.EVT_BUTTON, self.clear_sheet)
        self.selected = []

    def on_status_change(self, event):
        selected_status = self.status_choice.GetStringSelection()
        self.selected_status = selected_status
        self.add_debug_message(f"Selected status: {selected_status}")
        print(f"[DEBUG] User selected status: {selected_status}")

    def on_checkbox_click(self, event):
        cb = event.GetEventObject()  # checkbox vừa được click
        label = self.checkboxes[cb]  # lấy info kèm theo từ dict
        state = "checked" if cb.IsChecked() else "unchecked"
        # print(f"Checkbox clicked: {label} ({state})")

    # def run_script(self, script, callback):
    #     # Run the script
    #     process = subprocess.Popen([sys.executable, script])
    #     # process = subprocess.Popen(['python', script])
    #     process.wait()  # Wait for the script to complete
    #     wx.CallAfter(callback)  # Safely call the callback in the main thread

    # def run_script_2(self, script, callback):
    #     # Run the script
    #     process = subprocess.Popen([sys.executable, script])
    #     process.wait()  # Wait for the script to complete
    def on_select_all(self, event):
        self.add_debug_message("Select all accounts")
        for cb in self.checkboxes:
            cb.SetValue(True)  # Check all checkboxes

    def on_unselect_all(self, event):
        self.add_debug_message("Unselect all accounts")
        for cb in self.checkboxes:
            cb.SetValue(False)  # Uncheck all checkboxes

    def clear_sheet(self, event):
        try:
            gs_util = GoogleServiceUtil(SERVICEACCOUNT_JSON)
            workbook = gs_util.get_spread_sheet_workbook(spread_sheet_id)
            worksheet = workbook.worksheet(worksheet_name)
            worksheet.clear()
        except: pass

    def process_each_user(self, isContinue):
        for user in self.selected:
            self.update_done_sum('0')
            self.update_total_sum('0')
            # self.update_selected_user(user["hw"])
            with open(selected_accounts_path, 'w', encoding='utf-8') as f:
                json.dump([user], f, ensure_ascii=False, indent=4)
            try:
                self.add_debug_message(f"Processing user: {user['hw']}")
                main()
            except:
                self.retry()
            self.add_debug_message(f"Processing scrap detail data and update sheet....")
            self.update_sheet(isContinue)
        self.done_step_2()

    def get_info_script(self, user):
        main()

    def on_run(self, e):
        self.update_total_sum('0')
        self.update_done_sum('0')
        self.btn_run_step_1.Disable()
        self.btn_continue.Disable()
        # self.btn_run_step_2.Disable()
        self.selected = [ obj for cb, obj in self.checkboxes.items() if cb.IsChecked()]
        if self.selected:
            try:
                threading.Thread(target=self.process_each_user, args=([False])).start()
            except:
                self.retry()
        else: self.retry()

    def on_run_remaining(self, e):
        self.update_total_sum('0')
        self.update_done_sum('0')
        self.btn_run_step_1.Disable()
        self.btn_continue.Disable()
        self.selected = [ obj for cb, obj in self.checkboxes.items() if cb.IsChecked()]
        if self.selected:
            try:
                threading.Thread(target=self.process_each_user, args=([True])).start()
            except:
                self.retry()
        else: self.retry()

    def update_total_sum(self, value):
        self.total_ev.SetLabel(value)
        self.Fit()
        self.Layout()  # Update layout to reflect changes

    def update_done_sum(self, value):
        self.done_ev.SetLabel(value)
        self.Fit()
        self.Layout()  # Update layout to reflect changes

    def update_selected_user(self, value):
        # self.selected_user.SetLabel(value)
        self.Fit()
        self.Layout()  # Update layout to reflect changes

    def close(self):
        wx.CallAfter(self.openNotice, "Process completed!", 'Success')
        self.btn_run_step_1.Enable()

    def openNotice(self, msg, title):
        push_Noti(msg)
        dlg = SuccessDialog(self, msg, title)
        # self.Close()

    def retry(self):
        wx.CallAfter(self.openNotice, "Something failed! Please try again!", 'Error')
        self.btn_run_step_1.Enable()
        self.btn_continue.Enable()

    def done_step_1(self):
        wx.CallAfter(self.openNotice, "Please click Run step 2 to continue", 'Success')
        self.btn_run_step_1.Enable()
        self.btn_continue.Enable()

    def done_step_2(self):
        wx.CallAfter(self.openNotice, "Process completed", 'Success')
        self.btn_run_step_1.Enable()
        self.btn_continue.Enable()

    def update_sheet(self, isContinue, status=None):
        this_file_dir = path.dirname(path.abspath(__file__))
        config_path = path.join(this_file_dir, 'config.ini')
        # コンフィグファイル読み込み
        config = ConfigParser()
        config.read(config_path, encoding='utf-8')
        # 最大並列数
        max_workers = int(config.get('LOCAL', 'max_workers'))
        # 記録用JSON
        job_info_json_path = config.get('LOCAL', 'job_info_json_path')
        # スプレッドシートID
        spread_sheet_id      = config.get('GOOGLE', 'spread_sheet_id')
        service_account_json = path.join(this_file_dir, config.get('GOOGLE', 'service_account_json'))
        worksheet_name_from_config = config.get('GOOGLE', 'worksheet_name')
        job_info_json_path = path.join(this_file_dir, job_info_json_path[2:])
        load_job_dict = {}
        key_list = []
        print('コンフィグ読込完了')
        self.add_debug_message('Add cookie and login')

        if status is None:
            status = getattr(self, "selected_status", "有効中 - public")

        print(f"[DEBUG] update_sheet called with status={status}")
        self.add_debug_message(f"update_sheet status: {status}")

        if path.exists(job_info_json_path):
            # JSON読み込み
            with open(job_info_json_path, 'r', encoding='utf-8') as f:
                load_job_dict = json.load(f)
                key_list = list(load_job_dict.keys())
                if not key_list:
                    print('JSONの中身が存在しません')
                    return False
        else:
            print('JSONファイルが存在しません')
            return False


        for key in key_list:
            try:
                # 対象のユーザを決定
                user_dict = load_job_dict.get(key, {})
                print(f'on update_sheet {user_dict.get("hw"), user_dict.get("passwd")}')
                hw     = user_dict.get('hw')
                passwd = user_dict.get('passwd')
                job_info_list = user_dict.get('job_info')
                current_worksheet_name = f'scraiping_{hw}'
                job_info_list_raw = user_dict.get('job_info', [])

                # SỬA ĐỔI QUAN TRỌNG: Lọc các bản ghi trùng lặp dựa trên URL
                seen_urls = set()
                job_info_list_filtered = []
                for job_info in job_info_list_raw:
                    url = job_info.get('URL')
                    if url and url not in seen_urls:
                        job_info_list_filtered.append(job_info)
                        seen_urls.add(url)
                    else:
                        self.add_debug_message(f"Skipped duplicate URL: {url}")

                # Cập nhật danh sách công việc đã lọc
                job_info_list = job_info_list_filtered

                # クロームドライバ生成
                options_list = [
                    '--headless',
                    # '--no-sandbox',
                    # '--disable-gpu',
                    # '--single-process',
                    # '--disable-dev-shm-usage',
                    # '--disable-dev-tools',
                ]
                chrome = Chrome_Util(options_str_list=options_list)
                login_with_cookies(chrome, key, passwd, COOKIES_FILE)
                print(f"Đã login {key}")
                self.add_debug_message(f"Had login with {key}")

                selenium_cookies = chrome.driver.get_cookies()
                cookies = {c['name']: c['value'] for c in selenium_cookies}

                job_page_list = [{
                    'url'       : job_info.get('URL'),
                    'cookies'   : cookies,
                    'status'    : job_info.get('公開ステータス'),
                    'open_range': job_info.get('公開範囲'),
                } for job_info in job_info_list]

                # Lấy trạng thái đã chọn từ GUI
                status_filter = getattr(self, "selected_status", "有効中 - public")
                print(f"[DEBUG] status_filter from GUI: {status_filter}")

                if status_filter != "all":
                    # Ánh xạ display label -> actual value trong job_info
                    mapping = {
                        "有効中 - public": "公開中",
                        "無効 - hidden": "無効"
                    }
                    actual_status = mapping.get(status_filter)
                    before_len = len(job_page_list)
                    job_page_list = [job for job in job_page_list if job.get("status") == actual_status]
                    after_len = len(job_page_list)

                    print(f"[DEBUG] Filtered job_page_list by status='{actual_status}', remain {after_len}/{before_len}")
                    self.add_debug_message(f"Filtered job_page_list by status='{actual_status}', remain {after_len}/{before_len}")
                else:
                    print(f"[DEBUG] No status filter applied, total jobs={len(job_page_list)}")
                    self.add_debug_message(f"No status filter applied, total jobs={len(job_page_list)}")

                print(f'{len(job_page_list)}件スクレイピング開始\nMAX_WORKER: {max_workers}')
                self.add_debug_message(f'{len(job_page_list)}件スクレイピング開始\nMAX_WORKER: {max_workers}')

                csv_file_path = path.join(this_file_dir, f'{key}_output.csv')
                unAuth = False
                try:
                    gs_util = GoogleServiceUtil(service_account_json)
                    workbook = gs_util.get_spread_sheet_workbook(spread_sheet_id)
                    try:
                        worksheet = workbook.worksheet(current_worksheet_name)
                    except:
                        print('求人一覧のシートを追加します')
                        workbook.add_worksheet(title=current_worksheet_name, rows='5', cols='5')
                        worksheet = workbook.worksheet(current_worksheet_name)
                except Exception as e:
                    print(f"Authentication error: {e}")
                    unAuth = True

                def get_job_id(url):
                    job_number = ''
                    try:
                        job_number = re.search(r'kjNo=(\d{5}-\d+)', url).group(1)
                    except: pass
                    return job_number

                if isContinue :
                    IDS = worksheet.col_values(9)
                    print(f"IDS on sheet: {IDS}")
                    IDS_set = set(IDS)
                    def is_existed_in_sheet(jobId):
                        return jobId in IDS_set
                    res = [ele for ele in job_page_list if not is_existed_in_sheet(get_job_id(ele.get('url')))]
                    job_page_list = res
                    self.update_total_sum(f'{len(res)}')

                # Bắt đầu thu thập tất cả kết quả
                lock = Lock()
                all_results_for_sheet = []
                count = 0

                # Using multithreads
                # with ThreadPoolExecutor(max_workers=max_workers) as executor:
                #     futures = [executor.submit(get_job_info_with_selenium, chrome, data) for data in job_page_list]
                #     for future in as_completed(futures):
                #         try:
                #             result = future.result()
                #             if result:
                #                 with lock:  # Đảm bảo chỉ một thread append tại một thời điểm
                #                     all_results_for_sheet.append(result)
                #                 count += 1
                #                 self.update_done_sum(f'{count}')
                #         except Exception as e:
                #             print(f"A thread failed with an exception: {e}")

                # Using single tasks
                for data in job_page_list:
                    try:
                        result = get_job_info_with_selenium(chrome, data)
                        if result:
                            all_results_for_sheet.append(result)
                            count += 1
                            self.update_done_sum(f'{count}')
                    except Exception as e:
                        print(f"Scraping failed for {data.get('url')}: {e}")

                chrome.driver.quit() # Đóng driver sau khi hoàn thành

                if unAuth:
                    df = pd.DataFrame(all_results_for_sheet).fillna('')
                    if not df.empty:
                        df.insert(0, '登録HW', hw)
                        df.to_csv(csv_file_path, encoding='utf-16', index=False)
                    push_Noti('スプレッドシート転記失敗\n代わりにCSVに出力します')
                else:
                    if all_results_for_sheet:
                        df_final = pd.DataFrame(all_results_for_sheet).fillna('')
                        df_final.insert(0, '登録HW', hw)

                        worksheet_values = worksheet.get_all_values()
                        all_data_len = len(worksheet_values)

                        # Sử dụng batch update để ghi toàn bộ dữ liệu lên sheet một lần
                        if all_data_len < 1 or (all_data_len == 1 and len(worksheet_values[0]) == 0):
                            gs_util.df_2_spread(df_final, worksheet, 1)
                            gs_util.change_cell_size(worksheet, start_index=1, end_index=len(all_results_for_sheet) + 1)
                        else:
                            gs_util.update_sheet(worksheet, df_final.values.tolist(), start_cell=f'A{all_data_len+1}', batch_size=len(df_final))

                        self.add_debug_message(f"Updated sheet with {len(all_results_for_sheet)} new data rows for {hw}")

                # 記録したユーザを除外
                load_job_dict = {user_id: val for user_id, val in load_job_dict.items() if user_id != key}
                if load_job_dict:
                    # まだ転記していないユーザがいればJSONを更新して終わる
                    # JSONファイルに出力
                    with open(job_info_json_path, 'w', encoding='utf-8') as f:
                        json.dump(load_job_dict, f)
                else:
                    # 転機していないユーザがいなければJSONファイルを削除
                    remove(job_info_json_path)
                    return
            except Exception as e:
                print(f"An exception occurred for user {key}: {e}")
                self.retry()
                break


    def add_debug_message(self, message):
        # wx.CallAfter(self.debug_text.AppendText, f"{message}\n")
        # wx.CallAfter(self.selected_user.SetLabel, message)
        wx.CallAfter(self.status_job.SetLabel, message)

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == "no-gui":
        print('Sub process')
    else:
        app = wx.App()
        frame = MyFrame(None, 'Cybozu')
        frame.Show()
        app.MainLoop()
