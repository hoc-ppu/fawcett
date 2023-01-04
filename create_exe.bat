pyinstaller --log-level WARN ^
--onefile --clean ^
--icon .\icons\Icon.ico ^
--windowed ^
--add-data=.\icons\Icon.ico;. ^
FawcettApp.py

::also copy the template file to the dist folder
copy /y .\FawcettApp_template.html .\dist\