import sys
import os
import socket
import webbrowser
import threading
import shutil
import tempfile
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QGroupBox, QPushButton, QLabel, QLineEdit, QTableWidget, QTableWidgetItem,
    QTextEdit, QComboBox, QFormLayout, QHeaderView, QAbstractItemView,
    QFileDialog, QMessageBox, QProgressBar, QMenu
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QPoint
from PyQt6.QtGui import QIcon
from datetime import datetime
from flask import Flask, send_from_directory, render_template_string, jsonify, abort, request, make_response
from werkzeug.serving import make_server
from werkzeug.utils import secure_filename

# --- Global base directory for resources ---
basedir = os.path.dirname(os.path.abspath(__file__))
icon_ico_path = os.path.join(basedir, 'icon.ico')
# For Flask route:
# The filename as it will appear in the URL and as it is on disk
icon_web_png_filename = 'iconweb.png'
# The directory where iconweb.png is located
icon_web_png_dir = basedir


# --- Utility Functions ---
def format_size(size_bytes):
    if not isinstance(size_bytes, (int, float)) or size_bytes < 0:
        return "N/A"
    if size_bytes == 0:
        return "0 B"
    size_name = ("B", "KiB", "MiB", "GiB", "TiB", "PiB", "EiB", "ZiB", "YiB")
    i = 0
    while size_bytes >= 1024 and i < len(size_name) - 1:
        size_bytes /= 1024.0
        i += 1
    return f"{size_bytes:.2f} {size_name[i]}"

def get_local_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    return ip

# --- Flask Server ---
flask_app = Flask(__name__)
flask_shared_items = []
qt_app_instance = None
UPLOAD_TEMP_DIR = tempfile.mkdtemp(prefix="EQS_uploads_")
incoming_files_buffer = {}

@flask_app.route(f'/{icon_web_png_filename}')
def serve_web_favicon():
    return send_from_directory(icon_web_png_dir, icon_web_png_filename, mimetype='image/png')

@flask_app.route('/')
def index():
    # SVG Icons (defined as Python strings for easy embedding)
    SVG_DOWNLOAD_ICON = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" style="vertical-align: middle; margin-right: 6px; width:18px; height:18px;"><path d="M12 15.586l-4.293-4.293a1 1 0 011.414-1.414L11 12.172V4a1 1 0 112 0v8.172l1.879-1.879a1 1 0 111.414 1.414L12 15.586zM5 18h14a1 1 0 110 2H5a1 1 0 110-2z"></path></svg>"""
    SVG_UPLOAD_BUTTON_ICON = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" style="vertical-align: middle; margin-right: 10px; width:20px; height:20px;"><path d="M11 15V9.414l-2.293 2.293a1 1 0 01-1.414-1.414l4-4a1 1 0 011.414 0l4 4a1 1 0 01-1.414 1.414L13 9.414V15a1 1 0 11-2 0zm-1 3H6.5A3.5 3.5 0 013 14.5V13a1 1 0 012 0v1.5A1.5 1.5 0 006.5 16H10a1 1 0 010 2zm10-2h-3.5A1.5 1.5 0 0015 14.5V13a1 1 0 112 0v1.5a3.5 3.5 0 01-3.5 3.5H13a1 1 0 010-2z"></path></svg>"""
    SVG_STATUS_UPLOADING_ICON = """<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="animate-spin" style="vertical-align: middle; margin-right: 8px;"><line x1="12" y1="2" x2="12" y2="6"></line><line x1="12" y1="18" x2="12" y2="22"></line><line x1="4.93" y1="4.93" x2="7.76" y2="7.76"></line><line x1="16.24" y1="16.24" x2="19.07" y2="19.07"></line><line x1="2" y1="12" x2="6" y2="12"></line><line x1="18" y1="12" x2="22" y2="12"></line><line x1="4.93" y1="19.07" x2="7.76" y2="16.24"></line><line x1="16.24" y1="7.76" x2="19.07" y2="4.93"></line></svg>"""
    SVG_STATUS_SUCCESS_ICON = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" width="20" height="20" style="vertical-align: middle; margin-right: 8px;"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm-2.07-5.83L16.59 7.5 18 8.91l-7.07 7.07-4.5-4.5 1.41-1.41z"></path></svg>"""
    SVG_STATUS_ERROR_ICON = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" width="20" height="20" style="vertical-align: middle; margin-right: 8px;"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm-1-13h2v6h-2zm0 8h2v2h-2z"></path></svg>"""

    upload_form_section = f"""
<style>
    body {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        background-color: #f4f7f6;
        color: #333;
        line-height: 1.6;
        margin: 0;
        padding: 20px;
    }}
    .EQS-container {{
        max-width: 800px;
        margin: 30px auto;
        padding: 30px 40px;
        background: #fff;
        border-radius: 12px;
        box-shadow: 0 8px 30px rgba(0,0,0,0.08);
    }}
    .EQS-heading {{
        text-align: center;
        font-size: 2.8em;
        font-weight: 700;
        color: #1a73e8; /* Google Blue */
        margin-bottom: 30px;
        letter-spacing: -0.5px;
    }}
    .section-title {{
        font-size: 1.6em;
        color: #202124;
        margin-top: 30px;
        margin-bottom: 15px;
        padding-bottom: 10px;
        border-bottom: 2px solid #e8eaed;
    }}
    .files-table {{
        width: 100%;
        border-collapse: collapse;
        margin-bottom: 30px;
        font-size: 0.95em;
    }}
    .files-table th, .files-table td {{
        padding: 14px 10px;
        text-align: left;
        border-bottom: 1px solid #dfe1e5;
    }}
    .files-table th {{
        background-color: #f1f3f4;
        color: #3c4043;
        font-weight: 600;
        letter-spacing: 0.3px;
    }}
    .files-table tr:last-child td {{
        border-bottom: none;
    }}
    .files-table tr:hover td {{
        background-color: #f8f9fa;
    }}
    .files-table a.download-link {{
        display: inline-flex;
        align-items: center;
        color: #1a73e8;
        text-decoration: none;
        font-weight: 500;
        padding: 6px 10px;
        border-radius: 5px;
        transition: background-color 0.2s ease, color 0.2s ease;
    }}
    .files-table a.download-link:hover {{
        background-color: #e8f0fe;
        color: #174ea6;
        text-decoration: none;
    }}
    /* SVG styling is mostly inline in this example, but you can add global svg rules here */

    .no-files-message {{
        color: #5f6368;
        margin-bottom: 25px;
        padding: 15px;
        background-color: #f8f9fa;
        border-radius: 8px;
        text-align: center;
    }}
    .upload-section {{
        margin-top: 30px;
        padding-top: 25px;
        border-top: 2px solid #e8eaed;
        text-align: center;
    }}
    #fileInput {{
        display: none; /* Hidden, triggered by label */
    }}
    .upload-button-container {{
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 10px;
        margin-bottom: 20px;
    }}
    .custom-upload-btn {{ /* This is the <label> acting as a button */
        display: inline-flex;
        align-items: center;
        background: linear-gradient(135deg, #1a73e8 0%, #1e88e5 100%);
        color: #fff;
        font-weight: 600;
        padding: 14px 30px;
        border: none;
        border-radius: 8px;
        cursor: pointer;
        font-size: 1.1em;
        transition: background 0.2s ease, box-shadow 0.2s ease;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }}
    .custom-upload-btn:hover {{
        background: linear-gradient(135deg, #1765cc 0%, #1a73e8 100%);
        box-shadow: 0 4px 8px rgba(0,0,0,0.15);
    }}
    #selectedFileName {{
        font-size: 0.95em;
        color: #5f6368;
        margin-top: 5px; /* Space from button if shown */
        font-style: italic;
        max-width: 100%;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        display: none; /* Initially hidden */
    }}
    .status-message {{
        margin-top: 20px;
        padding: 12px 18px;
        border-radius: 8px;
        font-size: 1.0em;
        font-weight: 500;
        display: flex; /* Use flex to align icon and text */
        align-items: center;
        justify-content: center; /* Center content if needed */
        gap: 8px; /* Space between icon and text */
        min-height: 2em;
        text-align: left; /* Align text to left within message box */
    }}
    .status-message.success {{
        background-color: #e6f4ea;
        color: #1e8e3e;
        border: 1px solid #a8d8b6;
    }}
    .status-message.error {{
        background-color: #fce8e6;
        color: #d93025;
        border: 1px solid #f5c1bc;
    }}
    .status-message.warning {{ /* For uploading */
        background-color: #fff8e1;
        color: #f9ab00;
        border: 1px solid #fde293;
    }}
    .hidden {{ display: none !important; }}

    @media (max-width: 700px) {{
        body {{ padding: 10px; }}
        .EQS-container {{
            padding: 20px;
            margin: 15px auto;
        }}
        .EQS-heading {{ font-size: 2.2em; }}
        .section-title {{ font-size: 1.4em; }}
        .files-table th, .files-table td {{ padding: 10px 8px; font-size: 0.9em; }}
        .custom-upload-btn {{ padding: 12px 22px; font-size: 1em; }}
        .status-message {{ padding: 10px 15px; font-size: 0.95em; }}
    }}
</style>
<div class="EQS-container">
    <div class="EQS-heading">Easy Quick Share</div>

    <h2 class="section-title">Available Files</h2>
    {('<table class="files-table">' +
     '<thead><tr><th>Name</th><th>Size</th><th>Action</th></tr></thead>' +
     '<tbody>' +
     "".join(
        f'<tr><td>{item["name"]}</td><td>{format_size(item["size_bytes"])}</td>' +
        f'<td><a href="/download/{idx}" class="download-link">{SVG_DOWNLOAD_ICON}Download</a></td></tr>'
        for idx, item in enumerate(flask_shared_items)
    ) + '</tbody></table>') if flask_shared_items else '<div class="no-files-message">No files are currently shared.</div>'}

    <div class="upload-section">
        <h2 class="section-title" style="border-bottom:none; margin-bottom:20px;">Upload a File</h2>
        <form id="uploadForm" method="post" enctype="multipart/form-data">
            <div class="upload-button-container">
                <label for="fileInput" class="custom-upload-btn">
                    {SVG_UPLOAD_BUTTON_ICON}
                    Choose File
                </label>
                <input type="file" name="file" id="fileInput" required onchange="updateSelectedFileNameAndSubmit()" />
                <span id="selectedFileName"></span>
            </div>
            <button type="submit" class="hidden"></button> <!-- Hidden submit, triggered by JS -->
        </form>
        <div id="statusMessage" class="status-message" style="display:none;"></div>
    </div>
    <script>
        const SVG_STATUS_UPLOADING_ICON_JS = `{SVG_STATUS_UPLOADING_ICON}`;
        const SVG_STATUS_SUCCESS_ICON_JS = `{SVG_STATUS_SUCCESS_ICON}`;
        const SVG_STATUS_ERROR_ICON_JS = `{SVG_STATUS_ERROR_ICON}`;

        function updateSelectedFileNameAndSubmit() {{
            var input = document.getElementById('fileInput');
            var span = document.getElementById('selectedFileName');
            
            if (input.files && input.files.length > 0) {{
                span.textContent = 'Selected: ' + input.files[0].name;
                span.style.display = 'block';
                // Trigger form submission automatically
                document.getElementById('uploadForm').dispatchEvent(new Event('submit', {{ bubbles: true, cancelable: true }}));
            }} else {{
                span.textContent = '';
                span.style.display = 'none';
            }}
        }}

        document.getElementById('uploadForm').addEventListener('submit', async function(e) {{
            e.preventDefault();
            const statusDiv = document.getElementById('statusMessage');
            const fileInput = document.getElementById('fileInput');
            const selectedFileNameSpan = document.getElementById('selectedFileName');

            statusDiv.textContent = ''; // Clear previous message content
            statusDiv.className = 'status-message'; // Reset classes
            statusDiv.style.display = 'none'; // Hide until new message is set

            if (!fileInput.files || fileInput.files.length === 0) {{
                statusDiv.innerHTML = SVG_STATUS_ERROR_ICON_JS + ' Please select a file to upload.';
                statusDiv.classList.add('error');
                statusDiv.style.display = 'flex';
                return;
            }}

            statusDiv.innerHTML = SVG_STATUS_UPLOADING_ICON_JS + ' Uploading...';
            statusDiv.classList.add('warning');
            statusDiv.style.display = 'flex';

            // Add spinner animation CSS if not already present
            const styleSheet = document.styleSheets[0];
            try {{
                let spinRuleExists = false;
                for (let i = 0; i < styleSheet.cssRules.length; i++) {{
                    if (styleSheet.cssRules[i].type === CSSRule.KEYFRAMES_RULE && styleSheet.cssRules[i].name === 'spin') {{
                        spinRuleExists = true;
                        break;
                    }}
                }}
                if (!spinRuleExists) {{
                    styleSheet.insertRule(`
                        @keyframes spin {{
                            0% {{ transform: rotate(0deg); }}
                            100% {{ transform: rotate(360deg); }}
                        }}`, styleSheet.cssRules.length);
                }}
                 // Apply animation to elements with class 'animate-spin'
                const spinners = statusDiv.querySelectorAll('.animate-spin');
                spinners.forEach(spinner => {{
                    spinner.style.animation = 'spin 1s linear infinite';
                }});

            }} catch (err) {{
                console.warn("Could not insert or apply spin animation: ", err);
            }}

            try {{
                const formData = new FormData(this);
                const response = await fetch('/upload', {{
                    method: 'POST',
                    body: formData,
                }});
                const data = await response.json();

                if (response.ok && data.message) {{ // response.ok checks for 2xx status
                    statusDiv.innerHTML = SVG_STATUS_SUCCESS_ICON_JS + ' Success: ' + data.message;
                    statusDiv.classList.remove('warning', 'error');
                    statusDiv.classList.add('success');
                }} else {{
                    let errorMessage = data.error || `Upload failed (HTTP ${'{response.status}'})`;
                    statusDiv.innerHTML = SVG_STATUS_ERROR_ICON_JS + ' Error: ' + errorMessage;
                    statusDiv.classList.remove('success', 'warning');
                    statusDiv.classList.add('error');
                }}
            }} catch (error) {{
                statusDiv.innerHTML = SVG_STATUS_ERROR_ICON_JS + ' Upload failed: Network error or server issue.';
                statusDiv.classList.remove('success', 'warning');
                statusDiv.classList.add('error');
                console.error('Error:', error);
            }} finally {{
                fileInput.value = ''; // Clear the file input
                selectedFileNameSpan.textContent = ''; // Clear the displayed file name
                selectedFileNameSpan.style.display = 'none'; // Hide the span

                // Optional: Auto-hide status message after a delay
                // setTimeout(() => {{
                // if (!statusDiv.classList.contains('warning')) {{ // Don't hide if it's an ongoing 'uploading' message
                // statusDiv.style.display = 'none';
                // }}
                // }}, 7000); // 7 seconds
            }}
        }});
    </script>
</div>
"""
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
    <meta charset="UTF-8">
    <title>EQS Instance</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="icon" type="image/png" href="/{icon_web_png_filename}">
    </head>
    <body>
        {upload_form_section if qt_app_instance and qt_app_instance.server_thread and qt_app_instance.server_thread.is_alive() else '<p style="color:red; text-align:center; font-size:1.2em; margin-top:50px;">Upload functionality is only available when the EQS server is running from the desktop application.</p>'}
    </body>
    </html>
    """
    return render_template_string(html_content)


@flask_app.route('/download/<int:file_id>')
def download_file(file_id):
    if 0 <= file_id < len(flask_shared_items):
        item = flask_shared_items[file_id]
        file_path = item['path']
        directory = os.path.dirname(file_path)
        filename = os.path.basename(file_path)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return send_from_directory(directory, filename, as_attachment=True)
        else:
            abort(404, description="File not found on server or is not a file.")
    else:
        abort(404, description="Invalid file ID.")

@flask_app.route('/upload', methods=['POST'])
def upload_file_route():
    if not (qt_app_instance and qt_app_instance.server_thread and qt_app_instance.server_thread.is_alive()):
        return make_response(jsonify(error="Server is not ready to accept uploads."), 503)
    if 'file' not in request.files:
        return make_response(jsonify(error="No file part in the request"), 400)
    file = request.files['file']
    if file.filename == '':
        return make_response(jsonify(error="No selected file"), 400)
    if file:
        original_filename = secure_filename(file.filename)
        # Create temp file in the UPLOAD_TEMP_DIR
        temp_file_id_base = tempfile.NamedTemporaryFile(delete=False, dir=UPLOAD_TEMP_DIR, prefix=f"{original_filename}_", suffix="")
        temp_file_path = temp_file_id_base.name
        temp_file_id_base.close() # Close the file handle so `file.save` can write to it
        try:
            file.save(temp_file_path)
            file_size = os.path.getsize(temp_file_path)
            sender_ip = request.remote_addr
            pending_id = os.path.basename(temp_file_path) # Use the unique temp filename as ID
            incoming_files_buffer[pending_id] = {
                'original_filename': original_filename,
                'temp_path': temp_file_path,
                'size': file_size,
                'sender_ip': sender_ip
            }
            # Signal the Qt app
            qt_app_instance.incoming_file_signal.emit(
                pending_id, original_filename, file_size, sender_ip
            )
            return make_response(jsonify(message=f"File '{original_filename}' received by server, awaiting user confirmation in EQS app."), 202)
        except Exception as e:
            if os.path.exists(temp_file_path): # Clean up if save failed
                os.remove(temp_file_path)
            return make_response(jsonify(error=f"Error saving file: {str(e)}"), 500)
    return make_response(jsonify(error="File processing error."), 500)


class ServerThread(threading.Thread):
    def __init__(self, app, host='0.0.0.0', port=8080):
        super().__init__(daemon=True)
        self.srv = make_server(host, port, app, threaded=True)
        self.host = host
        self.port = port
        self.app_context = app.app_context()

    def run(self):
        with self.app_context:
            print(f"Flask server starting on http://{self.host}:{self.port}")
            self.srv.serve_forever()

    def shutdown(self):
        print("Attempting to shut down Flask server...")
        self.srv.shutdown()

# --- Main Application Class ---
class EQSApp(QMainWindow):
    log_signal = pyqtSignal(str, str)
    incoming_file_signal = pyqtSignal(str, str, int, str)
    transfer_progress_signal = pyqtSignal(str, int, int)
    transfer_finished_signal = pyqtSignal(str, bool, str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("EQS")
        if os.path.exists(icon_ico_path):
            self.setWindowIcon(QIcon(icon_ico_path))
        else:
            print(f"Warning: Window icon file not found at {icon_ico_path}", file=sys.stderr)

        self.setGeometry(100, 100, 850, 650)
        global qt_app_instance
        qt_app_instance = self
        self.shared_items_data = []
        self.server_thread = None
        self.server_port = 8080
        self.default_receiving_folder = os.path.expanduser("~/Downloads")
        if not os.path.exists(self.default_receiving_folder):
            try:
                os.makedirs(self.default_receiving_folder, exist_ok=True)
            except OSError:
                self.default_receiving_folder = tempfile.gettempdir() # Fallback
                print(f"Warning: Could not create default Downloads folder. Using temp: {self.default_receiving_folder}")

        self.pending_transfers_ui = {}
        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)
        self._create_shared_files_tab()
        self._create_pending_receives_tab()
        self._create_logs_tab()
        self._create_settings_tab()
        self._connect_signals()
        # Connect signals defined in the class
        self.log_signal.connect(self._log_message_from_signal)
        self.incoming_file_signal.connect(self.handle_incoming_file_signal)
        self.transfer_progress_signal.connect(self.handle_transfer_progress)
        self.transfer_finished_signal.connect(self.handle_transfer_finished)
        self.le_receiving_folder.setText(self.default_receiving_folder)
        self.log_message("Application initialized.")

    def _create_shared_files_tab(self):
        self.shared_files_tab = QWidget()
        layout = QVBoxLayout(self.shared_files_tab)
        layout.setContentsMargins(10, 10, 10, 10)
        # Server Control Group
        server_control_group = QGroupBox("Server Control")
        server_control_layout = QVBoxLayout()
        server_buttons_layout = QHBoxLayout()
        self.btn_toggle_server = QPushButton("Start Server")
        self.btn_open_browser = QPushButton("Open in Browser")
        self.btn_open_browser.setEnabled(False)
        server_buttons_layout.addWidget(self.btn_toggle_server)
        server_buttons_layout.addWidget(self.btn_open_browser)
        server_buttons_layout.addStretch()
        server_info_layout = QFormLayout()
        server_info_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        self.lbl_status_value = QLabel("Stopped")
        self.lbl_status_value.setStyleSheet("color: red;")
        self.lbl_url_value = QLabel("N/A")
        self.lbl_url_value.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.lbl_url_value.setOpenExternalLinks(True)
        server_info_layout.addRow(QLabel("Status:"), self.lbl_status_value)
        server_info_layout.addRow(QLabel("URL:"), self.lbl_url_value)
        server_control_layout.addLayout(server_buttons_layout)
        server_control_layout.addLayout(server_info_layout)
        server_control_group.setLayout(server_control_layout)
        layout.addWidget(server_control_group)
        # Shared Files Group
        shared_files_group = QGroupBox("Shared Files")
        shared_files_group_layout = QVBoxLayout()
        shared_buttons_layout = QHBoxLayout()
        self.btn_add_files = QPushButton("Add Files")
        self.btn_add_folder = QPushButton("Add Folder")
        self.btn_remove_selected = QPushButton("Remove Selected")
        self.btn_clear_all_shared = QPushButton("Clear All")
        shared_buttons_layout.addWidget(self.btn_add_files)
        shared_buttons_layout.addWidget(self.btn_add_folder)
        shared_buttons_layout.addWidget(self.btn_remove_selected)
        shared_buttons_layout.addWidget(self.btn_clear_all_shared)
        shared_buttons_layout.addStretch()
        self.tbl_shared_files = QTableWidget()
        self.tbl_shared_files.setColumnCount(3)
        self.tbl_shared_files.setHorizontalHeaderLabels(["Name", "Size", "Path"])
        self.tbl_shared_files.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tbl_shared_files.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.tbl_shared_files.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tbl_shared_files.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tbl_shared_files.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl_shared_files.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        shared_files_group_layout.addLayout(shared_buttons_layout)
        shared_files_group_layout.addWidget(self.tbl_shared_files)
        shared_files_group.setLayout(shared_files_group_layout)
        layout.addWidget(shared_files_group)
        self.tab_widget.addTab(self.shared_files_tab, "Shared Files")

    def _create_pending_receives_tab(self):
        self.pending_receives_tab = QWidget()
        layout = QVBoxLayout(self.pending_receives_tab)
        layout.setContentsMargins(10, 10, 10, 10)
        instruction_label = QLabel("Review incoming receives. Right-click on an item to Accept or Reject.")
        layout.addWidget(instruction_label)
        self.tbl_pending_receives = QTableWidget()
        self.tbl_pending_receives.setColumnCount(4) # Filename, Status, Size, Received/Progress
        self.tbl_pending_receives.setHorizontalHeaderLabels(["Filename", "Status", "Size", "Received/Progress"])
        self.tbl_pending_receives.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tbl_pending_receives.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.tbl_pending_receives.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.tbl_pending_receives.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.tbl_pending_receives.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tbl_pending_receives.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl_pending_receives.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tbl_pending_receives.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tbl_pending_receives.customContextMenuRequested.connect(self.show_pending_receive_context_menu)
        layout.addWidget(self.tbl_pending_receives)
        self.tab_widget.addTab(self.pending_receives_tab, "Pending Receives")

    def _create_logs_tab(self):
        self.logs_tab = QWidget()
        layout = QVBoxLayout(self.logs_tab)
        layout.setContentsMargins(10, 10, 10, 10)
        self.txt_logs = QTextEdit()
        self.txt_logs.setReadOnly(True)
        layout.addWidget(self.txt_logs)
        # Log controls
        bottom_layout = QHBoxLayout()
        bottom_layout.addWidget(QLabel("Log Level:"))
        self.cmb_log_level = QComboBox()
        self.cmb_log_level.addItems(["NOTSET", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self.cmb_log_level.setCurrentText("INFO") # Default log level
        bottom_layout.addWidget(self.cmb_log_level)
        bottom_layout.addStretch()
        self.btn_clear_logs = QPushButton("Clear Logs")
        bottom_layout.addWidget(self.btn_clear_logs)
        layout.addLayout(bottom_layout)
        self.tab_widget.addTab(self.logs_tab, "Logs")

    def _create_settings_tab(self):
        self.settings_tab = QWidget()
        main_layout = QVBoxLayout(self.settings_tab)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop) # Align group boxes to top
        settings_group = QGroupBox("General Settings")
        form_layout = QFormLayout()
        # Receiving Folder
        self.le_receiving_folder = QLineEdit()
        self.le_receiving_folder.setPlaceholderText(f"Default: {os.path.expanduser('~/Downloads')}")
        self.btn_browse_recv_folder = QPushButton("Browse...")
        recv_folder_layout = QHBoxLayout()
        recv_folder_layout.addWidget(self.le_receiving_folder)
        recv_folder_layout.addWidget(self.btn_browse_recv_folder)
        form_layout.addRow(QLabel("Receiving Folder:"), recv_folder_layout)
        settings_group.setLayout(form_layout)
        main_layout.addWidget(settings_group)
        self.tab_widget.addTab(self.settings_tab, "Settings")
        # Initialize with default
        self.le_receiving_folder.setText(self.default_receiving_folder)

    def _connect_signals(self):
        self.btn_add_files.clicked.connect(self.add_files_action)
        self.btn_add_folder.clicked.connect(self.add_folder_action)
        self.btn_remove_selected.clicked.connect(self.remove_selected_shared_files_action)
        self.btn_clear_all_shared.clicked.connect(self.clear_all_shared_files_action)
        self.btn_toggle_server.clicked.connect(self.toggle_server_action)
        self.btn_open_browser.clicked.connect(self.open_browser_action)
        self.btn_clear_logs.clicked.connect(self.clear_logs_action)
        self.cmb_log_level.currentTextChanged.connect(self.placeholder_action_text) # Placeholder for log level change
        self.btn_browse_recv_folder.clicked.connect(self.browse_receiving_folder_action)

    def _log_message_from_signal(self, message, level):
        """Slot to handle log messages emitted from other threads."""
        self.log_message(message, level)

    def log_message(self, message, level="INFO"):
        # Ensure logging happens on the main thread if called from another thread
        if threading.current_thread() != threading.main_thread():
            self.log_signal.emit(message, level)
            return

        # Basic filtering based on combobox (can be made more sophisticated)
        log_levels = {"NOTSET": 0, "DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}
        current_log_setting = self.cmb_log_level.currentText()
        if log_levels.get(level.upper(), 0) < log_levels.get(current_log_setting, 20):
            return

        timestamp = datetime.now().strftime("%H:%M:%S")
        self.txt_logs.append(f"[{timestamp}] {level}: {message}")
        self.txt_logs.verticalScrollBar().setValue(self.txt_logs.verticalScrollBar().maximum())


    def placeholder_action_text(self, text):
        sender = self.sender()
        if isinstance(sender, QComboBox): # Example, could be more specific
            self.log_message(f"Action: Log Level ComboBox changed to '{text}'.")
        # else:
        #     self.log_message(f"Action triggered by: {sender}, Text: '{text}'")

    def handle_incoming_file_signal(self, pending_id, filename, size, sender_ip):
        self.log_message(f"Incoming file '{filename}' ({format_size(size)}) from {sender_ip}. Pending ID: {pending_id}", level="INFO")
        row_position = self.tbl_pending_receives.rowCount()
        self.tbl_pending_receives.insertRow(row_position)

        filename_item = QTableWidgetItem(filename)
        filename_item.setData(Qt.ItemDataRole.UserRole, pending_id) # Store pending_id with the item
        status_item = QTableWidgetItem("Pending Confirmation")
        size_item = QTableWidgetItem(format_size(size))
        progress_bar = QProgressBar()
        progress_bar.setValue(0)
        progress_bar.setTextVisible(True)
        progress_bar.setFormat("0%")

        self.tbl_pending_receives.setItem(row_position, 0, filename_item)
        self.tbl_pending_receives.setItem(row_position, 1, status_item)
        self.tbl_pending_receives.setItem(row_position, 2, size_item)
        self.tbl_pending_receives.setCellWidget(row_position, 3, progress_bar)

        self.pending_transfers_ui[pending_id] = {
            'row': row_position, 'status_item': status_item,
            'progress_bar': progress_bar, 'filename_item': filename_item
        }
        # Notify user by changing tab text if not active
        if self.tab_widget.currentWidget() != self.pending_receives_tab:
            pending_tab_index = self.tab_widget.indexOf(self.pending_receives_tab)
            self.tab_widget.setTabText(pending_tab_index, f"Pending Receives ({self.tbl_pending_receives.rowCount()})*")


    def handle_transfer_progress(self, pending_id, current_bytes, total_bytes):
        if pending_id in self.pending_transfers_ui:
            ui = self.pending_transfers_ui[pending_id]
            if total_bytes > 0:
                percentage = int((current_bytes / total_bytes) * 100)
                ui['progress_bar'].setValue(percentage)
                ui['progress_bar'].setFormat(f"{percentage}% ({format_size(current_bytes)}/{format_size(total_bytes)})")
            ui['status_item'].setText("Downloading...")


    def handle_transfer_finished(self, pending_id, success, message_or_path):
        if pending_id in self.pending_transfers_ui:
            ui = self.pending_transfers_ui[pending_id]
            if success:
                ui['status_item'].setText("Completed")
                ui['progress_bar'].setValue(100)
                ui['progress_bar'].setFormat(f"Completed: {os.path.basename(message_or_path)}")
                self.log_message(f"File '{ui['filename_item'].text()}' received. Saved to: {message_or_path}", level="INFO")
            else:
                ui['status_item'].setText(f"Failed")
                ui['progress_bar'].setFormat(f"Failed: {message_or_path}")
                self.log_message(f"Failed to receive '{ui['filename_item'].text()}': {message_or_path}", level="ERROR")

            # Clean up the temporary file from incoming_files_buffer if it still exists
            if pending_id in incoming_files_buffer:
                temp_file_info = incoming_files_buffer.pop(pending_id, None)
                if temp_file_info and os.path.exists(temp_file_info['temp_path']):
                    try:
                        os.remove(temp_file_info['temp_path'])
                        self.log_message(f"Cleaned temp file {temp_file_info['temp_path']} for {pending_id}", level="DEBUG")
                    except OSError as e:
                        self.log_message(f"Error removing temp file {temp_file_info['temp_path']}: {e}", level="WARNING")
            
            # Update tab text if no more items are "Pending Confirmation"
            active_pending_count = 0
            for r_idx in range(self.tbl_pending_receives.rowCount()):
                status_cell_item = self.tbl_pending_receives.item(r_idx, 1)
                if status_cell_item and status_cell_item.text() == "Pending Confirmation":
                    active_pending_count += 1
            
            pending_tab_idx = self.tab_widget.indexOf(self.pending_receives_tab)
            if active_pending_count > 0:
                self.tab_widget.setTabText(pending_tab_idx, f"Pending Receives ({active_pending_count})*")
            else:
                self.tab_widget.setTabText(pending_tab_idx, "Pending Receives")


    def show_pending_receive_context_menu(self, position: QPoint):
        selected_items = self.tbl_pending_receives.selectedItems()
        if not selected_items:
            return

        row = selected_items[0].row() # Get row from the first selected item
        filename_item = self.tbl_pending_receives.item(row, 0)
        status_item = self.tbl_pending_receives.item(row, 1) # Status is in column 1

        if not filename_item or not status_item: return # Should not happen

        pending_id = filename_item.data(Qt.ItemDataRole.UserRole)

        if not pending_id or status_item.text() != "Pending Confirmation":
            # Don't show menu if not in a state to be actioned or ID missing
            return

        menu = QMenu()
        accept_action = menu.addAction("Accept File")
        reject_action = menu.addAction("Reject File")

        action = menu.exec(self.tbl_pending_receives.mapToGlobal(position))

        if action == accept_action:
            self.accept_file_action(pending_id, row)
        elif action == reject_action:
            self.reject_file_action(pending_id, row)

    def accept_file_action(self, pending_id, row):
        if pending_id not in incoming_files_buffer:
            self.log_message(f"No data for pending ID {pending_id} to accept.", level="ERROR")
            if pending_id in self.pending_transfers_ui:
                self.pending_transfers_ui[pending_id]['status_item'].setText("Error: Data lost")
            return

        pending_info = incoming_files_buffer[pending_id]
        original_filename = pending_info['original_filename']
        temp_path = pending_info['temp_path']

        save_dir = self.le_receiving_folder.text()
        if not os.path.isdir(save_dir): # Fallback if dir is invalid
            save_dir = self.default_receiving_folder
            self.le_receiving_folder.setText(save_dir) # Update UI
        os.makedirs(save_dir, exist_ok=True) # Ensure it exists

        suggested_path = os.path.join(save_dir, original_filename)

        final_save_path, _ = QFileDialog.getSaveFileName(
            self, "Save Incoming File As...", suggested_path, f"Files (*{os.path.splitext(original_filename)[1] if '.' in original_filename else '.*'});;All Files (*.*)"
        )

        if final_save_path:
            self.log_message(f"Accepting '{original_filename}' to '{final_save_path}'", level="INFO")
            if pending_id in self.pending_transfers_ui:
                 self.pending_transfers_ui[pending_id]['status_item'].setText("Accepted. Saving...")
            # Start the file move in a separate thread to keep UI responsive
            threading.Thread(target=self._process_accepted_file, args=(pending_id, temp_path, final_save_path), daemon=True).start()
        else:
            self.log_message(f"Acceptance of '{original_filename}' cancelled by user.", level="INFO")
            # Status remains "Pending Confirmation"

    def _process_accepted_file(self, pending_id, temp_path, final_save_path):
        try:
            total_size = os.path.getsize(temp_path)
            # Initial progress update
            self.transfer_progress_signal.emit(pending_id, 0, total_size)

            # Simulate chunky copy for progress bar visibility (optional for small files)
            # For large files, shutil.move might be quick if on same filesystem,
            # otherwise it's a copy then delete.
            # A more robust progress would involve chunked reading/writing.
            # Here, we just signal start and end.
            
            shutil.move(temp_path, final_save_path) # This is the actual move/copy

            # Final progress update
            self.transfer_progress_signal.emit(pending_id, total_size, total_size)
            self.transfer_finished_signal.emit(pending_id, True, final_save_path)
        except Exception as e:
            self.log_message(f"Error processing accepted file {pending_id}: {e}", level="ERROR")
            self.transfer_finished_signal.emit(pending_id, False, str(e))
            # Ensure temp file is removed if move failed but file still exists at temp_path
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass # Logged by finished handler already if needed

    def reject_file_action(self, pending_id, row):
        original_filename = "Unknown file"
        if pending_id in self.pending_transfers_ui:
            original_filename = self.pending_transfers_ui[pending_id]['filename_item'].text()

        if pending_id in incoming_files_buffer:
            temp_info = incoming_files_buffer.pop(pending_id) # Remove from buffer
            try:
                if os.path.exists(temp_info['temp_path']):
                    os.remove(temp_info['temp_path'])
                self.log_message(f"Rejected and deleted temp file for '{original_filename}' (ID: {pending_id})", level="INFO")
            except OSError as e:
                self.log_message(f"Error deleting temp file {temp_info['temp_path']} on reject: {e}", level="WARNING")
        else:
            self.log_message(f"No temp data found for ID {pending_id} to reject. File might have been processed or data lost.", level="WARNING")

        if pending_id in self.pending_transfers_ui:
            self.pending_transfers_ui[pending_id]['status_item'].setText("Rejected by User")
            self.pending_transfers_ui[pending_id]['progress_bar'].setFormat("Rejected")
            # Use transfer_finished to potentially clear the entry or mark as fully processed
        self.transfer_finished_signal.emit(pending_id, False, "Rejected by user")


    def _update_flask_shared_items(self):
        global flask_shared_items
        flask_shared_items.clear()
        for idx, item_data in enumerate(self.shared_items_data):
            flask_shared_items.append({
                'id': idx, # Flask will use this for download URL
                'name': item_data['name'],
                'size_bytes': item_data['size_bytes'],
                'path': item_data['path']
            })

    def _add_item_to_shared_table(self, file_name, file_size_bytes, file_path):
        # Check for duplicates
        if any(item['path'] == file_path for item in self.shared_items_data):
            self.log_message(f"File already shared: {file_path}", level="WARNING")
            return False # Indicate that the file was not added

        self.shared_items_data.append({'name': file_name, 'size_bytes': file_size_bytes, 'path': file_path})
        self._update_flask_shared_items() # Update Flask's list

        row_position = self.tbl_shared_files.rowCount()
        self.tbl_shared_files.insertRow(row_position)
        self.tbl_shared_files.setItem(row_position, 0, QTableWidgetItem(file_name))
        self.tbl_shared_files.setItem(row_position, 1, QTableWidgetItem(format_size(file_size_bytes)))
        self.tbl_shared_files.setItem(row_position, 2, QTableWidgetItem(file_path))
        return True # Indicate success


    def add_files_action(self):
        file_paths, _ = QFileDialog.getOpenFileNames(self, "Select Files to Share", "", "All Files (*.*)")
        if file_paths:
            added_count = 0
            for file_path in file_paths:
                if os.path.isfile(file_path):
                    file_name = os.path.basename(file_path)
                    file_size_bytes = os.path.getsize(file_path)
                    if self._add_item_to_shared_table(file_name, file_size_bytes, file_path):
                        added_count +=1
            if added_count > 0:
                self.log_message(f"Added {added_count} file(s) to shared list.")
            else:
                self.log_message("No new files were added (perhaps duplicates or invalid selections).")


    def add_folder_action(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder to Share Files From", "")
        if folder_path:
            added_count = 0
            for item_name in os.listdir(folder_path):
                full_item_path = os.path.join(folder_path, item_name)
                if os.path.isfile(full_item_path): # Only add files, not sub-folders
                    file_size_bytes = os.path.getsize(full_item_path)
                    if self._add_item_to_shared_table(item_name, file_size_bytes, full_item_path):
                        added_count += 1
            if added_count > 0:
                self.log_message(f"Added {added_count} file(s) from folder '{os.path.basename(folder_path)}'.")
            else:
                self.log_message(f"No new files from folder '{os.path.basename(folder_path)}' were added (perhaps duplicates or folder is empty/contains no files).")

    def remove_selected_shared_files_action(self):
        selected_rows = sorted(list(set(index.row() for index in self.tbl_shared_files.selectedIndexes())), reverse=True)
        if not selected_rows:
            self.log_message("No files selected to remove.", level="WARNING")
            return

        removed_count = 0
        for row_index in selected_rows:
            path_item = self.tbl_shared_files.item(row_index, 2) # Path is in the 3rd column (index 2)
            if path_item:
                removed_path = path_item.text()
                # Remove from internal data store
                self.shared_items_data = [item for item in self.shared_items_data if item['path'] != removed_path]
                self.tbl_shared_files.removeRow(row_index)
                removed_count +=1

        if removed_count > 0:
            self.log_message(f"Removed {removed_count} file(s) from shared list.")
            self._update_flask_shared_items() # Update Flask's list


    def clear_all_shared_files_action(self):
        if not self.shared_items_data:
            self.log_message("Shared files list is already empty.", level="INFO")
            return

        reply = QMessageBox.question(self, "Confirm Clear", "Are you sure you want to remove all shared files?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.tbl_shared_files.setRowCount(0) # Clear table
            self.shared_items_data.clear()      # Clear internal data
            self._update_flask_shared_items()   # Update Flask's list
            self.log_message("Cleared all shared files.")

    def toggle_server_action(self):
        if self.server_thread and self.server_thread.is_alive():
            self.stop_server()
        else:
            self.start_server()

    def start_server(self):
        if self.server_thread and self.server_thread.is_alive():
            self.log_message("Server is already running.", level="WARNING")
            return
        try:
            host_ip = get_local_ip()
            self._update_flask_shared_items() # Ensure Flask has the current list
            self.server_thread = ServerThread(flask_app, host=host_ip, port=self.server_port)
            self.server_thread.start()

            self.lbl_status_value.setText("Running")
            self.lbl_status_value.setStyleSheet("color: green;")
            url = f"http://{host_ip}:{self.server_port}"
            self.lbl_url_value.setText(f"<a href='{url}'>{url}</a>")
            self.btn_toggle_server.setText("Stop Server")
            self.btn_open_browser.setEnabled(True)
            self.log_message(f"Server started. Listening on {url}")
            self.log_message(f"Upload endpoint available at POST {url}/upload", level="DEBUG")

        except Exception as e:
            self.log_message(f"Failed to start server: {e}", level="ERROR")
            QMessageBox.critical(self, "Server Start Error", f"Could not start the server: {e}")
            self.lbl_status_value.setText("Error")
            self.lbl_status_value.setStyleSheet("color: red;")
            self.lbl_url_value.setText("N/A")
            self.btn_toggle_server.setText("Start Server")
            self.btn_open_browser.setEnabled(False)


    def stop_server(self):
        if self.server_thread and self.server_thread.is_alive():
            try:
                self.log_message("Stopping server...", level="INFO")
                self.server_thread.shutdown()
                self.server_thread.join(timeout=5) # Wait for thread to finish
                if self.server_thread.is_alive():
                    self.log_message("Server thread did not stop gracefully. It might take a moment.", level="WARNING")
                    # Further action might be needed if it's truly stuck
                else:
                    self.log_message("Server stopped successfully.", level="INFO")
            except Exception as e:
                self.log_message(f"Error stopping server: {e}", level="ERROR")
            finally:
                self.server_thread = None # Clear the reference
                self.lbl_status_value.setText("Stopped")
                self.lbl_status_value.setStyleSheet("color: red;")
                self.lbl_url_value.setText("N/A")
                self.btn_toggle_server.setText("Start Server")
                self.btn_open_browser.setEnabled(False)
        else:
            self.log_message("Server is not running.", level="WARNING")


    def open_browser_action(self):
        if self.server_thread and self.server_thread.is_alive():
            url = f"http://{self.server_thread.host}:{self.server_thread.port}"
            try:
                webbrowser.open(url)
                self.log_message(f"Opened '{url}' in browser.")
            except Exception as e:
                self.log_message(f"Failed to open browser: {e}", level="ERROR")
                QMessageBox.warning(self, "Browser Error", f"Could not open URL: {e}")
        else:
            self.log_message("Cannot open in browser: Server not running.", level="WARNING")


    def clear_logs_action(self):
        self.txt_logs.clear()

    def browse_receiving_folder_action(self):
        current_path = self.le_receiving_folder.text()
        if not current_path or not os.path.isdir(current_path):
            current_path = self.default_receiving_folder # Use default if current is invalid

        folder_path = QFileDialog.getExistingDirectory(self, "Select Default Receiving Folder", current_path)
        if folder_path: # If user selected a folder
            self.le_receiving_folder.setText(folder_path)
            self.default_receiving_folder = folder_path # Update the actual default
            self.log_message(f"Default receiving folder set to: {folder_path}")


    def closeEvent(self, event):
        self.log_message("Application closing. Attempting to stop server if running...")
        self.stop_server()
        # Cleanup UPLOAD_TEMP_DIR
        try:
            if os.path.exists(UPLOAD_TEMP_DIR):
                shutil.rmtree(UPLOAD_TEMP_DIR)
                self.log_message(f"Cleaned up temporary upload directory: {UPLOAD_TEMP_DIR}", level="DEBUG")
        except Exception as e:
            self.log_message(f"Error cleaning up temp directory {UPLOAD_TEMP_DIR}: {e}", level="WARNING")
        event.accept()

if __name__ == "__main__":
    # Ensure UPLOAD_TEMP_DIR exists (though mkdtemp should create it)
    if not os.path.exists(UPLOAD_TEMP_DIR):
        os.makedirs(UPLOAD_TEMP_DIR, exist_ok=True)

    app = QApplication(sys.argv)
    if os.path.exists(icon_ico_path):
        app.setWindowIcon(QIcon(icon_ico_path))
    else:
        print(f"Warning: Application icon file not found at {icon_ico_path}", file=sys.stderr)
        
    # Apply a basic style if desired (optional)
    # app.setStyle("Fusion")
    main_window = EQSApp()
    main_window.show()
    sys.exit(app.exec())