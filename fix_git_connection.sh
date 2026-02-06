#!/bin/bash
# Fix Git connection to Antenna_Aligner repository

echo "================================================"
echo "Git Connection Fix Script"
echo "================================================"
echo ""

cd /home/sd2-group2/Documents/SD2_Codespace/Antenna_Aligner

echo "Step 1: Setting up git to use GitHub CLI credentials..."
gh auth setup-git
echo ""

echo "Step 2: Checking current branch..."
BRANCH=$(git branch --show-current)
echo "Current branch: $BRANCH"
echo ""

echo "Step 3: Checking remote configuration..."
git remote -v
echo ""

echo "Step 4: Testing connection with git pull..."
git pull origin $BRANCH
echo ""

if [ $? -eq 0 ]; then
    echo "✓ SUCCESS: Git is now connected properly!"
else
    echo "⚠ Pull failed. Let's try alternative authentication..."
    echo ""
    echo "Option 1: Switch to SSH (requires SSH key setup)"
    echo "  git remote set-url origin git@github.com:lesmalan/Antenna_Aligner.git"
    echo ""
    echo "Option 2: Use GitHub CLI for git operations"
    echo "  gh repo sync"
    echo ""
    echo "Option 3: Re-authenticate with GitHub"
    echo "  gh auth login --web"
fi

echo ""
echo "Current git status:"
git status --short
