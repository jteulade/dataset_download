#!/bin/bash

# filepath: /home/kigmou/Documents/dataset_download/install_packages.sh

# Step 1: Download the Conda installer
echo "Downloading Conda installer..."
wget -O ~/miniconda_installer.sh https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh

# Step 2: Make the installer executable
echo "Making the installer executable..."
chmod +x ~/miniconda_installer.sh

# Step 3: Run the installer silently with default values
echo "Running the Conda installer..."
bash ~/miniconda_installer.sh -b

# Step 4: Activate Conda
echo "Activating Conda..."
source $HOME/miniconda3/bin/activate

# Step 5: Install the required Python packages
echo "Installing required Python packages..."
pip install -r requirements.txt

echo "Installation complete!"

