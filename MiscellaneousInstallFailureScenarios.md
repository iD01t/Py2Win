Miscellaneous Install Failure Scenarios
This document lists EXE return code values for miscellaneous installation failure scenarios for the Py2Win installer, along with URLs to specific documentation where applicable. These codes assist testers in diagnosing installation issues.



Scenario
EXE Return Code Value
Description
Documentation URL



Invalid system architecture
1632
The installer is incompatible with the system architecture (e.g., 32-bit installer on a 64-bit system). Ensure the correct installer version (e.g., Py2Win-x64.exe for 64-bit systems) is used. Troubleshooting: Verify system bitness via systeminfo or Windows Settings > System > About. Re-download the correct installer from Py2Win releases. Check logs at [installation directory]/logs/install.log for details. If running from source, ensure the Python runtime matches the system architecture (e.g., 64-bit Python 3.8+).
https://github.com/iD01t/Py2Win/blob/main/docs/installer.md#invalid-system-architecture


Corrupted installer file
1606
The installer file is corrupted or incomplete. Re-download the installer from the official source.
https://github.com/iD01t/Py2Win/blob/main/docs/troubleshooting.md#corrupted-installer


Missing system prerequisites
1608
Required system components (e.g., Microsoft Visual C++ Redistributable or Python runtime) are missing. Install prerequisites before retrying.
https://github.com/iD01t/Py2Win/blob/main/docs/installer.md#prerequisites


User account control (UAC) denial
1222
The installer was denied by User Account Control (UAC). Run the installer as an administrator.
https://github.com/iD01t/Py2Win/blob/main/docs/installer.md#uac-issues


Notes

Return Code Source: These codes are based on standard Windows Installer (MSI) conventions, commonly used by tools like Inno Setup or PyInstaller. If Py2Win uses a custom installer, refer to the Installer Handling documentation for specific codes.
Troubleshooting: 
Check installation logs at [installation directory]/logs/install.log for detailed error messages.
For architecture issues, verify the system’s bitness (32-bit or 64-bit) and download the matching installer.
For prerequisite issues, ensure Python 3.8+ and any required runtimes are installed.


Documentation: The URLs provided point to placeholder sections in the Py2Win repository’s documentation. Update these links to reflect actual documentation if available.
Contact: Report issues via GitHub Issues.

Last Updated: July 27, 2025
