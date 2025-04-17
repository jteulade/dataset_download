If you want to install by yourself : 

 - You need to install Conda first:
     - Download the installer from this website: [https://www.anaconda.com/download/](https://www.anaconda.com/download/).
     - Execute the following command to give execution rights to the script:
       ```bash
       chmod +x /path/to/the/script.sh
       ```
     - Run the installer silently with default values:
       ```bash
       bash SCRIPT_NAME.sh -b
       ```
     - Activate Conda:
       ```bash
       source $HOME/anaconda3/bin/activate
       ```
   - Install the required Python packages:
     ```bash
     pip install -r requirements.txt
     ```