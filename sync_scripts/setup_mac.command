#!/bin/bash
# ==============================================================================
# SolaceSquad & Antigravity Setup Script for macOS (MacBook)
# ==============================================================================
# How to run:
# 1. Double-click this file in Finder, OR
# 2. In Terminal run: chmod +x setup_mac.command && ./setup_mac.command
# ==============================================================================

set -e

echo ""
echo "=========================================================="
echo "  🚀 SolaceSquad & Antigravity Setup for MacBook"
echo "=========================================================="
echo ""

# 1. Check / Install Xcode Command Line Tools
echo "Step 1/5: Checking Apple Developer Tools..."
if ! xcode-select -p &>/dev/null; then
    echo "Installing Xcode Command Line Tools. Please click 'Install' if prompted..."
    xcode-select --install
    echo "Press Enter once Xcode tools installation completes..."
    read -r
else
    echo "✓ Apple Developer Tools already installed."
fi

# 2. Check / Install Homebrew
echo ""
echo "Step 2/5: Checking Homebrew package manager..."
if ! command -v brew &>/dev/null; then
    echo "Homebrew not found. Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    
    # Configure brew for Apple Silicon or Intel
    if [ -f "/opt/homebrew/bin/brew" ]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
        echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
    elif [ -f "/usr/local/bin/brew" ]; then
        eval "$(/usr/local/bin/brew shellenv)"
        echo 'eval "$(/usr/local/bin/brew shellenv)"' >> ~/.zprofile
    fi
else
    echo "✓ Homebrew is installed."
fi

# 3. Install Git, Python 3.11, Google Cloud SDK
echo ""
echo "Step 3/5: Installing Git, Python 3.11, and Google Cloud SDK..."
brew install git python@3.11 || true
if ! command -v gcloud &>/dev/null; then
    echo "Installing Google Cloud SDK..."
    brew install --cask google-cloud-sdk || true
    if [ -f "$(brew --prefix)/Caskroom/google-cloud-sdk/latest/google-cloud-sdk/path.zsh.inc" ]; then
        source "$(brew --prefix)/Caskroom/google-cloud-sdk/latest/google-cloud-sdk/path.zsh.inc"
    fi
else
    echo "✓ Google Cloud SDK is already installed."
fi

# 4. Clone or Update SolaceSquad Repository
echo ""
echo "Step 4/5: Setting up workspace in ~/Projects/Soul Squad..."
mkdir -p ~/Projects
cd ~/Projects

if [ -d "Soul Squad/.git" ]; then
    echo "Repository already exists. Updating..."
    cd "Soul Squad"
    git fetch origin
    git checkout feature/events-and-workshops || git checkout -b feature/events-and-workshops origin/feature/events-and-workshops
    git pull origin feature/events-and-workshops
else
    echo "Cloning SolaceSquad repository..."
    git clone https://github.com/Ananthaa/SolaceSquad.git "Soul Squad"
    cd "Soul Squad"
    git checkout feature/events-and-workshops || true
fi

# 5. Configure Google Cloud Authentication
echo ""
echo "Step 5/5: Configuring Google Cloud authentication..."
echo "Authenticating as sg@solacesquad.com..."
gcloud auth login sg@solacesquad.com || true
gcloud config set project abiding-idea-485817-k2
gcloud config set run/region us-central1

# 6. Create Daily Sync Utilities on Desktop
echo ""
echo "Creating one-click Sync helpers on your Desktop..."
cat << 'EOF' > ~/Desktop/Sync_Pull_Mac.command
#!/bin/bash
cd "$HOME/Projects/Soul Squad"
echo "Pulling latest changes from GitHub..."
git pull origin feature/events-and-workshops
echo ""
echo "✓ Workspace is up-to-date with Windows!"
read -n 1 -s -r -p "Press any key to close..."
EOF
chmod +x ~/Desktop/Sync_Pull_Mac.command

cat << 'EOF' > ~/Desktop/Sync_Push_Mac.command
#!/bin/bash
cd "$HOME/Projects/Soul Squad"
echo "Staging all changes..."
git status
git add .
read -p "Enter commit message (or press enter for default): " MSG
if [ -z "$MSG" ]; then
    MSG="wip: sync from mac $(date '+%Y-%m-%d %H:%M')"
fi
git commit -m "$MSG" || echo "Nothing new to commit."
echo "Pushing to GitHub..."
git push origin feature/events-and-workshops
echo ""
echo "✓ Pushed successfully! Ready to pull on Windows."
read -n 1 -s -r -p "Press any key to close..."
EOF
chmod +x ~/Desktop/Sync_Push_Mac.command

echo ""
echo "=========================================================="
echo "  🎉 Setup Complete!"
echo "=========================================================="
echo ""
echo "Next steps:"
echo "1. Open Google Antigravity on this Mac."
echo "2. Open the project folder: $HOME/Projects/Soul Squad"
echo "3. Use the two icons on your Desktop anytime:"
echo "   - 'Sync_Pull_Mac': Click before starting work"
echo "   - 'Sync_Push_Mac': Click before leaving your Mac"
echo ""
read -n 1 -s -r -p "Press any key to exit..."
