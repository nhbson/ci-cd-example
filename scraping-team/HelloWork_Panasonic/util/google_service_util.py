import csv
import gspread
import io
import re
from google.oauth2 import service_account
from oauth2client.service_account import ServiceAccountCredentials
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
from typing import TypeVar, Union

DF  = TypeVar('DF',  bound='pandas.core.frame.DataFrame')
GDF = TypeVar('GDF', bound='pydrive.files.GoogleDriveFile')
GSC = TypeVar('GSC', bound=gspread.client.Client)
SAC = TypeVar('SAC', bound=service_account.Credentials)
WB  = TypeVar('WS',  bound=gspread.spreadsheet.Spreadsheet)
WS  = TypeVar('WS',  bound=gspread.worksheet.Worksheet)

class GoogleServiceUtil:
    # コンストラクタ ======================================================================================
    def __init__(self, service_account_data:Union[str, dict]):
        self._credentials = self.create_credentials(service_account_data)
        self._drive = self.create_google_drive()
        self._gc = self.create_gspread_client()
    # ====================================================================================================
    
    # ゲッター ============================================================================================
    # 認証オブジェクト取得
    @property
    def credentials(self) -> SAC:
        return self._credentials
    
    # スプレッドシートのクライアント取得
    @property
    def gspread_client(self) -> GSC:
        return self._gc
    
    # グーグルドライブのコントローラ取得
    @property
    def drive(self) -> GoogleDrive:
        return self._drive
    # ====================================================================================================
    
    # 操作 ================================================================================================
    # 認証情報オブジェクト生成
    def create_credentials(self, service_account_data:Union[str, dict]) -> SAC:
        try:
            scope = [
                'https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive',
            ]
            # サービスアカウント認証情報
            if type(service_account_data)==str:
                self._credentials = ServiceAccountCredentials.from_json_keyfile_name(service_account_data, scope)
            else:
                self._credentials = service_account.Credentials.from_service_account_info(service_account_data, scopes=scope) 
        except Exception as e:
            print(f'認証情報オブジェクトの生成: 失敗\n{e}')
            self._credentials = None
        finally:
            return self._credentials

    # グーグルドライブのコントローラ生成
    def create_google_drive(self) -> GoogleDrive:
        try:
            # pydrive用の認証
            gauth = GoogleAuth()
            gauth.credentials = self._credentials
            self._drive = GoogleDrive(gauth)
        except Exception as e:
            print(f'グーグルドライブコントローラ生成: 失敗\n{e}')
            self._drive = None
        finally:
            return self._drive

    # スプレッドシートのクライアント生成
    def create_gspread_client(self) -> GSC:
        try:
            self._gc = gspread.authorize(self._credentials)
        except Exception as e:
            print(f'gspreadコントローラ生成: 失敗\n{e}')
            self._gc = None
        finally:
            return self._gc
    
    # ドライブ内のファイル一覧取得
    def get_file_list(self, dir_id:str, mime_type:str=None):
        query = f"'{dir_id}' in parents and trashed=false"
        if mime_type:
            query += f" and mimeType='{mime_type}'"
        try:
            file_list = self.drive.ListFile({'q': query}).GetList()
            return file_list
        except Exception as e:
            print(f'ファイル一覧取得: 失敗\n{e}')
            return []
    
    # ファイルアップロード
    def upload_file(self, tgt_file:Union[str, io.BytesIO], dir_id:str, permission:dict=None):
        try:
            file_name = tgt_file.split('/')[-1] if type(tgt_file)==str else tgt_file.name
            upload_item = self.drive.CreateFile({'title': file_name, 'parents': [{'id': dir_id}]})
            # ローカルファイルの内容を設定
            if type(tgt_file)==str:
                upload_item.SetContentFile(tgt_file)
            else:
                upload_item.content = tgt_file
            # ファイルをアップロード
            upload_item.Upload()
            # 権限の指定があればここで適用
            if permission:
                upload_item.InsertPermission(permission)
            return upload_item
        except Exception as e:
            print(f'ファイルアップロード: 失敗\n{e}')
            return e

    # グーグルドライブにスプレッドシート作成
    def add_spread_sheet(self, dir_id:str, title:str) -> GDF:
        try:
            # スプレッドシート作成
            f = self._drive.CreateFile({
                'title'   : title,
                'mimeType': 'application/vnd.google-apps.spreadsheet',
                'parents' : [{'id': dir_id}],
            })
            f.Upload()
            return f
        except Exception as e:
            print(f'スプレッドシートの作成: 失敗\n{e}')
            return e

    # グーグルドライブにディレクトリ作成
    def add_folder(self, dir_id:str, title:str) -> GDF:
        try:
            f = self._drive.CreateFile({
                'title'   : title,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents' : [{'id': dir_id}],
            })
            f.Upload()
            return f
        except Exception as e:
            print(f'ディレクトリの作成: 失敗\n{e}')
            return e

    # スプレッドシートワークブック取得
    def get_spread_sheet_workbook(self, sheet_id:str) -> WB:
        try:
            return self._gc.open_by_key(sheet_id)
        except Exception as e:
            print(f'スプレッドシートの取得: 失敗\n{e}')
            return e
    # ====================================================================================================

    # クラスメソッド =======================================================================================
    # Googleドライブダウンロードリンク取得
    @classmethod
    def get_download_link(cls, tgt_item:Union[str, GDF]):
        base_url = 'https://drive.google.com/uc?export=download&id={}'
        if type(tgt_item)!=str: tgt_item = tgt_item.get('id')
        return base_url.format(tgt_item)

    # リスト→スプレッドシート変換
    @classmethod
    def list_2_spread(cls, add_body:list, worksheet:WS, batch_size:int=1000, clear_mode:bool=True) -> WS:
        try:
            if clear_mode: worksheet.clear()
            # batch_size行ごとにデータを追加する
            for i in range(0, len(add_body), batch_size):
                range_label = f'A{i + 1}'
                subset = add_body[i: i + batch_size]
                worksheet.append_rows(subset, table_range=range_label)
            return worksheet
        except Exception as e:
            print(f'スプレッドシートの書込: 失敗\n{e}')
            return e

    # CSV→スプレッドシート変換
    @classmethod
    def csv_2_spread(
        cls, csv_path:str, worksheet:WS, 
        batch_size:int=1000, encoding:str='utf_8', clear_mode:bool=True
    ) -> WS:
        add_body = list(csv.reader(open(csv_path, encoding=encoding)))
        return cls.list_2_spread(add_body, worksheet, batch_size, clear_mode)
    
    # DF→スプレッドシート変換
    @classmethod
    def df_2_spread(
        cls, df:DF, worksheet:WS, 
        batch_size:int=1000, header:bool=True, clear_mode:bool=True
    ) -> WS:
        add_body = df.values.tolist()
        if header: add_body.insert(0, df.columns.tolist())
        return cls.list_2_spread(add_body, worksheet, batch_size, clear_mode)
       
    # ワークシートに書き込み
    @classmethod
    def update_sheet(
        cls, worksheet:WS, data, start_cell:str='A1', 
        batch_size:int=1000, value_input_option:str='USER_ENTERED'
    ) -> WS:
        split_start_cell = re.sub("^([^0-9]+)([1-9]+)", "\\1,\\2", start_cell).split(",")
        if len(split_start_cell) != 2: return None
        try:
            # 開始位置を取得
            start_col, start_row = split_start_cell
            # 終了カラムを取得
            start_col_num = cls.col_letter_to_num(start_col)
            end_col_num = start_col_num + len(data[0]) -1
            end_col = cls.num_to_col_letter(end_col_num)
            data_list = [data[i: i+batch_size] for i in range(0, len(data), batch_size)]
            start_row = int(start_row)
            for split_data in data_list:
                end_row = start_row + batch_size - 1
                cell_range = f'{start_col}{start_row}:{end_col}{end_row}'
                # データをセルに書き込む（value_input_optionがRAWでデータのまま入力）
                worksheet.update(cell_range, split_data, value_input_option=value_input_option)
                start_row = end_row + 1
            return worksheet
        except Exception as e:
            return e

    # 列番号を文字列に変換
    @classmethod
    def num_to_col_letter(cls, num:int) -> str:
        result = ""
        while num > 0:
            num, remainder = divmod(num - 1, 26)
            result = chr(65 + remainder) + result
        return result
    
    # 列名を数値に変換
    @classmethod
    def col_letter_to_num(cls, col_letter:str) -> int:
        result = 0
        for i, char in enumerate(reversed(col_letter.upper())):
            result += (ord(char) - 64) * (26 ** i)
        return result
        
    # スプシのセルサイズ変更
    @classmethod
    def change_cell_size(
        cls, worksheet:WS, mode:str='ROWS', 
        start_index:int=0, end_index:int=100, pixcel_size:int=20
    ) -> WS:
        mode = mode.upper()
        if mode != 'COLUMNS': mode='ROWS'
        try:
            requests = [{
                'updateDimensionProperties': {
                    'range': {
                        'sheetId'   : worksheet.id,
                        'dimension' : mode,
                        'startIndex': start_index, # 行の開始位置
                        'endIndex'  : end_index, # 行の終了位置
                    },
                    'properties': {
                        'pixelSize': pixcel_size, # セルの高さ（ピクセル単位）
                    },
                    'fields': 'pixelSize',
                }
            }]
            response = worksheet.spreadsheet.batch_update({'requests': requests})
            return worksheet
        except Exception as e:
            print(f'セルの縦幅変更: 失敗\n{e}')
            return e
    
    # セルの色を変更
    @classmethod
    def change_cell_color(
        cls, worksheet:WS, color:list=[255,255,255], 
        start_row:int=0, end_row:int=1, start_col:int=0, end_col:int=1
    ) -> WS:
        try:
            # 色取得
            red, green, blue = [rgb / 255 for rgb in color]
            # セルのバックグラウンドカラーを変更するリクエストを作成
            requests = [{
                'repeatCell': {
                    'range': {
                        'sheetId'         : worksheet.id,
                        'startRowIndex'   : start_row,
                        'endRowIndex'     : end_row,
                        'startColumnIndex': start_col,
                        'endColumnIndex'  : end_col,
                    },
                    'cell': {
                        'userEnteredFormat': {
                            'backgroundColor': {
                                'red'  : red,
                                'green': green,
                                'blue' : blue,
                            }
                        }
                    },
                    'fields': 'userEnteredFormat.backgroundColor',
                }
            }]
            # リクエストを実行
            worksheet.spreadsheet.batch_update({'requests': requests})
            return worksheet
        except Exception as e:
            print(f'セルの色変更: 失敗\n{e}')
            return e
    # ====================================================================================================