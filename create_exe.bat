pyinstaller --log-level WARN ^
--onefile --clean ^
--icon .\icons\Icon.ico ^
--windowed ^
--add-data=.\icons\Icon.ico;. ^
FawcettApp.py
