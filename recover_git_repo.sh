#!/bin/bash
# Git Repository Recovery Script
# Fixes corrupted git objects

echo "================================================"
echo "Git Repository Recovery"
echo "================================================"
echo ""

cd /home/sd2-group2/Documents/SD2_Codespace/Antenna_Aligner

echo "Step 1: Checking for local uncommitted changes..."
git status --short > /tmp/git_status.txt
if [ -s /tmp/git_status.txt ]; then
    echo "⚠ You have uncommitted changes. Backing up..."
    git diff > /tmp/antenna_aligner_changes_backup.patch
    git diff --cached > /tmp/antenna_aligner_staged_backup.patch
    echo "✓ Backup saved to /tmp/antenna_aligner_*_backup.patch"
fi
echo ""

echo "Step 2: Attempting to recover corrupted objects..."
# Remove empty/corrupted object files
find .git/objects/ -type f -empty -delete
echo "✓ Removed empty object files"
echo ""

echo "Step 3: Checking repository integrity..."
git fsck --full 2>&1 | tee /tmp/git_fsck.log
echo ""

echo "Step 4: Attempting to fetch from remote..."
git fetch origin --prune 2>&1
echo ""

echo "Step 5: Resetting to remote branch..."
BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "main")
echo "Current branch: $BRANCH"

if git show-ref --verify --quiet refs/remotes/origin/$BRANCH; then
    echo "Resetting to origin/$BRANCH..."
    git reset --hard origin/$BRANCH
    echo "✓ Repository recovered!"
else
    echo "⚠ Could not find remote branch origin/$BRANCH"
    echo "Available remote branches:"
    git branch -r
fi
echo ""

echo "Step 6: Reapplying local changes (if any)..."
if [ -f /tmp/antenna_aligner_changes_backup.patch ] && [ -s /tmp/antenna_aligner_changes_backup.patch ]; then
    echo "Found backup of uncommitted changes. Apply? (y/n)"
    read -p "> " apply_patch
    if [ "$apply_patch" = "y" ]; then
        git apply /tmp/antenna_aligner_changes_backup.patch 2>&1 && echo "✓ Uncommitted changes restored"
    fi
fi

if [ -f /tmp/antenna_aligner_staged_backup.patch ] && [ -s /tmp/antenna_aligner_staged_backup.patch ]; then
    git apply --cached /tmp/antenna_aligner_staged_backup.patch 2>&1 && echo "✓ Staged changes restored"
fi
echo ""

echo "================================================"
echo "Recovery Complete!"
echo "================================================"
git status
echo ""
echo "If recovery failed, you may need to re-clone:"
echo "  cd /home/sd2-group2/Documents/SD2_Codespace/"
echo "  mv Antenna_Aligner Antenna_Aligner.backup"
echo "  gh repo clone lesmalan/Antenna_Aligner"
