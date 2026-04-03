import sqlite3
from nicegui import ui
from datetime import datetime

# ==============================================================================
# 1. DATABASE SETUP
# ==============================================================================
def init_db():
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            is_approved INTEGER,
            status TEXT,
            start_time TEXT,
            end_time TEXT,
            approver TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# ==============================================================================
# 2. DATA & STATE
# ==============================================================================
# Static Information from the screenshot
info_data = [
    ('受注No', '0000006775'), ('スタッフNo.', '00001028'),
    ('スタッフ名', '布施 美空'), ('事業所の名称', 'AdlerOrtho株式会社'),
    ('事業所の所在地', '東京都文京区本郷1-21-8 NSKビル8F'),
    ('就業の場所', '〒112-0004 東京都文京区 後楽1-7-12...'),
    ('業務内容', '請求書発行・送付 SAP入力 資料作成...'),
    ('総稼働時間', '85:31'),
]

# Initial Table Data
initial_rows = [
    {'date': '11/01', 'day': '土', 'type': '稼無', 'approved': True, 'start': '', 'end': '', 'color': '#e3f2fd'},
    {'date': '11/02', 'day': '日', 'type': '稼無', 'approved': True, 'start': '', 'end': '', 'color': '#ffebee'},
    {'date': '11/03', 'day': '月', 'type': '稼無', 'approved': True, 'start': '', 'end': '', 'color': '#ffebee'},
    {'date': '11/04', 'day': '火', 'type': '出勤', 'approved': True, 'start': '10:00', 'end': '18:05', 'color': 'white'},
    {'date': '11/05', 'day': '水', 'type': '出勤', 'approved': False, 'start': '09:00', 'end': '17:00', 'color': 'white'},
]

class AttendanceApp:
    def __init__(self):
        self.rows = initial_rows

    def register_data(self):
        """Logic for the 'Register' button"""
        try:
            conn = sqlite3.connect('attendance.db')
            cursor = conn.cursor()
            
            for row in self.rows:
                cursor.execute('''
                    INSERT INTO attendance_records (date, is_approved, status, start_time, end_time, approver)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (row['date'], 1 if row['approved'] else 0, '確定済', row['start'], row['end'], '山崎'))
            
            conn.commit()
            conn.close()
            ui.notify('登録が完了しました (Registration Successful)', type='positive', icon='cloud_done')
        except Exception as e:
            ui.notify(f'Error: {str(e)}', type='negative')

    def toggle_all(self, val):
        """Logic for 'Batch Check' button"""
        for row in self.rows:
            row['approved'] = val
        ui.notify('All items selected' if val else 'Selection cleared')
        # In a real grid, we would refresh the UI element here

app_logic = AttendanceApp()

# ==============================================================================
# 3. UI LAYOUT
# ==============================================================================

# Custom CSS for the grid borders to match Japanese ERP style
ui.add_head_html('''
    <style>
        .erp-grid div { border: 0.5px solid #ccc; display: flex; align-items: center; justify-content: center; min-height: 40px; }
        .erp-header { font-weight: bold; background-color: #fff9c4; }
    </style>
''')

# --- HEADER ---
with ui.header().classes('items-center bg-blue-700 py-2 px-6 shadow-md'):
    ui.label('勤怠承認画面').classes('text-white text-xl font-bold tracking-widest')

# --- MAIN CONTENT ---
with ui.column().classes('w-full p-8 bg-slate-50 min-h-screen'):
    
    # Navigation Buttons (Top Right)
    with ui.row().classes('w-full justify-end gap-2 mb-4'):
        ui.button('一覧画面へ', color='cyan-8').props('outline size=sm')
        ui.button('前月', color='cyan-8').props('unelevated size=sm')
        ui.button('次月', color='cyan-8').props('unelevated size=sm')
        ui.button('印刷プレビュー', color='cyan-8').props('unelevated size=sm')

    # Employee Information Card
    with ui.card().classes('w-full p-0 mb-6 shadow-sm border-none overflow-hidden'):
        for label, value in info_data:
            with ui.row().classes('w-full border-b last:border-0 no-wrap items-stretch'):
                ui.label(label).classes('bg-slate-100 p-2 w-48 font-bold border-r text-xs text-slate-700')
                ui.label(value).classes('bg-white p-2 flex-grow text-xs text-slate-800')

    # Legal Disclaimer
    ui.label('貴社のご承認をもって、労働者派遣法第42条第3項等による通知とします。').classes('text-xs text-slate-500 italic mb-6')
    
    # Action Row
    with ui.row().classes('items-center justify-between w-full mb-4 bg-white p-4 rounded-lg shadow-sm border'):
        with ui.row().classes('items-center gap-4'):
            ui.label('対象年月 : 2025 年 11 月').classes('font-bold text-lg text-blue-900')
            ui.button('一括チェック', on_click=lambda: app_logic.toggle_all(True), color='cyan-6').props('unelevated')
            
            # --- THE REGISTER BUTTON ---
            ui.button('登 録', on_click=app_logic.register_data, color='blue-8').classes('px-10').props('unelevated')
        
        ui.label('承認チェック後、登録ボタンを押下してください。').classes('text-sm text-amber-700 font-bold')

    # --- ATTENDANCE GRID ---
    with ui.card().classes('w-full p-0 shadow-lg border-none'):
        with ui.grid(columns=13).classes('w-full gap-0 erp-grid'):
            # Header Row
            headers = ['承認', '確定', '日付', '曜日', '在宅', '出勤区分', '打刻開始', '打刻終了', '開始', '終了', '休憩', '深夜休憩', '承認者']
            for h in headers:
                ui.label(h).classes('erp-header text-[10px]')
            
            # Data Rows
            for row in app_logic.rows:
                bg = row['color']
                
                # Checkbox Cell
                with ui.element('div').style(f'background-color: {bg}'):
                    ui.checkbox().bind_value(row, 'approved').props('dense color=blue')
                
                # Status & Date
                ui.label('確定済').style(f'background-color: {bg}').classes('text-blue-600 font-bold text-[10px]')
                ui.label(row['date']).style(f'background-color: {bg}').classes('text-blue-600 font-bold')
                ui.label(row['day']).style(f'background-color: {bg}')
                
                # Remote Checkbox
                with ui.element('div').style(f'background-color: {bg}'):
                    ui.checkbox().props('dense')
                
                # Time Cells
                ui.label(row['type']).style(f'background-color: {bg}')
                ui.label(row['start']).style(f'background-color: {bg}') # 打刻開始
                ui.label(row['end']).style(f'background-color: {bg}')   # 打刻終了
                ui.label(row['start']).style(f'background-color: {bg}') # 開始
                ui.label(row['end']).style(f'background-color: {bg}')   # 終了
                ui.label('01:00' if row['start'] else '').style(f'background-color: {bg}')
                ui.label('00:00' if row['start'] else '').style(f'background-color: {bg}')
                
                # Approver Cell
                ui.label('山崎').style(f'background-color: {bg}').classes('text-red-400 font-bold')

# --- START THE APP ---
# We use reload=False and port 8080 for a stable production-like run
ui.run(title='勤怠承認システム', port=8080, reload=True)