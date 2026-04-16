import os, sys, shutil, subprocess

def main():
    print("Installing pup editor...")
    
    print("Installing dependencies...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "blessed"], check=True)
    except subprocess.CalledProcessError:
        print("Error installing blessed. Try: pip install blessed")
        return
    
    src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "editor.py")
    if not os.path.exists(src):
        print("Error: editor.py not found!")
        return
    
    install_dir = os.path.join(os.environ['LOCALAPPDATA'], 'pup-editor')
    if not os.path.exists(install_dir):
        os.makedirs(install_dir)
    
    dst = os.path.join(install_dir, 'editor.py')
    shutil.copy2(src, dst)
    
    bat_dir = os.path.join(os.environ['LOCALAPPDATA'], 'Microsoft', 'WindowsApps')
    bat_path = os.path.join(bat_dir, 'pup.bat')
    
    with open(bat_path, 'w', encoding='utf-8') as f:
        f.write(f'@echo off\npython "{dst}" %*\n')
    
    print(f"Installed to: {install_dir}")
    print(f"Command: pup")
    print("\nRestart terminal and use 'pup' to open editor.")

if __name__ == "__main__": main()