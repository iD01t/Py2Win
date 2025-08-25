# py2win_premium_app.py
# Py2Win Premium, iD01t Productions
# Single-file Python to Windows Executable Builder - World Class Edition

import sys
import os
import subprocess
import threading
import queue
import json
import ast
import shutil
import zipfile
import urllib.request
import time
import webbrowser
import tempfile
from pathlib import Path
from tkinter import filedialog, messagebox, Listbox
from importlib import metadata
from modulefinder import ModuleFinder

try:
    import customtkinter
    from PIL import Image
except ImportError:
    print("Py2Win Premium: Initial setup requires customtkinter and Pillow.")
    try:
        import pip
        pip.main(['install', 'customtkinter', 'pillow'])
        import customtkinter
        from PIL import Image
    except Exception as e:
        print(f"Failed to auto-install dependencies: {e}")
        sys.exit(1)

# --- CONSTANTS ---
APP_NAME = "Py2Win Premium, iD01t Productions"
APP_VERSION = "3.0.1" # Incremented for bugfix
UPDATE_URL = "https://gist.githubusercontent.com/jules-at-gh/f575f812ce4205428a16be649f448b11/raw/py2win_version.txt"
VENV_DIR = Path("./build_env")
TOOLS_DIR = Path("./.tools")
NSIS_DIR = TOOLS_DIR / "nsis"
NSIS_URL = "https://prdownloads.sourceforge.net/nsis/nsis-3.09.zip?download"
NSIS_EXE_PATH = NSIS_DIR / "nsis-3.09" / "makensis.exe"
REQUIRED_PACKAGES = ["pip", "wheel", "setuptools", "pyinstaller", "pynsist", "pillow", "requests", "cryptography", "pefile", "pipdeptree"]

# --- UTILITY FUNCTIONS ---
def log_message(console_widget, message):
    timestamp = time.strftime("%H:%M:%S")
    full_message = f"[{timestamp}] {message}"
    if console_widget and console_widget.winfo_exists():
        console_widget.insert(customtkinter.END, full_message + "\n")
        console_widget.see(customtkinter.END)
        console_widget.update_idletasks()
    else:
        print(full_message)

class Tooltip:
    def __init__(self, widget, text):
        self.widget = widget; self.text = text; self.tooltip_window = None
        widget.bind("<Enter>", self._show); widget.bind("<Leave>", self._hide)
    def _show(self, _=None):
        if self.tooltip_window or not self.text: return
        x, y, _, _ = self.widget.bbox("insert"); x += self.widget.winfo_rootx() + 25; y += self.widget.winfo_rooty() + 25
        self.tooltip_window = customtkinter.CTkToplevel(self.widget); self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_geometry(f"+{x}+{y}")
        label = customtkinter.CTkLabel(self.tooltip_window, text=self.text, corner_radius=6, fg_color="#2B2B2B", text_color="white", wraplength=280, padx=8, pady=5)
        label.pack()
    def _hide(self, _=None):
        if self.tooltip_window: self.tooltip_window.destroy()
        self.tooltip_window = None

# --- CORE LOGIC CLASSES ---
class EnvManager:
    def __init__(self, app_instance=None):
        self.app = app_instance
        try: self.console = self.app.console if self.app else None
        except AttributeError: self.console = None
        self.python_executable = VENV_DIR / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        self.pip_executable = VENV_DIR / ("Scripts/pip.exe" if sys.platform == "win32" else "bin/pip")
    def log(self, message): log_message(self.console, message)
    def validate_environment(self, on_complete=None):
        self.log("Starting environment validation..."); thread = threading.Thread(target=self._validate_in_background, args=(on_complete,), daemon=True); thread.start(); return thread
    def _validate_in_background(self, on_complete=None):
        try:
            if not self._check_venv(): self._create_venv()
            self._check_and_install_packages(); self.log("✅ Environment validation successful.")
            if self.app: self.app.is_env_valid = True
            if on_complete: (self.app.after(0, on_complete, True) if self.app else on_complete(True))
        except Exception as e:
            self.log(f"❌ Environment validation failed: {e}")
            if self.app: self.app.is_env_valid = False; messagebox.showerror("Environment Error", f"Failed to set up the environment: {e}")
            if on_complete: (self.app.after(0, on_complete, False) if self.app else on_complete(False))
    def _check_venv(self): return VENV_DIR.is_dir() and self.python_executable.is_file()
    def _create_venv(self):
        self.log(f"Creating virtual environment in {VENV_DIR}...")
        try:
            subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR)], check=True, capture_output=True, text=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            self.log("Virtual environment created.")
        except subprocess.CalledProcessError as e: raise RuntimeError(f"Failed to create venv: {e.stderr}")
    def _check_and_install_packages(self):
        self.log("Checking for required packages...")
        try:
            installed_raw = subprocess.run([str(self.pip_executable), "freeze"], check=True, capture_output=True, text=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)).stdout
            installed = {p.split('==')[0].lower() for p in installed_raw.splitlines()}
            missing = [pkg for pkg in REQUIRED_PACKAGES if pkg.lower() not in installed]
            if missing:
                self.log(f"Installing missing/upgrading packages: {', '.join(missing)}")
                cmd = [str(self.pip_executable), "install", "--upgrade"] + missing
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                for line in iter(process.stdout.readline, ''): self.log(line.strip())
                if process.wait() != 0: raise RuntimeError("Failed to install packages.")
                self.log("All packages installed successfully.")
            else: self.log("All required packages are already installed.")
        except (subprocess.CalledProcessError, FileNotFoundError) as e: raise RuntimeError(f"Failed to check/install packages: {e}")

class BuildOrchestrator:
    def __init__(self, app_instance=None):
        self.app = app_instance
        try: self.console = self.app.console if self.app else None
        except AttributeError: self.console = None
        self.env_manager = EnvManager(app_instance)
    def log(self, message): log_message(self.console, message)
    def build(self, project_settings, on_complete=None):
        thread = threading.Thread(target=self._build_in_background, args=(project_settings, on_complete), daemon=True)
        thread.start(); return thread
    def _create_version_file(self, p_settings):
        exe_name = p_settings.get('exe_name', 'MyApp')
        ver_info = {
            "CompanyName": p_settings.get('company_name', 'My Company'), "FileDescription": p_settings.get('file_description', 'Packaged Python Application'),
            "FileVersion": p_settings.get('file_version', '1.0.0.0'), "InternalName": exe_name,
            "LegalCopyright": p_settings.get('legal_copyright', f'Copyright {time.strftime("%Y")}'), "OriginalFilename": f"{exe_name}.exe",
            "ProductName": p_settings.get('product_name', exe_name), "ProductVersion": p_settings.get('product_version', '1.0.0.0'),
        }
        ver_file_content = f"""# UTF-8\nVSVersionInfo(\n  ffi=FixedFileInfo(\n    filevers=({",".join(ver_info['FileVersion'].split('.'))}),\n    prodvers=({",".join(ver_info['ProductVersion'].split('.'))}),\n    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),\n  kids=[\n    StringFileInfo([StringTable('040904B0', [\n        StringStruct('CompanyName', '{ver_info["CompanyName"]}'),\n        StringStruct('FileDescription', '{ver_info["FileDescription"]}'),\n        StringStruct('FileVersion', '{ver_info["FileVersion"]}'),\n        StringStruct('InternalName', '{ver_info["InternalName"]}'),\n        StringStruct('LegalCopyright', '{ver_info["LegalCopyright"]}'),\n        StringStruct('OriginalFilename', '{ver_info["OriginalFilename"]}'),\n        StringStruct('ProductName', '{ver_info["ProductName"]}'),\n        StringStruct('ProductVersion', '{ver_info["ProductVersion"]}')])]),\n    VarFileInfo([VarStruct('Translation', [1033, 1200])])])"""
        fd, path = tempfile.mkstemp(prefix="py2win_ver_", suffix=".txt");
        with os.fdopen(fd, "w", encoding="utf-8") as f: f.write(ver_file_content)
        return path
    def _build_in_background(self, p_settings, on_complete=None):
        if not p_settings.get('script_path') or not Path(p_settings.get('script_path')).exists():
            self.log("❌ Build failed: Python script not specified or not found."); on_complete and on_complete(False); return
        if self.app: self.app.after(0, self.app.update_status, "Starting build...", 0)
        start_time = time.time(); success = False; version_file = None
        try:
            pyinstaller_exe = self.env_manager.python_executable.parent / "pyinstaller"
            dist_path = Path(p_settings.get('output_dir', './dist')); work_path = Path('./build')
            if p_settings.get('clean_build', True):
                self.log("🧹 Cleaning previous build files...");
                if dist_path.exists(): shutil.rmtree(dist_path)
                if work_path.exists(): shutil.rmtree(work_path)
                self.log("Clean complete.")
            version_file = self._create_version_file(p_settings)
            cmd = [str(pyinstaller_exe), p_settings['script_path'], "--noconfirm", f"--version-file={version_file}"]
            cmd.extend(["--name", p_settings.get('exe_name', 'MyApp')]); cmd.extend(["--distpath", str(dist_path)]); cmd.extend(["--workpath", str(work_path)])
            if p_settings.get('one_file', True): cmd.append("--onefile")
            cmd.append("--windowed" if p_settings.get('windowed', True) else "--console")
            if p := p_settings.get('icon_path'): cmd.extend(["--icon", str(p)])
            if p_settings.get('use_upx') and shutil.which("upx"): cmd.extend(["--upx-dir", str(Path(shutil.which("upx")).parent)])
            for hi in p_settings.get('hidden_imports', []): cmd.extend(["--hidden-import", hi])
            for ex in p_settings.get('exclude_modules', []): cmd.extend(["--exclude-module", ex])
            for p in p_settings.get('data_paths', []):
                sp = os.path.abspath(p); dest = os.path.basename(sp) if os.path.isdir(sp) else "."
                cmd.append(f"--add-data={sp}{(';' if os.name == 'nt' else ':')}{dest}")
            self.log("Building with PyInstaller..."); self.log(f"Command: {' '.join(cmd)}")
            if self.app: self.app.after(0, self.app.progress_bar.set, 0.1)
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            for i, line in enumerate(iter(process.stdout.readline, '')):
                self.log(line.strip());
                if self.app: self.app.after(0, self.app.progress_bar.set, min(0.9, 0.1 + (i / 200.0)))
            process.wait();
            if self.app: self.app.after(0, self.app.progress_bar.set, 1.0)
            if process.returncode == 0:
                duration = round(time.time() - start_time, 2); success = True
                self.log(f"✅ Build successful in {duration} seconds.")
                if self.app: self.app.after(0, self.app.update_status, f"Build successful! ({duration}s)", 1.0)
            else: self.log(f"❌ Build failed with exit code {process.returncode}.")
        except Exception as e: self.log(f"❌ An unexpected error occurred during build: {e}")
        finally:
            if version_file and os.path.exists(version_file): os.remove(version_file)
            if on_complete: on_complete(success)

class InstallerMaker:
    def __init__(self, app_instance=None):
        self.app = app_instance
        try: self.console = self.app.console if self.app else None
if on_complete: on_complete(success)

class InstallerMaker:
    def __init__(self, app_instance=None):
        self.app = app_instance
        self.console = getattr(self.app, 'console', None) if self.app else None
        self.nsis_provider = NSISProvider(app_instance)
    def log(self, message): log_message(self.console, message)
    def build_nsis(self, installer_settings, project_settings, security_settings, on_complete=None):
        thread = threading.Thread(target=self.nsis_provider.build, args=(installer_settings, project_settings, security_settings, on_complete), daemon=True)
        thread.start(); return thread

class NSISProvider:
    def __init__(self, app_instance=None):
        self.app = app_instance
        self.console = getattr(self.app, 'console', None) if self.app else None
    def log(self, message): log_message(self.console, message)
    def _check_nsis(self):
        if NSIS_EXE_PATH.is_file():
            if sys.platform != "win32" and not os.access(NSIS_EXE_PATH, os.X_OK): os.chmod(NSIS_EXE_PATH, 0o755)
            self.log("makensis.exe found and executable."); return True
        self.nsis_provider = NSISProvider(app_instance)
    def log(self, message): log_message(self.console, message)
    def build_nsis(self, installer_settings, project_settings, security_settings, on_complete=None):
        thread = threading.Thread(target=self.nsis_provider.build, args=(installer_settings, project_settings, security_settings, on_complete), daemon=True)
        thread.start(); return thread

class NSISProvider:
    def __init__(self, app_instance=None):
        self.app = app_instance
        try: self.console = self.app.console if self.app else None
class NSISProvider:
    def __init__(self, app_instance=None):
        self.app = app_instance
        try:
            self.console = self.app.console if self.app else None
        except Exception:
            self.console = None
    def log(self, message): log_message(self.console, message)
    def _check_nsis(self):
        if NSIS_EXE_PATH.is_file():
    def log(self, message): log_message(self.console, message)
    def _check_nsis(self):
        if NSIS_EXE_PATH.is_file():
def _check_nsis(self):
        if NSIS_EXE_PATH.is_file():
            if sys.platform != "win32" and not os.access(NSIS_EXE_PATH, os.X_OK): os.chmod(NSIS_EXE_PATH, 0o754)
            self.log("makensis.exe found and executable."); return True
        self.log("makensis.exe not found. Attempting to download and extract NSIS...")
        TOOLS_DIR.mkdir(exist_ok=True); zip_path = TOOLS_DIR / "nsis.zip"
        try:
            with urllib.request.urlopen(NSIS_URL) as response, open(zip_path, 'wb') as out_file: shutil.copyfileobj(response, out_file)
            self.log("Downloaded NSIS zip. Extracting...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref: zip_ref.extractall(NSIS_DIR)
            zip_path.unlink()
            if NSIS_EXE_PATH.is_file():
                if sys.platform != "win32": os.chmod(NSIS_EXE_PATH, 0o754)
                self.log("✅ NSIS setup complete."); return True
            self.log(f"❌ Failed to find makensis.exe at {NSIS_EXE_PATH}"); return False
        except Exception as e: self.log(f"❌ Failed to download or extract NSIS: {e}"); return False
            self.log("makensis.exe found and executable."); return True
        self.log("makensis.exe not found. Attempting to download and extract NSIS...")
        TOOLS_DIR.mkdir(exist_ok=True); zip_path = TOOLS_DIR / "nsis.zip"
        try:
            with urllib.request.urlopen(NSIS_URL) as response, open(zip_path, 'wb') as out_file: shutil.copyfileobj(response, out_file)
            self.log("Downloaded NSIS zip. Extracting...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref: zip_ref.extractall(NSIS_DIR)
            zip_path.unlink()
            if NSIS_EXE_PATH.is_file():
                if sys.platform != "win32": os.chmod(NSIS_EXE_PATH, 0o755)
                self.log("✅ NSIS setup complete."); return True
            self.log(f"❌ Failed to find makensis.exe at {NSIS_EXE_PATH}"); return False
        except Exception as e: self.log(f"❌ Failed to download or extract NSIS: {e}"); return False
    def build(self, i_settings, p_settings, s_settings, on_complete=None):
        self.log("Starting NSIS installer build..."); success = False
        try:
            if not self._check_nsis(): return
            dist_dir = Path(p_settings.get('output_dir', './dist'))
            if not dist_dir.exists() or not any(dist_dir.iterdir()): self.log("❌ Dist directory is empty. Build the application first."); return
            output_exe_path = self._get_output_path(i_settings)
            nsi_script = self._generate_nsi_script(i_settings, p_settings, dist_dir, output_exe_path)
            nsi_file = Path("./installer.nsi"); nsi_file.write_text(nsi_script, encoding='utf-8')
            self.log("Generated .nsi script."); cmd = [str(NSIS_EXE_PATH), str(nsi_file)]
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            for line in iter(process.stdout.readline, ''): self.log(line.strip())
            if process.wait() == 0:
process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            for line in iter(process.stdout.readline, ''): self.log(line.strip())
            if process.wait() == 0:
                self.log(f"✅ NSIS installer built successfully: {output_exe_path}")
                self._sign_installer(output_exe_path, s_settings)
                success = True
            else: self.log("❌ NSIS build failed.")
        except Exception as e: self.log(f"❌ An unexpected error occurred during installer build: {e}")
        finally:
            else: self.log("❌ NSIS build failed.")
        except Exception as e: self.log(f"❌ An unexpected error occurred during installer build: {e}")
        finally:
            if on_complete: on_complete(success)
    def _get_output_path(self, i_settings):
        app_name = i_settings.get('app_name', 'MyApp'); version = i_settings.get('version', '1.0')
        output_dir = Path(i_settings.get('output_dir', './installers')); output_dir.mkdir(exist_ok=True)
        return output_dir / f"Setup_{app_name}_{version}.exe"
    def _sign_installer(self, installer_path, s_settings):
        tool = s_settings.get('sign_tool_path'); cert = s_settings.get('cert_file'); pwd = s_settings.get('cert_pass')
        if not (tool and cert and Path(tool).exists() and Path(cert).exists()): self.log("Code signing skipped: tool or certificate not provided or found."); return
def _sign_installer(self, installer_path, s_settings):
        tool = s_settings.get('sign_tool_path'); cert = s_settings.get('cert_file'); pwd = s_settings.get('cert_pass')
        if not (tool and cert and Path(tool).exists() and Path(cert).exists()): self.log("Code signing skipped: tool or certificate not provided or found."); return
        self.log(f"Signing installer: {installer_path}")
        cmd = [tool, "sign", "/f", cert, "/p", pwd, "/t", "http://timestamp.digicert.com", str(installer_path)]
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            self.log("✅ Installer signed successfully.")
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            self.log("✅ Installer signed successfully.")
        except subprocess.CalledProcessError as e: self.log(f"❌ Code signing failed: {e.stderr}")
    def _generate_nsi_script(self, i_settings, p_settings, dist_dir, output_exe):
        exe_name = f"{p_settings.get('exe_name', 'MyApp')}.exe"
        script = f"""
!define APPNAME "{i_settings.get('app_name', 'MyApp')}"
!define COMPANYNAME "{p_settings.get('company_name', 'My Company')}"
!define VERSION "{i_settings.get('version', '1.0.0')}"
!define EXENAME "{exe_name}"
OutFile "{output_exe}"
InstallDir "$PROGRAMFILES64\\${{APPNAME}}"
RequestExecutionLevel admin
VIAddVersionKey "ProductName" "${{APPNAME}}"; VIAddVersionKey "ProductVersion" "${{VERSION}}"
Page directory; Page instfiles; UninstPage uninstConfirm
Section "Install"
  SetOutPath $INSTDIR; File /r "{dist_dir}\\*.*"
  WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${{APPNAME}}" "DisplayName" "${{APPNAME}}"
  WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${{APPNAME}}" "UninstallString" '"$INSTDIR\\uninstall.exe"'
  WriteUninstaller "$INSTDIR\\uninstall.exe"
  {f'CreateShortCut "$DESKTOP\\${{APPNAME}}.lnk" "$INSTDIR\\${{EXENAME}}"' if i_settings.get("desktop_shortcut") else ""}
  {f'CreateDirectory "$SMPROGRAMS\\${{APPNAME}}"\n  CreateShortCut "$SMPROGRAMS\\${{APPNAME}}\\{{APPNAME}}.lnk" "$INSTDIR\\${{EXENAME}}"' if i_settings.get("start_menu_shortcut") else ""}
SectionEnd
Section "Uninstall"
  Delete "$INSTDIR\\*.*"; RMDir /r "$INSTDIR"
  {f'Delete "$DESKTOP\\${{APPNAME}}.lnk"' if i_settings.get("desktop_shortcut") else ""}
  {f'RMDir /r "$SMPROGRAMS\\${{APPNAME}}"' if i_settings.get("start_menu_shortcut") else ""}
  DeleteRegKey HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${{APPNAME}}"
SectionEnd
"""
        return script

class AIAssistantDialog(customtkinter.CTkToplevel):
    def __init__(self, parent, script_path, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.title("AI Assistant"); self.geometry("600x400"); self.parent = parent; self.script_path = script_path
        self.grid_columnconfigure(0, weight=1); self.grid_rowconfigure(1, weight=1)
        customtkinter.CTkLabel(self, text="AI Analysis & Suggestions", font=("", 16, "bold")).grid(row=0, column=0, padx=15, pady=15)
        self.textbox = customtkinter.CTkTextbox(self, wrap="word"); self.textbox.grid(row=1, column=0, padx=15, pady=15, sticky="nsew")
        self.analyze()
    def analyze(self):
        if not self.script_path or not Path(self.script_path).exists(): self.textbox.insert("end", "Please select a valid Python script first."); return
        try:
            with open(self.script_path, "r", encoding="utf-8") as f: content = f.read().lower()
            suggestions = []
            if "matplotlib" in content: suggestions.append("• Matplotlib detected: This library often requires its data files ('mpl-data'). Consider adding its folder to 'Additional Files & Folders'.")
            if "pyside6" in content or "pyqt6" in content: suggestions.append("• Qt (PySide/PyQt) detected: Remember to add your UI files (.ui), resource files (.qrc), and translation files (.qm) as data. Common hidden imports include 'PySide6.QtSvg' and 'PySide6.plugins.platforms'.")
            if "requests" in content: suggestions.append("• Requests detected: This library uses 'certifi' for SSL. PyInstaller usually handles this, but if you face SSL errors, ensure 'certifi' is included.")
            if "pandas" in content: suggestions.append("• Pandas detected: This can be a large dependency. Ensure you are using a virtual environment. One-file mode may have a slower startup.")
            if not suggestions: suggestions.append("Analysis complete. No common problematic libraries detected. If you have issues, check the PyInstaller build log for 'ModuleNotFound' errors.")
            self.textbox.insert("end", "Analysis Results:\n\n" + "\n\n".join(suggestions))
        except Exception as e: self.textbox.insert("end", f"Error during analysis: {e}")

class Py2WinPremiumApp(customtkinter.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} v{APP_VERSION}"); self.geometry("1200x800"); customtkinter.set_appearance_mode("Dark"); customtkinter.set_default_color_theme("blue")
        self.console = None; self.project_settings = {}; self.is_env_valid = False; self.ai_assistant_window = None; self.data_paths = []
        self.env_manager = EnvManager(self); self.build_orchestrator = BuildOrchestrator(self); self.installer_maker = InstallerMaker(self)
        self.create_widgets(); self.load_default_project()

    def create_widgets(self):
        self.grid_columnconfigure(1, weight=1); self.grid_rowconfigure(0, weight=1)
        self.sidebar_frame = customtkinter.CTkFrame(self, width=200, corner_radius=0); self.sidebar_frame.grid(row=0, column=0, rowspan=2, sticky="nsw"); self.sidebar_frame.grid_rowconfigure(6, weight=1)
        customtkinter.CTkLabel(self.sidebar_frame, text="Py2Win Premium", font=customtkinter.CTkFont(size=20, weight="bold")).grid(row=0, column=0, padx=20, pady=(20, 10))
        self.validate_env_button = customtkinter.CTkButton(self.sidebar_frame, text="Validate Environment", command=self.validate_env); self.validate_env_button.grid(row=1, column=0, padx=20, pady=10)
        self.ai_btn = customtkinter.CTkButton(self.sidebar_frame, text="🤖 AI Assistant", command=self.open_ai_assistant); self.ai_btn.grid(row=2, column=0, padx=20, pady=10)
        self.update_btn = customtkinter.CTkButton(self.sidebar_frame, text="Check for Updates", command=self.check_for_updates); self.update_btn.grid(row=3, column=0, padx=20, pady=10)
        self.main_frame = customtkinter.CTkFrame(self); self.main_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.tab_view = customtkinter.CTkTabview(self.main_frame); self.tab_view.pack(expand=True, fill="both", padx=5, pady=5)
        tabs = ["Build", "Advanced", "Branding", "Installer", "Security"]; [self.tab_view.add(t) for t in tabs]
        self.create_build_tab(self.tab_view.tab("Build")); self.create_advanced_tab(self.tab_view.tab("Advanced")); self.create_branding_tab(self.tab_view.tab("Branding")); self.create_installer_tab(self.tab_view.tab("Installer")); self.create_security_tab(self.tab_view.tab("Security"))
        self.console_frame = customtkinter.CTkFrame(self); self.console_frame.grid(row=1, column=1, sticky="nsew", padx=10, pady=(0,10)); self.console_frame.grid_columnconfigure(0, weight=1)
        self.console = customtkinter.CTkTextbox(self.console_frame, height=200); self.console.pack(expand=True, fill="both", padx=5, pady=5)
        self.status_frame = customtkinter.CTkFrame(self.sidebar_frame, corner_radius=0); self.status_frame.grid(row=9, column=0, sticky="sew")
        self.status_label = customtkinter.CTkLabel(self.status_frame, text="Ready", anchor="w"); self.status_label.pack(side="left", padx=10)
        self.progress_bar = customtkinter.CTkProgressBar(self.status_frame); self.progress_bar.pack(side="right", padx=10, pady=10, fill="x", expand=True); self.progress_bar.set(0)

    def create_build_tab(self, tab):
        tab.grid_columnconfigure(1, weight=1)
        customtkinter.CTkLabel(tab, text="Python Script:").grid(row=0, column=0, padx=10, pady=10, sticky="w"); self.script_entry = customtkinter.CTkEntry(tab, width=400); self.script_entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew"); Tooltip(self.script_entry, "The main .py or .pyw file of your application.")
        customtkinter.CTkButton(tab, text="Browse...", command=self.browse_script).grid(row=0, column=2, padx=10, pady=10)
        customtkinter.CTkLabel(tab, text="Executable Name:").grid(row=1, column=0, padx=10, pady=10, sticky="w"); self.exe_name_entry = customtkinter.CTkEntry(tab); self.exe_name_entry.grid(row=1, column=1, padx=10, pady=10, sticky="ew"); Tooltip(self.exe_name_entry, "The name of the final .exe file (without extension).")
        customtkinter.CTkLabel(tab, text="Output Directory:").grid(row=2, column=0, padx=10, pady=10, sticky="w"); self.output_dir_entry = customtkinter.CTkEntry(tab); self.output_dir_entry.grid(row=2, column=1, padx=10, pady=10, sticky="ew"); Tooltip(self.output_dir_entry, "The folder where the final executable or app folder will be placed. Defaults to './dist'.")
        customtkinter.CTkButton(tab, text="Browse...", command=self.browse_output_dir).grid(row=2, column=2, padx=10, pady=10)
        self.one_file_var = customtkinter.StringVar(value="on"); ofc = customtkinter.CTkCheckBox(tab, text="Single File Executable (--onefile)", variable=self.one_file_var, onvalue="on", offvalue="off"); ofc.grid(row=3, column=1, padx=10, pady=10, sticky="w"); Tooltip(ofc, "Package everything into a single .exe file. May have slower startup.")
        self.windowed_var = customtkinter.StringVar(value="on"); wc = customtkinter.CTkCheckBox(tab, text="Windowed Application (--windowed)", variable=self.windowed_var, onvalue="on", offvalue="off"); wc.grid(row=4, column=1, padx=10, pady=10, sticky="w"); Tooltip(wc, "For GUI applications. Hides the black console window.")
        customtkinter.CTkButton(tab, text="Build Executable", height=40, font=("", 16, "bold"), command=self.start_build).grid(row=5, column=0, columnspan=4, padx=20, pady=20, sticky="ew")

    def create_advanced_tab(self, tab):
        tab.grid_columnconfigure(0, weight=1); tab.grid_rowconfigure(3, weight=1)
        options_frame = customtkinter.CTkFrame(tab); options_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew"); options_frame.grid_columnconfigure((0,1), weight=1)
        self.clean_build_var = customtkinter.StringVar(value="on"); cbc = customtkinter.CTkCheckBox(options_frame, text="Clean Build", variable=self.clean_build_var, onvalue="on", offvalue="off"); cbc.grid(row=0, column=0, padx=10, pady=10, sticky="w"); Tooltip(cbc, "Deletes old 'build' and 'dist' folders before starting a new build.")
        self.use_upx_var = customtkinter.StringVar(value="off"); upx_cb = customtkinter.CTkCheckBox(options_frame, text="Use UPX compression", variable=self.use_upx_var, onvalue="on", offvalue="off"); upx_cb.grid(row=0, column=1, padx=10, pady=10, sticky="w"); Tooltip(upx_cb, "Requires UPX in PATH. Reduces file size but may affect startup time.")
        hid_frame = customtkinter.CTkFrame(tab); hid_frame.grid(row=1, column=0, padx=10, pady=6, sticky="ew"); hid_frame.grid_columnconfigure(1, weight=1)
        customtkinter.CTkLabel(hid_frame, text="Hidden Imports:").grid(row=0, column=0, padx=10, pady=8, sticky="w"); self.hidden_entry = customtkinter.CTkEntry(hid_frame, placeholder_text="module_name"); self.hidden_entry.grid(row=0, column=1, padx=6, pady=8, sticky="ew"); Tooltip(self.hidden_entry, "Enter a module name that PyInstaller might miss and click 'Add'.")
        customtkinter.CTkButton(hid_frame, text="Add", width=80, command=self._add_hidden).grid(row=0, column=2, padx=6, pady=8)
        self.hidden_list = Listbox(hid_frame, height=4, bg="#2B2B2B", fg="white", selectbackground="#1F6AA5", borderwidth=0, highlightthickness=1, highlightcolor="#565B5E", selectmode="extended"); self.hidden_list.grid(row=1, column=0, columnspan=2, padx=10, pady=(0,10), sticky="ew")
        customtkinter.CTkButton(hid_frame, text="Remove Selected", command=self._remove_hidden).grid(row=1, column=2, padx=6, pady=(0,10))
        exc_frame = customtkinter.CTkFrame(tab); exc_frame.grid(row=2, column=0, padx=10, pady=6, sticky="ew"); exc_frame.grid_columnconfigure(1, weight=1)
        customtkinter.CTkLabel(exc_frame, text="Exclude Modules:").grid(row=0, column=0, padx=10, pady=8, sticky="w"); self.exclude_entry = customtkinter.CTkEntry(exc_frame, placeholder_text="module_name"); self.exclude_entry.grid(row=0, column=1, padx=6, pady=8, sticky="ew"); Tooltip(self.exclude_entry, "Enter a module name to exclude from the build to save space.")
        customtkinter.CTkButton(exc_frame, text="Add", width=80, command=self._add_exclude).grid(row=0, column=2, padx=6, pady=8)
        self.exclude_list = Listbox(exc_frame, height=4, bg="#2B2B2B", fg="white", selectbackground="#1F6AA5", borderwidth=0, highlightthickness=1, highlightcolor="#565B5E", selectmode="extended"); self.exclude_list.grid(row=1, column=0, columnspan=2, padx=10, pady=(0,10), sticky="ew")
        customtkinter.CTkButton(exc_frame, text="Remove Selected", command=self._remove_exclude).grid(row=1, column=2, padx=6, pady=(0,10))
        data_frame = customtkinter.CTkFrame(tab); data_frame.grid(row=3, column=0, padx=10, pady=6, sticky="nsew"); data_frame.grid_columnconfigure(0, weight=1); data_frame.grid_rowconfigure(1, weight=1)
        customtkinter.CTkLabel(data_frame, text="Additional Files & Folders:").grid(row=0, column=0, columnspan=2, padx=10, pady=(10, 0), sticky="w")
        self.data_listbox = Listbox(data_frame, bg="#2B2B2B", fg="white", selectbackground="#1F6AA5", borderwidth=0, highlightthickness=1, highlightcolor="#565B5E", selectmode="extended"); self.data_listbox.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
        btns = customtkinter.CTkFrame(data_frame, fg_color="transparent"); btns.grid(row=1, column=1, padx=(0, 10), pady=10, sticky="ns")
        customtkinter.CTkButton(btns, text="Add File(s)", command=self._add_data_files).grid(row=0, column=0, padx=5, pady=5); customtkinter.CTkButton(btns, text="Add Folder", command=self._add_data_folder).grid(row=1, column=0, padx=5, pady=5); customtkinter.CTkButton(btns, text="Remove", command=self._remove_selected_data).grid(row=2, column=0, padx=5, pady=5)

    def create_branding_tab(self, tab):
        tab.grid_columnconfigure(1, weight=1); customtkinter.CTkLabel(tab, text="EXE Metadata & Branding", font=customtkinter.CTkFont(size=16, weight="bold")).grid(row=0, column=0, columnspan=2, padx=10, pady=10, sticky="w")
        fields = {"Company Name:": "company_name", "Product Name:": "product_name", "File Description:": "file_description", "File Version (x.x.x.x):": "file_version", "Product Version (x.x.x.x):": "product_version", "Legal Copyright:": "legal_copyright"}; self.branding_entries = {}
        for i, (label, key) in enumerate(fields.items()):
            customtkinter.CTkLabel(tab, text=label).grid(row=i+1, column=0, padx=10, pady=6, sticky="e"); entry = customtkinter.CTkEntry(tab); entry.grid(row=i+1, column=1, padx=10, pady=6, sticky="ew"); self.branding_entries[key] = entry; Tooltip(entry, f"Sets the '{label[:-1]}' field in the EXE's properties.")
        self.branding_entries["company_name"].insert(0, "iD01t Productions"); self.branding_entries["file_version"].insert(0, "1.0.0.0"); self.branding_entries["product_version"].insert(0, "1.0.0.0"); self.branding_entries["legal_copyright"].insert(0, f"Copyright {time.strftime('%Y')} iD01t Productions")

    def create_installer_tab(self, tab):
        tab.grid_columnconfigure(1, weight=1)
        customtkinter.CTkLabel(tab, text="Installer Settings", font=customtkinter.CTkFont(size=16, weight="bold")).grid(row=0, column=0, columnspan=2, padx=10, pady=10, sticky="w")
        self.inst_app_name = customtkinter.CTkEntry(tab, placeholder_text="App Name"); self.inst_app_name.grid(row=1, column=1, padx=10, pady=5, sticky="ew"); customtkinter.CTkLabel(tab, text="Installer App Name:").grid(row=1, column=0, padx=10, pady=5, sticky="e")
        self.inst_version = customtkinter.CTkEntry(tab, placeholder_text="1.0.0"); self.inst_version.grid(row=2, column=1, padx=10, pady=5, sticky="ew"); customtkinter.CTkLabel(tab, text="Installer Version:").grid(row=2, column=0, padx=10, pady=5, sticky="e")
        self.inst_output_dir = customtkinter.CTkEntry(tab, placeholder_text="./installers"); self.inst_output_dir.grid(row=3, column=1, padx=10, pady=5, sticky="ew"); customtkinter.CTkLabel(tab, text="Installer Output Dir:").grid(row=3, column=0, padx=10, pady=5, sticky="e")
        options_frame = customtkinter.CTkFrame(tab, fg_color="transparent"); options_frame.grid(row=4, column=1, padx=10, pady=10, sticky="w")
        self.desktop_shortcut_var = customtkinter.StringVar(value="on"); dsc = customtkinter.CTkCheckBox(options_frame, text="Desktop Shortcut", variable=self.desktop_shortcut_var, onvalue="on", offvalue="off"); dsc.pack(side="left", padx=10); Tooltip(dsc, "Create a shortcut to your app on the user's desktop.")
        self.start_menu_var = customtkinter.StringVar(value="on"); smc = customtkinter.CTkCheckBox(options_frame, text="Start Menu Shortcut", variable=self.start_menu_var, onvalue="on", offvalue="off"); smc.pack(side="left", padx=10); Tooltip(smc, "Create a shortcut in the Windows Start Menu.")
        customtkinter.CTkButton(tab, text="Build NSIS Installer", command=self.build_nsis_installer).grid(row=5, column=0, columnspan=2, padx=10, pady=20, sticky="ew")

    def create_security_tab(self, tab):
        tab.grid_columnconfigure(1, weight=1)
        customtkinter.CTkLabel(tab, text="Code Signing (for signed installer)", font=customtkinter.CTkFont(size=16, weight="bold")).grid(row=0, column=0, columnspan=3, padx=10, pady=10, sticky="w")
        customtkinter.CTkLabel(tab, text="Sign Tool Path:").grid(row=1, column=0, padx=10, pady=6, sticky="e"); self.sign_tool_entry = customtkinter.CTkEntry(tab, placeholder_text="C:\\...\\signtool.exe"); self.sign_tool_entry.grid(row=1, column=1, padx=10, pady=6, sticky="ew"); Tooltip(self.sign_tool_entry, "Path to signtool.exe, usually from the Windows SDK.")
        customtkinter.CTkButton(tab, text="Browse...", command=lambda: self.sign_tool_entry.insert(0, filedialog.askopenfilename(title="Select signtool.exe") or "")).grid(row=1, column=2, padx=10)
        customtkinter.CTkLabel(tab, text="Certificate (.pfx):").grid(row=2, column=0, padx=10, pady=6, sticky="e"); self.cert_file_entry = customtkinter.CTkEntry(tab); self.cert_file_entry.grid(row=2, column=1, padx=10, pady=6, sticky="ew"); Tooltip(self.cert_file_entry, "Your .pfx code signing certificate file.")
        customtkinter.CTkButton(tab, text="Browse...", command=lambda: self.cert_file_entry.insert(0, filedialog.askopenfilename(title="Select .pfx certificate") or "")).grid(row=2, column=2, padx=10)
        customtkinter.CTkLabel(tab, text="Password:").grid(row=3, column=0, padx=10, pady=6, sticky="e"); self.cert_pass_entry = customtkinter.CTkEntry(tab, show="*"); self.cert_pass_entry.grid(row=3, column=1, padx=10, pady=6, sticky="ew"); Tooltip(self.cert_pass_entry, "The password for your certificate file.")

    def _add_hidden(self): m = self.hidden_entry.get().strip(); self.hidden_list.insert("end", m) and self.hidden_entry.delete(0, "end") if m else None
    def _remove_hidden(self): [self.hidden_list.delete(i) for i in sorted(self.hidden_list.curselection(), reverse=True)]
    def _add_exclude(self): m = self.exclude_entry.get().strip(); self.exclude_list.insert("end", m) and self.exclude_entry.delete(0, "end") if m else None
    def _remove_exclude(self): [self.exclude_list.delete(i) for i in sorted(self.exclude_list.curselection(), reverse=True)]
    def _add_data_files(self): [self.data_paths.append(p) or self.data_listbox.insert("end", f"FILE: {p}") for p in filedialog.askopenfilenames(title="Select file(s) to bundle") if p not in self.data_paths]
    def _add_data_folder(self): p = filedialog.askdirectory(title="Select folder to bundle"); self.data_paths.append(p) and self.data_listbox.insert("end", f"DIR:  {p}") if p and p not in self.data_paths else None
    def _remove_selected_data(self): [self.data_listbox.delete(i) or self.data_paths.pop(i) for i in sorted(self.data_listbox.curselection(), reverse=True)]

    def update_status(self, text, progress=None): self.status_label.configure(text=text); self.progress_bar.set(progress if progress is not None else self.progress_bar.get())
    def validate_env(self): self.validate_env_button.configure(state="disabled", text="Validating..."); self.env_manager.validate_environment(self.on_env_validated)
    def on_env_validated(self, success): self.is_env_valid = success; self.validate_env_button.configure(state="normal", text="Validate Environment", fg_color="green" if success else "red")
    def browse_script(self):
        path = filedialog.askopenfilename(filetypes=[("Python Files", "*.py *.pyw")])
        if path: self.script_entry.delete(0, "end"); self.script_entry.insert(0, path); self.exe_name_entry.delete(0, "end"); self.exe_name_entry.insert(0, Path(path).stem); self.branding_entries["product_name"].delete(0, "end"); self.branding_entries["product_name"].insert(0, Path(path).stem)
    def browse_output_dir(self): path = filedialog.askdirectory(); self.output_dir_entry.delete(0, "end"); self.output_dir_entry.insert(0, path)
    def start_build(self):
        if not self.is_env_valid: messagebox.showerror("Environment Invalid", "Please validate the environment before building."); return
        self.build_orchestrator.build(self.gather_project_settings())
    def build_nsis_installer(self):
        if not self.is_env_valid: messagebox.showerror("Environment Invalid", "Please validate environment first."); return
        self.installer_maker.build_nsis(self.gather_installer_settings(), self.gather_project_settings(), self.gather_security_settings())
    def gather_project_settings(self):
        settings = {"script_path": self.script_entry.get(), "exe_name": self.exe_name_entry.get(), "output_dir": self.output_dir_entry.get() or "./dist", "one_file": self.one_file_var.get() == "on", "windowed": self.windowed_var.get() == "on", "clean_build": self.clean_build_var.get() == "on", "use_upx": self.use_upx_var.get() == "on", "hidden_imports": list(self.hidden_list.get(0, "end")), "exclude_modules": list(self.exclude_list.get(0, "end")), "data_paths": self.data_paths, "icon_path": ""}
        for key, entry in self.branding_entries.items(): settings[key] = entry.get()
        return settings
    def gather_installer_settings(self):
        return {"app_name": self.inst_app_name.get() or self.exe_name_entry.get(), "version": self.inst_version.get() or "1.0.0", "output_dir": self.inst_output_dir.get(), "desktop_shortcut": self.desktop_shortcut_var.get() == "on", "start_menu_shortcut": self.start_menu_var.get() == "on"}
    def gather_security_settings(self):
        return {"sign_tool_path": self.sign_tool_entry.get(), "cert_file": self.cert_file_entry.get(), "cert_pass": self.cert_pass_entry.get()}
    def load_default_project(self): pass
    def open_ai_assistant(self):
        if self.ai_assistant_window is None or not self.ai_assistant_window.winfo_exists():
            self.ai_assistant_window = AIAssistantDialog(self, self.script_entry.get())
        else: self.ai_assistant_window.focus()
    def check_for_updates(self):
        self.update_status("Checking for updates...")
        def _check():
            try:
                with urllib.request.urlopen(UPDATE_URL, timeout=5) as response:
                    latest_version = response.read().decode('utf-8').strip()
                if latest_version > APP_VERSION:
                    messagebox.showinfo("Update Available", f"A new version ({latest_version}) is available!\nVisit the website to download.")
                else:
                    messagebox.showinfo("No Updates", f"You are running the latest version ({APP_VERSION}).")
            except Exception as e: messagebox.showerror("Update Check Failed", f"Could not check for updates: {e}")
            if self.winfo_exists(): self.update_status("Ready")
        threading.Thread(target=_check, daemon=True).start()

if __name__ == "__main__":
    if not hasattr(subprocess, 'CREATE_NO_WINDOW'): subprocess.CREATE_NO_WINDOW = 0
    
    if len(sys.argv) > 1 and sys.argv[1] == '--smoke-test':
        print("--- Running Headless End-to-End Smoke Test ---")
        
        # Use mutable lists to store callback results, avoiding 'nonlocal' issues
        validation_status, build_status, installer_status = [], [], []
        validation_complete, build_complete, installer_complete = threading.Event(), threading.Event(), threading.Event()

        def on_validation_complete(success): validation_status.append(success); validation_complete.set()
        def on_build_complete(success): build_status.append(success); build_complete.set()
        def on_installer_complete(success): installer_status.append(success); installer_complete.set()

        # 1. Validate Environment
        env_manager = EnvManager(); env_manager.validate_environment(on_validation_complete)
        print("Waiting for environment validation..."); completed = validation_complete.wait(timeout=300)
        if not (completed and validation_status and validation_status[0]): print("❌ Smoke Test Failed: Environment validation failed or timed out."); sys.exit(1)
        print("✅ Environment validation complete.")
        
        # 2. Run smoke test build
        build_orchestrator = BuildOrchestrator()
        test_app_path = Path("./smoke_test_app.py"); test_app_path.write_text("print('Hello from smoke test app!')")
        smoke_settings = {"script_path": str(test_app_path), "exe_name": "SmokeTestApp", "output_dir": "./dist_smoke", "one_file": True, "windowed": False, "clean_build": True}
        build_orchestrator.build(smoke_settings, on_build_complete)
        print("Build triggered. Waiting for completion..."); completed = build_complete.wait(timeout=300)
        if not (completed and build_status and build_status[0]): print("❌ Smoke Test Failed: Build process failed or timed out."); sys.exit(1)
        print("✅ Build process complete.")

        # 3. Run installer creation (only if on Windows)
        installer_created = False
        if sys.platform == "win32":
            installer_maker = InstallerMaker()
            installer_settings = {"app_name": "SmokeTestApp", "version": "1.0", "output_dir": "./installers_smoke", "desktop_shortcut": True}
            installer_maker.build_nsis(installer_settings, smoke_settings, {}, on_installer_complete)
            print("Installer build triggered. Waiting for completion..."); completed = installer_complete.wait(timeout=120)
            if not (completed and installer_status and installer_status[0]): print("❌ Smoke Test Failed: Installer creation failed or timed out."); sys.exit(1)
            print("✅ Installer creation complete.")
            installer_created = True
        else:
            print("ℹ️ Skipping NSIS installer test on non-Windows platform.")
            installer_created = True # Mark as "success" for non-windows platforms

        # 4. Verify outputs
        exe_path = Path("./dist_smoke/SmokeTestApp.exe") if sys.platform == "win32" else Path("./dist_smoke/SmokeTestApp")
        installer_path = Path("./installers_smoke/Setup_SmokeTestApp_1.0.exe")

        exe_ok = exe_path.is_file()
        installer_ok = (not (sys.platform == "win32")) or installer_path.is_file()

        if exe_ok and installer_ok:
            print(f"✅ Smoke Test Success: All possible artifacts created.")
            sys.exit(0)
        else:
            print(f"❌ Smoke Test Failed: Missing output files. Found EXE: {exe_ok}, Found Installer: {installer_path.is_file() if sys.platform == 'win32' else 'skipped'}.")
            sys.exit(1)
    else:
        app = Py2WinPremiumApp()
        app.mainloop()
