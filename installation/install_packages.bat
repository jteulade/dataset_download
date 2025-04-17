:: filepath: install_packages.bat
@echo off

:: Step 1: Download the Conda installer
echo Downloading Conda installer...
curl -o %USERPROFILE%\miniconda_installer.exe https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe

:: Step 2: Run the installer silently with default values
echo Running the Conda installer...
%USERPROFILE%\miniconda_installer.exe /InstallationType=JustMe /AddToPath=1 /RegisterPython=0 /S /D=%USERPROFILE%\Miniconda3

:: Step 3: Activate Conda
echo Activating Conda...
call %USERPROFILE%\Miniconda3\Scripts\activate.bat

:: Step 4: Install the required Python packages
echo Installing required Python packages...
pip install -r requirements.txt

echo Installation complete!
pause