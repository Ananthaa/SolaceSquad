@echo off
echo Connecting to Cloud SQL as postgres user...
echo.
echo You'll be prompted for the postgres password: SolaceSquad2024!
echo.
echo After connecting, run these commands:
echo.
echo GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO "Admin";
echo GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO "Admin";
echo \q
echo.
pause

gcloud sql connect solacesquad-login-data1 --user=postgres --project=abiding-idea-485817-k2
