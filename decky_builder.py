import os
import subprocess
import shutil
import argparse
from pathlib import Path
import sys
import time

class DeckyBuilder:
    def __init__(self, release: str):
        self.release = release
        self.root_dir = Path(__file__).parent
        self.app_dir = self.root_dir / "app"
        self.src_dir = self.root_dir / "src"
        self.dist_dir = self.root_dir / "dist"
        self.homebrew_dir = self.dist_dir / "homebrew"
        
        # Setup user homebrew directory
        self.user_home = Path.home()
        self.user_homebrew_dir = self.user_home / "homebrew"
        self.homebrew_folders = [
            "data",
            "logs",
            "plugins",
            "services",
            "settings",
            "themes"
        ]

    def safe_remove_directory(self, path):
        """Safely remove a directory with retries for Windows"""
        max_retries = 3
        retry_delay = 1  # seconds

        for attempt in range(max_retries):
            try:
                if path.exists():
                    # On Windows, sometimes we need to remove .git directory separately
                    git_dir = path / '.git'
                    if git_dir.exists():
                        for item in git_dir.glob('**/*'):
                            if item.is_file():
                                try:
                                    item.chmod(0o777)  # Give full permissions
                                    item.unlink()
                                except:
                                    pass
                    
                    shutil.rmtree(path, ignore_errors=True)
                return
            except Exception as e:
                print(f"Attempt {attempt + 1} failed to remove {path}: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                else:
                    print(f"Warning: Could not fully remove {path}. Continuing anyway...")

    def setup_directories(self):
        """Setup directory structure"""
        print("Setting up directories...")
        # Clean up any existing directories
        if self.app_dir.exists():
            self.safe_remove_directory(self.app_dir)
        if self.src_dir.exists():
            self.safe_remove_directory(self.src_dir)
        if self.homebrew_dir.exists():
            self.safe_remove_directory(self.homebrew_dir)

        # Create fresh directories
        self.src_dir.mkdir(parents=True, exist_ok=True)
        self.homebrew_dir.mkdir(parents=True, exist_ok=True)

    def setup_homebrew(self):
        """Setup homebrew directory structure"""
        print("Setting up homebrew directory structure...")
        # Create dist directory
        (self.homebrew_dir / "dist").mkdir(parents=True, exist_ok=True)

        # Setup homebrew directory structure for both temp and user directories
        print("Setting up homebrew directory structure...")
        for directory in [self.homebrew_dir, self.user_homebrew_dir]:
            if not directory.exists():
                directory.mkdir(parents=True)
            
            for folder in self.homebrew_folders:
                folder_path = directory / folder
                if not folder_path.exists():
                    folder_path.mkdir(parents=True)

    def clone_repository(self):
        """Clone Decky Loader repository"""
        print("Cloning repository with release {}...".format(self.release))
        subprocess.run([
            "git", "clone",
            "--branch", self.release,
            "https://github.com/SteamDeckHomebrew/decky-loader.git",
            str(self.app_dir)
        ], check=True)

    def build_frontend(self):
        """Build frontend files"""
        print("Building frontend...")
        try:
            frontend_dir = self.app_dir / "frontend"
            if frontend_dir.exists():
                # Install dependencies and build using shell=True
                print("Installing frontend dependencies...")
                subprocess.run("pnpm i", shell=True, cwd=frontend_dir, check=True)
                
                print("Building frontend...")
                subprocess.run("pnpm run build", shell=True, cwd=frontend_dir, check=True)
                
                # Create .loader.version
                with open(frontend_dir / ".loader.version", "w") as f:
                    f.write(self.release)
                    
                print("Frontend build completed successfully")
            else:
                raise Exception("Frontend directory not found")
        except Exception as e:
            print(f"Error building frontend: {str(e)}")
            raise

    def prepare_backend(self):
        """Prepare backend files for PyInstaller"""
        print("Preparing backend files...")
        try:
            # Create dist directory first
            (self.src_dir / "dist").mkdir(parents=True, exist_ok=True)
            
            print("Copying files according to Dockerfile structure...")
            
            # Copy backend directory contents
            backend_dir = self.app_dir / "backend"
            if backend_dir.exists():
                print("Copying backend files...")
                
                # Copy main.py to src directory
                shutil.copy2(backend_dir / "main.py", self.src_dir / "main.py")
                
                # Copy decky_loader package
                decky_loader_src = backend_dir / "decky_loader"
                if decky_loader_src.exists():
                    decky_loader_dest = self.src_dir / "decky_loader"
                    if decky_loader_dest.exists():
                        shutil.rmtree(decky_loader_dest)
                    shutil.copytree(decky_loader_src, decky_loader_dest)
                else:
                    raise Exception("decky_loader directory not found in backend")

                # Copy frontend static files
                frontend_dir = self.app_dir / "frontend" / "dist"
                if frontend_dir.exists():
                    static_dest = self.src_dir / "static"
                    if static_dest.exists():
                        shutil.rmtree(static_dest)
                    shutil.copytree(frontend_dir, static_dest)

                # Copy plugin directory
                plugin_src = self.app_dir / "plugin"
                if plugin_src.exists():
                    plugin_dest = self.src_dir / "plugin"
                    if plugin_dest.exists():
                        shutil.rmtree(plugin_dest)
                    shutil.copytree(plugin_src, plugin_dest)
            else:
                raise Exception("Backend directory not found")
            
            # Create .loader.version file
            print("Creating .loader.version...")
            with open(self.src_dir / "dist" / ".loader.version", "w") as f:
                f.write(self.release)
            
            print("Backend preparation completed successfully!")
            
        except Exception as e:
            print(f"Error during backend preparation: {str(e)}")
            raise

    def install_requirements(self):
        """Install Python requirements"""
        print("Installing Python requirements...")
        try:
            # Try both requirements.txt and pyproject.toml
            requirements_file = self.app_dir / "backend" / "requirements.txt"
            pyproject_file = self.app_dir / "backend" / "pyproject.toml"
            
            if requirements_file.exists():
                subprocess.run([
                    "pip", "install", "-r", str(requirements_file)
                ], check=True)
            elif pyproject_file.exists():
                subprocess.run([
                    "pip", "install", "poetry"
                ], check=True)
                subprocess.run([
                    "poetry", "install"
                ], cwd=self.app_dir / "backend", check=True)
            else:
                print("Warning: No requirements.txt or pyproject.toml found")
        except Exception as e:
            print(f"Error installing requirements: {str(e)}")
            raise

    def build_executables(self):
        """Build executables using PyInstaller"""
        print("Building executables...")
        try:
            # Common PyInstaller arguments
            pyinstaller_args = [
                "--noconfirm",
                "--onefile",
                "--name", "PluginLoader",
                "--add-data", f"{self.src_dir / 'decky_loader/static'};decky_loader/static",
                "--add-data", f"{self.src_dir / 'decky_loader/locales'};decky_loader/locales",
                "--add-data", f"{self.src_dir / 'decky_loader/plugin'};decky_loader/plugin",
                "--hidden-import=logging.handlers",
                "--hidden-import=sqlite3",
                str(self.src_dir / "main.py")
            ]
            
            # Print directory contents for debugging
            print("Current directory contents:")
            for path in self.src_dir.rglob("*"):
                print(f"  {path}")
            
            print("Building console version...")
            subprocess.run(["pyinstaller"] + pyinstaller_args, check=True)
            
            print("Building no-console version...")
            subprocess.run(["pyinstaller", "--noconsole"] + pyinstaller_args, check=True)
            
        except subprocess.CalledProcessError as e:
            print(f"Error building executables: {e}")
            raise

    def copy_to_homebrew(self):
        """Copy all necessary files to the homebrew directory"""
        print("Copying files to homebrew directory...")
        services_dir = self.homebrew_dir / "services"
        user_services_dir = self.user_homebrew_dir / "services"
        
        # Copy executables from dist directory (matching Dockerfile)
        exe_extension = ".exe" if os.name == 'nt' else ""
        try:
            # Create services directory if it doesn't exist
            services_dir.mkdir(parents=True, exist_ok=True)
            user_services_dir.mkdir(parents=True, exist_ok=True)
            
            # Copy the built executables to both locations
            plugin_loader_exe = self.root_dir / "dist" / f"PluginLoader{exe_extension}"
            if plugin_loader_exe.exists():
                shutil.copy2(plugin_loader_exe, services_dir / f"plugin_loader{exe_extension}")
                shutil.copy2(plugin_loader_exe, user_services_dir / f"plugin_loader{exe_extension}")
            else:
                raise FileNotFoundError(f"Built executable not found at: {plugin_loader_exe}")
                
            # Copy version file to both locations
            version_file = self.src_dir / "dist" / ".loader.version"
            if version_file.exists():
                shutil.copy2(version_file, self.homebrew_dir / ".loader.version")
                shutil.copy2(version_file, self.user_homebrew_dir / ".loader.version")
            else:
                raise FileNotFoundError(f"Version file not found at: {version_file}")
            
            print(f"Successfully copied files to: {self.user_homebrew_dir}")
                
        except Exception as e:
            print(f"Error during copy to homebrew: {e}")
            raise

    def install_nodejs(self):
        """Install Node.js v18.18.0 with npm"""
        print("Installing Node.js v18.18.0...")
        try:
            # Create temp directory for downloads
            temp_dir = self.root_dir / "temp"
            temp_dir.mkdir(exist_ok=True)
            
            # Download Node.js installer
            node_installer = temp_dir / "node-v18.18.0-x64.msi"
            if not node_installer.exists():
                print("Downloading Node.js installer...")
                try:
                    import urllib.request
                    urllib.request.urlretrieve(
                        "https://nodejs.org/dist/v18.18.0/node-v18.18.0-x64.msi",
                        node_installer
                    )
                except Exception as e:
                    print(f"Error downloading Node.js installer: {str(e)}")
                    print("Please download Node.js v18.18.0 manually from: https://nodejs.org/dist/v18.18.0/node-v18.18.0-x64.msi")
                    print("Then place it in the following directory:", temp_dir)
                    input("Press Enter to continue once you've downloaded the installer...")

            if not node_installer.exists():
                raise Exception("Node.js installer not found. Please download it manually.")

            # Install Node.js using interactive mode
            print("Installing Node.js (this may take a few minutes)...")
            print("Please follow the installation wizard when it appears...")
            install_process = subprocess.run(
                ["msiexec", "/i", str(node_installer)],
                check=True
            )
            
            print("Waiting for Node.js installation to complete...")
            time.sleep(10)
            
            # Set environment variables for the current process
            nodejs_paths = [
                r"C:\Program Files\nodejs",
                os.path.join(os.environ["APPDATA"], "npm")
            ]
            
            for nodejs_path in nodejs_paths:
                if nodejs_path not in os.environ["PATH"]:
                    os.environ["PATH"] = nodejs_path + os.pathsep + os.environ["PATH"]

            # Verify installation
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    node_version = subprocess.run(["node", "--version"], capture_output=True, text=True, check=True).stdout.strip()
                    npm_version = subprocess.run(["npm", "--version"], capture_output=True, text=True, check=True).stdout.strip()
                    print(f"Successfully installed Node.js {node_version} with npm {npm_version}")
                    break
                except subprocess.CalledProcessError as e:
                    if attempt == max_retries - 1:
                        print("Warning: Node.js installation completed but verification failed")
                        print(f"Error: {str(e)}")
                        print("You may need to restart your system for the changes to take effect")
                        print("After restarting, run this script again")
                        raise Exception("Node.js verification failed")
                    else:
                        print(f"Waiting for Node.js to be available (attempt {attempt + 1}/{max_retries})...")
                        time.sleep(5)
            
            # Clean up
            self.safe_remove_directory(temp_dir)
            
        except Exception as e:
            print(f"Error installing Node.js: {str(e)}")
            raise

    def check_dependencies(self):
        """Check and install required dependencies"""
        print("Checking dependencies...")
        try:
            # Check Node.js and npm first
            node_installed = False
            try:
                # Use shell=True to find node in PATH
                node_version = subprocess.run("node --version", shell=True, check=True, capture_output=True, text=True).stdout.strip()
                npm_version = subprocess.run("npm --version", shell=True, check=True, capture_output=True, text=True).stdout.strip()
                
                # Check if version meets requirements
                if not node_version.startswith("v18."):
                    print(f"Node.js {node_version} found, but v18.18.0 is required")
                    self.install_nodejs()
                else:
                    print(f"Node.js {node_version} with npm {npm_version} is installed")
                    node_installed = True

            except Exception as e:
                print(f"Node.js/npm not found or error: {str(e)}")
                self.install_nodejs()
                node_installed = True  # If we get here, Node.js was installed successfully

            if not node_installed:
                raise Exception("Failed to install Node.js")

            # Install pnpm globally if not present
            try:
                pnpm_version = subprocess.run("pnpm --version", shell=True, check=True, capture_output=True, text=True).stdout.strip()
                print(f"pnpm version {pnpm_version} is installed")
            except:
                print("Installing pnpm globally...")
                subprocess.run("npm i -g pnpm", shell=True, check=True)
                pnpm_version = subprocess.run("pnpm --version", shell=True, check=True, capture_output=True, text=True).stdout.strip()
                print(f"Installed pnpm version {pnpm_version}")

            # Check Python
            try:
                python_version = subprocess.run("python --version", shell=True, check=True, capture_output=True, text=True).stdout.strip()
                print(f"{python_version} is installed")
            except:
                raise Exception("Python is not installed. Please install Python 3.8 or later.")

            # Check git
            try:
                git_version = subprocess.run("git --version", shell=True, check=True, capture_output=True, text=True).stdout.strip()
                print(f"{git_version} is installed")
            except:
                raise Exception("git is not installed. Please install git from https://git-scm.com/downloads")

            print("All dependencies are satisfied")
        except Exception as e:
            print(f"Error checking dependencies: {str(e)}")
            raise

    def setup_steam_config(self):
        """Configure Steam for Decky Loader"""
        print("Configuring Steam...")
        try:
            # Add -dev argument to Steam shortcut
            import winreg
            steam_path = None
            
            # Try to find Steam installation path from registry
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam") as key:
                    steam_path = winreg.QueryValueEx(key, "InstallPath")[0]
            except:
                try:
                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam") as key:
                        steam_path = winreg.QueryValueEx(key, "InstallPath")[0]
                except:
                    print("Steam installation not found in registry")
            
            if steam_path:
                steam_exe = Path(steam_path) / "steam.exe"
                if steam_exe.exists():
                    # Create .cef-enable-remote-debugging file
                    debug_file = Path(steam_path) / ".cef-enable-remote-debugging"
                    debug_file.touch()
                    print("Created .cef-enable-remote-debugging file")
                    
                    # Create/modify Steam shortcut
                    desktop = Path.home() / "Desktop"
                    shortcut_path = desktop / "Steam.lnk"
                    
                    import pythoncom
                    from win32com.client import Dispatch
                    
                    shell = Dispatch("WScript.Shell")
                    shortcut = shell.CreateShortCut(str(shortcut_path))
                    shortcut.Targetpath = str(steam_exe)
                    shortcut.Arguments = "-dev"
                    shortcut.save()
                    print("Created Steam shortcut with -dev argument")

        except Exception as e:
            print(f"Error configuring Steam: {str(e)}")
            raise

    def setup_autostart(self):
        """Setup PluginLoader to run at startup"""
        print("Setting up autostart...")
        try:
            startup_folder = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
            plugin_loader = self.user_homebrew_dir / "services" / "PluginLoader_noconsole.exe"
            
            if plugin_loader.exists():
                import pythoncom
                from win32com.client import Dispatch
                
                shell = Dispatch("WScript.Shell")
                shortcut_path = startup_folder / "PluginLoader.lnk"
                shortcut = shell.CreateShortCut(str(shortcut_path))
                shortcut.Targetpath = str(plugin_loader)
                shortcut.WorkingDirectory = str(plugin_loader.parent)
                shortcut.save()
                print("Created autostart shortcut for PluginLoader")
            else:
                print("Warning: PluginLoader_noconsole.exe not found")

        except Exception as e:
            print(f"Error setting up autostart: {str(e)}")
            raise

    def run(self):
        """Run the build process"""
        try:
            print("Starting Decky Loader build process...")
            self.check_dependencies()
            self.setup_directories()
            self.clone_repository()
            self.setup_homebrew()
            self.build_frontend()
            self.prepare_backend()
            self.install_requirements()
            self.build_executables()
            self.copy_to_homebrew()
            self.setup_steam_config()
            self.setup_autostart()
            print("Build process completed successfully!")
            print("\nNext steps:")
            print("1. Close Steam if it's running")
            print("2. Launch Steam using the new shortcut on your desktop")
            print("3. Enter Big Picture Mode")
            print("4. Hold the STEAM button and press A to access the Decky menu")
        except Exception as e:
            print(f"Error during build process: {str(e)}")
            raise

def main():
    parser = argparse.ArgumentParser(description='Build and Install Decky Loader for Windows')
    parser.add_argument('--release', required=False, default="main", 
                      help='Release version/branch to build (default: main)')
    args = parser.parse_args()

    try:
        builder = DeckyBuilder(args.release)
        builder.run()
        print(f"\nDecky Loader has been installed to: {builder.user_homebrew_dir}")
    except Exception as e:
        print(f"Error during build process: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
