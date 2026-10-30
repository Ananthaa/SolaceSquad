@echo off
title SolaceSquad - Pull from GitHub
cd /d "C:\Anantha\Projects\Soul Squad"

echo ========================================================
echo  Syncing GitHub -> Windows
echo ========================================================
echo.
echo Pulling latest changes from origin/feature/events-and-workshops...
git pull origin feature/events-and-workshops
echo.
echo [DONE] Local files are now up-to-date with Mac!
echo.
pause
