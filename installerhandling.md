Installer Handling
Overview
This section provides information on handling the Py2Win installer, including documentation for all miscellaneous EXE return code values. These return codes are used to indicate the success or failure of the installation process and assist in troubleshooting.
EXE Return Codes
The Py2Win installer (if applicable) generates return codes to indicate the outcome of the installation process. Below is the documentation for all possible return codes:



Return Code
Description



0
Success: Installation completed successfully.


1
General Error: An unspecified error occurred during installation. Check the installer logs in [installation directory]/logs/install.log for details.


2
Missing Dependencies: Required dependencies (e.g., Python runtime) are not installed. Ensure Python 3.8+ is installed before running the installer.


3
Insufficient Permissions: The installer requires elevated (administrator) permissions. Run the installer as an administrator.


4
Disk Space Error: Insufficient disk space to complete the installation. Free up at least 500MB of disk space and try again.


5
Invalid Configuration: The installer detected an invalid configuration file or parameter. Verify the configuration in [installation directory]/config.ini.


Notes:

If no installer is used (e.g., Py2Win is run directly from source), these return codes are not applicable. Instead, refer to the Python script execution errors in the README or logs.
Additional return codes may be added in future releases. Check the GitHub repository for updates.

Documentation
For detailed information on installer handling and troubleshooting:

Primary Documentation: https://github.com/iD01t/Py2Win/blob/main/docs/installer.md
Troubleshooting Guide: Refer to the Troubleshooting section in the repository for common issues and solutions.
Log Files: Installation logs are saved to [installation directory]/logs/install.log. Review these logs for detailed error messages.

Contact
For issues related to the installer or return codes, please open an issue on the GitHub repository: https://github.com/iD01t/Py2Win/issues.
Last Updated: July 27, 2025
