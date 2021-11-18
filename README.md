# Fawcett App
Create a quick proof of the Questions Tabled document.
For ordinary usage instructions see SharePoint.

## Development instructions
1. Install python if you haven't already.
2. Install pipenv.
3. Install git if you haven't already.
4. Clone this repository.
5. In command prompt or power shell `cd` to the repository.
6. Do `pipenv install` to install dependencies.
7. `pipenv shell` to activate the virtual environment.
8. `python FawcettApp.py` to test.

## Creating the .exe
1. You may need to run `pipenv install --dev` to get pyInstaller dependency.
2. run`create_exe.bat`. This should expand to a longer command.
3. A new FawcettApp.exe will be created in the dist folder.
4. You may need to copy `FawcettApp_template.html` into the dist folder.
5. Run FawcettApp.exe by double clicking.
