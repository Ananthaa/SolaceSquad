# Multi-Device Sync Scripts (Windows <-> Mac)

These scripts keep your SolaceSquad project and Antigravity workspace 100% synchronized when switching between your **Windows Laptop** and your **MacBook**.

---

## 1. First-Time Setup on MacBook

1. Copy `setup_mac.command` to your MacBook (via AirDrop, email, or USB).
2. On your MacBook:
   - Double-click `setup_mac.command` in Finder.
   - If macOS displays a permission warning, open Terminal and run:
     ```bash
     chmod +x setup_mac.command && ./setup_mac.command
     ```
3. What the script does automatically:
   - Installs Xcode CLI tools, Homebrew, Git, and Python 3.11.
   - Installs and configures Google Cloud SDK (`gcloud auth login sg@solacesquad.com`).
   - Clones the repository to `~/Projects/Soul Squad` on branch `feature/events-and-workshops`.
   - Creates two 1-click helper icons directly on your **Mac Desktop**:
     - `Sync_Pull_Mac.command`
     - `Sync_Push_Mac.command`

4. Launch **Google Antigravity** on your Mac and open folder:
   `/Users/<your-username>/Projects/Soul Squad`

---

## 2. Daily Workflow: Switching Between Laptops

### When Leaving Windows to Go to Mac:
- Double-click `sync_scripts/Sync_Push_Windows.bat` (or run `git push origin feature/events-and-workshops`).
- Open your Mac and double-click `Sync_Pull_Mac.command` on your Desktop.
- You now have all latest code on Mac!

### When Leaving Mac to Go to Windows:
- Double-click `Sync_Push_Mac.command` on your Mac Desktop.
- Open your Windows laptop and double-click `sync_scripts/Sync_Pull_Windows.bat`.
- You now have all latest code on Windows!
