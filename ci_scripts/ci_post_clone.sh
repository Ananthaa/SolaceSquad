#!/bin/sh
set -e

echo \ === Xcode Cloud: Setting up CocoaPods dependencies ===\

if ! command -v pod &> /dev/null; then
    echo \Installing CocoaPods via Homebrew...\
    brew install cocoapods
fi

if [ -n \\\ ] && [ -d \\/ios-app\ ]; then
    cd \\/ios-app\
elif [ -n \\\ ] && [ -d \\/ios-app\ ]; then
    cd \\/ios-app\
elif [ -d \ios-app\ ]; then
    cd ios-app
fi

echo \Running pod install in \C:\Anantha\Projects\Soul Squad...\
pod install

echo \=== CocoaPods setup completed successfully ===\
