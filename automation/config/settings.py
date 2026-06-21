"""Application-wide configuration constants. Edit here to affect the whole app."""

# ── Window ────────────────────────────────────────────────────────────────────
APP_TITLE = "FLEX Tester Controller"
APP_GEOMETRY = "1000x700"

# ── Filesystem ────────────────────────────────────────────────────────────────
LOGS_DIR_NAME = "FLEX_LOGS"

# ── Serial ────────────────────────────────────────────────────────────────────
BAUD_RATES = ["9600", "115200", "57600"]
DEFAULT_BAUD_INDEX = 1          # 115200

LINE_ENDINGS = ["\\r\\n", "\\n", "\\r"]
DEFAULT_LINE_END_INDEX = 1      # \n

LINE_ENDING_MAP: dict[str, str] = {
    "\\r\\n": "\r\n",
    "\\n":    "\n",
    "\\r":    "\r",
}

# ── Water Meters ─────────────────────────────────────────────────────────────
WM_COUNT = 5
WM_COLORS: dict[int, str] = {1: "blue", 2: "red", 3: "green", 4: "darkorange", 5: "purple"}
WM_OFFSETS: dict[int, float] = {1: 0.0, 2: 1.5, 3: 3.0, 4: 4.5, 5: 6.0}
WM_GRAPH_WINDOW_SECONDS = 120   # rolling window kept in memory
WM_GRAPH_POST_STOP_SECONDS = 10 # keep refreshing N seconds after all WMs stop
WM_GRAPH_REFRESH_MS = 400

# ── Pinout mapping (Tab 1 right panel) ───────────────────────────────────────
PINOUT_DATA: list[tuple[str, str, str]] = [
    ("Valve 1",  "PB0",  "Input (Button B1)"),
    ("Valve 2",  "PB1",  "Input"),
    ("Valve 3",  "PB2",  "Input"),
    ("Valve 4",  "PB10", "Input"),
    ("Valve 5",  "PB11", "Input"),
    ("Valve 6",  "PB12", "Input"),
    ("Valve 7",  "PB13", "Input"),
    ("Valve 8",  "PB14", "Input"),
    ("Valve 9",  "PB15", "Input"),
    ("Valve 10", "PC6",  "Input"),
    ("Valve 11", "PC7",  "Input"),
    ("Valve 12", "PC8",  "Input"),
    ("Valve 13", "PC9",  "Input"),
    ("Valve 14", "PA8",  "Input"),
    ("Valve 15", "PA9",  "Input"),
    ("Valve 16", "PA10", "Input"),
    ("",         "",     ""),
    ("WM 1",     "PA5",  "Output (LED LD2)"),
    ("WM 2",     "PC1",  "Output"),
    ("WM 3",     "PC2",  "Output"),
    ("WM 4",     "PC3",  "Output"),
    ("WM 5",     "PC4",  "Output"),
    ("",         "",     ""),
    ("DAC 1",    "PA4",  "Analog Output 0-3.3V"),
]

# ── CLI command categories (Tab 2 command builder) ────────────────────────────
CLI_COMMANDS: dict[str, list[str]] = {
    "Tab": [], "?": [], "Device": ["Info", "Reset"], "Flash": ["Test", "SwitchBank"],
    "RTC": ["Time", "Date"], "OS": ["Info"], "ADC": ["Get", "Test", "Enable"],
    "CRC": ["Calc32", "Calc16"], "AI": ["Info", "Config", "Enable", "Read", "Reset"],
    "AS": ["dump"], "PR": ["set", "setbits", "get"],
    "DI": ["Info", "Config", "Enable", "Feed", "PinIrq", "Reset", "Count", "Get",
           "PinGet", "RstCnt", "Test"],
    "wm":  ["status", "debug"],
    "DO":  ["Info", "Config", "Enable", "Open", "Close", "Reset"],
    "DFM": ["Enable"],
    "BLE": ["Info", "Enable", "SendMsg", "GetMsg", "SendMacCmd", "GetMac"],
    "SDI": ["Info", "Config", "SendCmd", "GetData", "Reset"],
    "Temp": ["Init", "Read"], "GPIO": ["Enable", "Get"], "RSW": ["Get"],
    "Cell": ["Info", "Enable", "SendMsg", "Get", "SendHex"],
    "SDCARD": ["Info", "Enable", "Mount", "UnMount", "Format", "CreateDir",
               "CreateFile", "DeleteFile", "UpdateFile", "ReadFile", "CloseFile",
               "RenameFile", "ReadString", "CheckSpace", "Scan", "PrintFile", "GetFileSize"],
    "FOTA":    ["SdCard", "BleTx", "Test"],
    "RS485":   ["Info", "Enable", "SendMsg", "SendHexMsg", "GetMsg"],
    "FlashOB": ["Set"],
    "IrrProg": ["Info", "Config", "Reset", "FlashSave"],
    "Shift":   ["Info", "Config", "Reset"],
    "Recipe":  ["Info", "Config", "Reset", "FlashSave"],
    "IrrGen":  ["Info", "Config", "Reset", "FlashSave"],
    "IrrAlarm":["Info", "Config", "Reset", "FlashSave"],
    "IrrDOMap":["Info", "Config", "Reset", "FlashSave"],
    "IrrDIMap":["Info", "Config", "Reset", "FlashSave"],
    "IrrAIMap":["Info", "Config", "Reset", "FlashSave"],
    "IrrQueue":["Test", "Print", "Clear", "FlashGet", "FlashSave", "FlashReset"],
    "IrrDO":   ["Open", "Close"],
    "IrrRep":  ["Print"],
    "IrrCmd":  ["Set", "Get"],
    "Uncomplt":["FlashGet", "FlashSave", "FlashErase"],
    "IrrMngr": ["FlashGet", "FlashSave", "FlashReset"],
    "MQUncmp": ["FlashSave"],
    "Log":     ["Write", "Read", "ReadArr", "GetSize", "Print", "Erase", "Test"],
    "KA":      ["Send", "Irr", "Alert", "Scheme", "Recipes", "Settings", "IOConfig"],
}

# ── System initialisation command sequence (Tab 2) ────────────────────────────
INIT_COMMANDS: list[str] = [
    "do reset", "di reset", "ai reset", "do config", "di config",
    "di pinirq 0 1 1", "irrdomap reset", "irrdomap config", "irrdomap flashsave",
    "irrdimap reset", "irrdimap config", "irrdimap flashsave",
]
INIT_COMMAND_DELAY_S = 0.5
