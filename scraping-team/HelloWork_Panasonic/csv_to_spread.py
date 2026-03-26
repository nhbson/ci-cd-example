import json
import os
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
from configparser import ConfigParser
from create_jobs_json import login
from get_job_info import get_job_info
from util.chrome_util import Chrome_Util
from util.google_service_util import GoogleServiceUtil

def main():
    this_file_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(this_file_dir, 'config.ini')
    # コンフィグファイル読み込み
    config = ConfigParser()
    config.read(config_path, encoding='utf-8')
    # 最大並列数
    max_workers = int(config.get('LOCAL', 'max_workers'))
    # 記録用JSON
    job_info_json_path = config.get('LOCAL', 'job_info_json_path')
    # スプレッドシートID
    spread_sheet_id      = config.get('GOOGLE', 'spread_sheet_id')
    service_account_json = config.get('GOOGLE', 'service_account_json')
    worksheet_name       = config.get('GOOGLE', 'worksheet_name')
    print('コンフィグ読込完了')
    if os.path.exists(job_info_json_path):
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
    tgt_file = [file_name for file_name in  os.listdir('./') if file_name.endswith('_output.csv')]
    if not tgt_file:
        print('対象のCSVがありません')
        return
    tgt_file = tgt_file[0]
    key = tgt_file.rstrip('_output.csv')

    # DFに変換
    df = pd.read_csv(tgt_file).fillna('')

    try:
        gs_util = GoogleServiceUtil(service_account_json)
        # スプレッドシート取得
        workbook = gs_util.get_spread_sheet_workbook(spread_sheet_id)
        # ワークシート取得（なければ作る）
        try:
            worksheet = workbook.worksheet(worksheet_name)    
        except:
            print('求人一覧のシートを追加します')
            workbook.add_worksheet(title=worksheet_name, rows='5', cols='5')
            worksheet = workbook.worksheet(worksheet_name)
        # 全てのデータ取得
        all_data_len = len(worksheet.get_all_values())
        # データが有れば追記、なければ新規作成
        if all_data_len:
            if worksheet.row_count < all_data_len+len(df):
                add_len = (all_data_len+len(df)) - worksheet.row_count
                worksheet.append_rows([['']]*add_len)
            gs_util.update_sheet(worksheet, df.values.tolist(), start_cell=f'A{all_data_len+1}', batch_size=5000)
        else:
            # DFをスプレッドシートに
            result = gs_util.df_2_spread(df, worksheet)
            if isinstance(result, Exception): raise result
            # セル幅調整
            gs_util.change_cell_size(worksheet, start_index=1, end_index=len(df)+1)
        print('スプレッドシート転記完了')

    except Exception as e:
        print(f'スプレッドシート転記失敗\n{e}')
        raise Exception(f'スプレッドシート転記失敗\n{e}')

    # 記録したユーザを除外
    load_job_dict = {user_id: val for user_id, val in load_job_dict.items() if user_id != key}
    if load_job_dict:
        # まだ転記していないユーザがいればJSONを更新して終わる
        # JSONファイルに出力
        with open(job_info_json_path, 'w', encoding='utf-8') as f:
            json.dump(load_job_dict, f)
    else:
        # 転機していないユーザがいなければJSONファイルを削除
        os.remove(job_info_json_path)
    os.remove(tgt_file)

if __name__ == '__main__':
    main()