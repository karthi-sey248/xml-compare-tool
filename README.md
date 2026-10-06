# XML Compare Tool

A tool for comparing two XML files (Before & After), identifying changes, and displaying them clearly.

The tool has two parts:

1. **`index.html`** — A browser-based side-by-side visual diff viewer (Left = Before, Right = After). Changes are highlighted, and clicking a change displays a popup with details.
2. **`xml_compare_to_excel.py`** — A Python script that generates a detailed Excel report (S.No, line number, attribute/text-level changes) and annotated XML copies.

No installation is required for the HTML viewer — no additional libraries or server are required for basic usage.

---

## 1. Browser Viewer (`index.html`) — Local Deployment

### New: Download Excel Report

The `index.html` now includes a **"Download Excel Report"** button.

Once both XML files are uploaded, the Excel download option becomes available. You can click the button to directly download an Excel (`.xlsx`) report from the browser.

The generated Excel report uses the **same detailed element/attribute-level comparison logic** as the `xml_compare_to_excel.py` script:

* S.No
* Before Line No
* After Line No
* XML Path
* Change Type
* Before Value
* After Value

Both comparison engines use the same logic, implemented separately in Python and JavaScript. They have been tested and verified to produce the same results.

### Option A — Open Directly

If you only want to use the tool on your local system:

1. Double-click the `index.html` file.
2. It will open in your default browser.
3. Upload the Before and After XML files.
4. Click **Compare**.

No server is required.

---

### Option B — Run as a Local Server

If you want other computers on the same network to access the tool, you can run your computer as a small web server.

For example, other systems on the same network can access the tool using:

```text
http://<your-IP>:8000
```

#### Step 1 — Find Your Computer's IP Address

**Windows:**

```bash
ipconfig
```

Look for the **IPv4 Address**, for example:

```text
192.168.1.25
```

**Mac / Linux:**

```bash
ifconfig
```

or:

```bash
ip addr
```

#### Step 2 — Navigate to the Project Folder

Open Command Prompt or Terminal and navigate to the project folder:

```bash
cd xml-compare-tool
```

Then start the Python HTTP server:

```bash
python3 -m http.server 8000
```

On Windows, you can also use:

```bash
python -m http.server 8000
```

Keep the terminal window open while the server is running. Closing the terminal will stop the server.

#### Step 3 — Access from Another System

On another computer connected to the same network, open a browser and enter:

```text
http://<your-computer-IP>:8000/index.html
```

Example:

```text
http://192.168.1.25:8000/index.html
```

### Notes

* Both computers must be connected to the **same network/Wi-Fi** (office LAN or the same router).
* If Windows Firewall is enabled, you may need to allow Python or port `8000` through the firewall.
* When prompted by Windows Firewall, allow access on the **Private Network** if this is an internal office network.
* If you want the server to run continuously, you can configure it as a background service.
* On Linux/Mac, you can use:

```bash
nohup python3 -m http.server 8000 &
```

* On Windows, you can use **Task Scheduler**, **NSSM**, or another service-management tool to run the server in the background.
* This approach is suitable for small teams and internal office use.
* For company-wide or permanent deployment, the tool can be hosted on an internal web server such as **IIS, Nginx, or Apache**.

---

### Option C — Deploy on a Company Server / Intranet

The `index.html` file can be deployed to any static file hosting environment, such as:

* Nginx
* Apache
* IIS
* SharePoint
* S3 / Static Hosting
* Internal company web server

The tool is completely client-side, so it does **not require**:

* Backend server
* Database
* API

Simply copy the `index.html` file and the required supporting files to the static hosting location.

---

# 2. Python Excel Report Script (`xml_compare_to_excel.py`)

## Requirements

* Python 3.8+
* `openpyxl` library

Install the required library using:

```bash
pip install openpyxl
```

## How to Run

Open the `xml_compare_to_excel.py` script and update the file paths in the **INPUT / OUTPUT SETTINGS** section:

```python
BEFORE_XML_PATH = "path/to/before.xml"
AFTER_XML_PATH  = "path/to/after.xml"
OUTPUT_EXCEL_PATH = "path/to/output_report.xlsx"
```

Then run the script:

```bash
python3 xml_compare_to_excel.py
```

On Windows, you can also use:

```bash
python xml_compare_to_excel.py
```

## Output

The script generates:

### Excel Report (`.xlsx`)

The report contains:

* S.No
* Before Line No
* After Line No
* XML Path
* Change Type
* Before Value
* After Value

### Annotated XML Copies

Annotated copies of the Before and After XML files are also generated.

For each detected change, a comment is added above the corresponding XML line in the following format:

```xml
<!-- >>> CHANGE #S.No ... -->
```

This makes it easy to identify exactly where each change occurred.

---

# Folder Structure

```text
xml-compare-tool/
├── index.html                 # Browser-based visual diff viewer
├── xml_compare_to_excel.py    # Python Excel report generator
└── README.md                  # Documentation
```

---

# Notes

* The `index.html` viewer does **not require an internet connection** for the XML comparison because the comparison is performed entirely on the client side.
* However, the **Excel Download** feature uses the SheetJS library loaded from `cdnjs.cloudflare.com`. Therefore, internet or network access is required for that specific feature if the library is not bundled locally.
* If your office network provides internet access, the Excel download feature will work normally.
* The XML files are processed in the browser and are **not uploaded to the server**.
* Even when the HTML tool is hosted on a local server, the XML comparison processing takes place entirely inside the user's browser.
* The two tools can be used independently or together:

  * Use `index.html` for visual comparison and quick Excel report generation.
  * Use `xml_compare_to_excel.py` when you need the Python-based detailed Excel report and annotated XML files.
