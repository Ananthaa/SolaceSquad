@echo off
title SolaceSquad - Push to GitHub
cd /d "C:\Anantha\Projects\Soul Squad"

echo ========================================================
echo  Syncing Windows -> GitHub
echo ========================================================
echo.
git status
echo.
git add .
set /p MSG="Enter commit message (or press enter for default): "
if "%MSG%"=="" set MSG=wip: update from windows %date% %time%
git commit -m "%MSG%"
echo.
echo Pushing to origin/feature/events-and-workshops...
git push origin feature/events-and-workshops
echo.
echo [DONE] Changes pushed successfully! Ready to pull on Mac.
echo.
pause
