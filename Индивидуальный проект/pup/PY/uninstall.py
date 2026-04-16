import os, sys, shutil

def main():
    print("Uninstalling pup editor...")
    
    install_dir = os.path.join(os.environ['LOCALAPPDATA'], 'pup-editor')
    bat_path = os.path.join(os.environ['LOCALAPPDATA'], 'Microsoft', 'WindowsApps', 'pup.bat')
    
    if os.path.exists(install_dir):
        shutil.rmtree(install_dir)
        print(f"Removed: {install_dir}")
    else:
        print("Install directory not found.")
    
    if os.path.exists(bat_path):
        os.remove(bat_path)
        print(f"Removed: {bat_path}")
    else:
        print("Command file not found.")
    
    print("\nUninstall complete. Restart terminal.")

if __name__ == "__main__": main()