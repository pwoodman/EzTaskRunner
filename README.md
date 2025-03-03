# EzTaskRunner

A web-based task scheduling and monitoring application for running scripts on a schedule. EzTaskRunner provides an easy-to-use interface for setting up, executing, and monitoring automated tasks for Python, PowerShell, and Batch scripts.

## 🚀 Features

- **Multi-Script Support**: Run Python, PowerShell, and Batch scripts from a single interface
- **Schedule Management**: Schedule scripts to run at specific intervals
- **Manual Execution**: Run scripts immediately for testing and verification
- **Task Monitoring**: Track execution status, history, and results
- **Resource Usage**: Monitor system resource usage during task execution
- **Auto-retry**: Configure tasks to automatically retry on failure
- **Email Notifications**: Receive notifications when tasks fail
- **Logging Configuration**: Easily adjust logging verbosity from the settings page
- **Search Functionality**: Easily find tasks across your workspace
- **Detailed History**: Access complete execution history with timestamps and results
- **Visual Indicators**: Script type badges help identify script types at a glance

## 📋 Prerequisites

- Python 3.7 or higher
- PowerShell (for PowerShell scripts - Windows built-in or PowerShell Core)
- Modern web browser (Chrome, Firefox, Edge, Safari)
- Operating system: Windows, macOS, or Linux (PowerShell scripts require compatible PowerShell version)

## 🔧 Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/eztaskrunner.git
   cd eztaskrunner
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   ```

3. Activate the virtual environment:
   - Windows:
     ```bash
     venv\Scripts\activate
     ```
   - Unix/MacOS:
     ```bash
     source venv/bin/activate
     ```

4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

5. Create an `.env` file based on the provided `.env.example`:
   ```bash
   cp .env.example .env
   ```
   
6. Generate a secure secret key for Flask and add it to your `.env` file:
   ```bash
   python -c "import secrets; print('FLASK_SECRET_KEY=' + secrets.token_hex(16))"
   ```

## ⚙️ Configuration

The application uses environment variables for configuration:

| Variable | Description | Default |
|----------|-------------|---------|
| `FLASK_SECRET_KEY` | Flask session secret key | Required, no default |
| `SCRIPTS_DIR` | Directory for user scripts | `scripts/` |
| `LOG_DIR` | Directory for application logs | `logs/` |
| `TASK_HISTORY_DIR` | Directory for task execution history | `task_history/` |
| `LOG_LEVEL` | Logging verbosity level | `INFO` |
| `EMAIL_NOTIFICATIONS_ENABLED` | Enable email notifications | `False` |
| `EMAIL_SMTP_HOST` | SMTP server host | `smtp.example.com` |
| `EMAIL_SMTP_PORT` | SMTP server port | `587` |
| `EMAIL_SMTP_USER` | SMTP username | `user` |
| `EMAIL_SMTP_PASS` | SMTP password | `password` |
| `EMAIL_SENDER` | Sender email address | `eztaskrunner@example.com` |
| `EMAIL_RECIPIENTS` | Comma-separated list of recipients | `admin@example.com` |

## 🚦 Usage

1. Start the application:
   ```bash
   python run.py
   ```

2. Command-line arguments:
   ```
   --host: Host to run the server on (default: 127.0.0.1)
   --port: Port to run the server on (default: 5000)
   --debug: Run in debug mode
   ```

3. Access the web interface at `http://localhost:5000`

## 📝 Supported Script Types

EzTaskRunner supports the following script types:

### Python Scripts (`.py`)
Python scripts must:
1. Have a `main()` function that serves as the entry point
2. Return a value or string that will be captured as the task output
3. Not use interactive prompts or require user input

Example Python script:
```python
def main():
    """
    This function will be called when the task is executed.
    Return values will be captured in the task history.
    """
    # Your code here
    result = "Task completed successfully"
    return result
```

### PowerShell Scripts (`.ps1`)
PowerShell scripts should:
1. Be standalone and not require interactive input
2. Use Write-Output for results that should be captured

Example PowerShell script:
```powershell
# Your PowerShell code here
$result = "PowerShell task completed"
Write-Output $result
```

### Batch Scripts (`.bat`, `.cmd`)
Batch scripts should:
1. Be standalone and not require interactive input
2. Output results to standard output (ECHO)

Example Batch script:
```batch
@echo off
REM Your batch code here
echo Batch task completed successfully
```

## 🔧 Settings Page

The settings page allows you to configure:

1. **Email Notifications**:
   - Enable/disable email notifications for task failures
   - Configure SMTP server details
   - Set sender and recipient email addresses
   - Test email configuration

2. **Logging Settings**:
   - Set logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
   - Control the verbosity of application logs

## 📊 Monitoring Dashboard

The monitoring dashboard provides:

1. **System Resources**:
   - CPU, memory, and disk usage statistics
   - Color-coded indicators for resource status

2. **Running Tasks**:
   - Real-time view of currently executing tasks
   - Script type indicators
   - Duration tracking
   - Stop button for terminating tasks

3. **Execution History**:
   - Recent task failures and executions
   - Filterable by time period
   - Detailed execution information

## 📁 Project Structure

```
eztaskrunner/
├── app/                    # Application package
│   ├── core.py             # Flask application setup
│   ├── task_manager.py     # Task execution logic
│   ├── scheduler.py        # APScheduler configuration
│   ├── utils/              # Utility functions
│   ├── routes/             # Flask route definitions
│   ├── views/              # Template rendering functions
│   ├── templates/          # Jinja2 HTML templates
│   └── static/             # Static files (CSS, JavaScript)
├── scripts/                # Directory for user scripts
├── logs/                   # Application logs
├── task_history/           # Task execution history
├── data/                   # Data storage for scripts
├── tasks/                  # Task configuration storage
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variables template
├── .gitignore              # Git ignore rules
└── run.py                  # Application entry point
```

## 📜 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🔗 Links

- [Project Homepage](https://github.com/yourusername/eztaskrunner)
- [Issue Tracker](https://github.com/yourusername/eztaskrunner/issues)
- [Buy me a coffee](https://buymeacoffee.com/patrickwoodman) 