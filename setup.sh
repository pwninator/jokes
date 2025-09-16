#! /bin/bash

#!/bin/bash

git checkout master
git log -1

# Configuration - Define all paths and URLs
export FLUTTER_HOME="/usr/local/flutter"
export ANDROID_HOME="/usr/local/android-sdk"
export FLUTTER_SDK_URL="https://storage.googleapis.com/flutter_infra_release/releases/stable/linux/flutter_linux_3.35.2-stable.tar.xz"
export ANDROID_SDK_URL="https://dl.google.com/android/repository/commandlinetools-linux-11391160_latest.zip"

# Update PATH
export PATH="$PATH:$FLUTTER_HOME/bin"
export PATH="$PATH:$ANDROID_HOME/cmdline-tools/latest/bin"
export PATH="$PATH:$ANDROID_HOME/platform-tools"



echo "Install Basic dependencies"
sudo apt-get update -y && sudo apt-get upgrade -y
sudo apt-get install -y apt-transport-https wget curl git unzip jq xz-utils zip libglu1-mesa openjdk-11-jdk

echo "Install Flutter"
if [ -d "$FLUTTER_HOME" ]; then
  echo "Flutter SDK is already installed."
else
  echo "Installing Flutter SDK..."
  wget -qO flutter.tar.xz "$FLUTTER_SDK_URL"
  sudo mkdir -p "$FLUTTER_HOME"
  sudo tar -xf flutter.tar.xz -C "$FLUTTER_HOME" --strip-components=1
  rm flutter.tar.xz 
  echo "Flutter SDK installed."
fi

echo "Install Android SDK"
if [ -d "$ANDROID_HOME" ]; then
  echo "Android SDK is already installed."
else
  echo "Installing Android SDK..."
  wget -qO android_sdk.zip "$ANDROID_SDK_URL"
  unzip -q android_sdk.zip
  sudo mkdir -p "$ANDROID_HOME/cmdline-tools"
  sudo mv cmdline-tools "$ANDROID_HOME/cmdline-tools/latest"
  rm android_sdk.zip
  echo "Android SDK installed."
fi

echo "Install Android platform tools"
echo "Installing Android platform tools..."
yes | sudo "$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager" --licenses
sudo "$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager" "platform-tools" "platforms;android-33" "build-tools;33.0.2"

echo "Configuring Flutter..."
git config --global --add safe.directory "$FLUTTER_HOME"
sudo chown -R $(whoami) $FLUTTER_HOME
# sudo "$FLUTTER_HOME/bin/flutter" config --enable-linux-desktop
sudo "$FLUTTER_HOME/bin/flutter" doctor

echo "Updating .bashrc for the current user..."
BASHRC_FILE="$HOME/.bashrc"
if ! grep -q 'export PATH="$PATH:/usr/local/flutter/bin"' "$BASHRC_FILE"; then
  echo '' >> "$BASHRC_FILE"
  echo '# Flutter and Android SDK' >> "$BASHRC_FILE"
  echo 'export PATH="$PATH:/usr/local/flutter/bin"' >> "$BASHRC_FILE"
fi
if ! grep -q 'export ANDROID_HOME="/usr/local/android-sdk"' "$BASHRC_FILE"; then
  echo 'export ANDROID_HOME="/usr/local/android-sdk"' >> "$BASHRC_FILE"
  echo 'export PATH="$PATH:$ANDROID_HOME/cmdline-tools/latest/bin"' >> "$BASHRC_FILE"
  echo 'export PATH="$PATH:$ANDROID_HOME/platform-tools"' >> "$BASHRC_FILE"
fi

echo "------------------------------------------------------------------"
echo "IMPORTANT:"
echo "The environment variables have been updated in $BASHRC_FILE. To apply the changes,"
echo "you need to either restart your terminal or run:"
echo "source $BASHRC_FILE"
echo "------------------------------------------------------------------"

echo "Setup complete!"

# Use full path to flutter since PATH changes may not be active yet
"$FLUTTER_HOME/bin/flutter" pub get



