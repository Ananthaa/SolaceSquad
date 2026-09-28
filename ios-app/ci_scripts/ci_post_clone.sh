#!/bin/sh
set -e

echo "=== Xcode Cloud Post-Clone Script ==="
echo "Installing CocoaPods dependencies..."

# Install CocoaPods using Homebrew
if ! command -v pod &> /dev/null; then
    echo "Installing CocoaPods via Homebrew..."
    brew install cocoapods
fi

# Navigate to ios-app and run pod install
cd "$CI_PRIMARY_REPOSITORY_PATH/ios-app"
pod install

echo "CocoaPods installation complete for Xcode Cloud!"
