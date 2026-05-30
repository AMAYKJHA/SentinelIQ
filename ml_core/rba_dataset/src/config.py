RAW_DATA_PATH = "data/raw/rba-dataset.csv"
SAMPLED_DATA_DIR = "data/samples"
MODEL_DIR = "models"
REPORT_DIR = "reports"

PHASE1_SAMPLE_SIZE = 100_000
PHASE2_SAMPLE_SIZE = 400_000  # change within 300K–500K

RANDOM_STATE = 42

# Adjust these to your actual column names
INDEX_COL = "index"
USER_COL = "User ID"
TIME_COL = "Login Timestamp"
ATTACK_COL = "Is Attack IP"
SUCCESS_COL = "Login Successful"
DEVICE_COL = "Device Type"
IP_COL = "IP Address"
COUNTRY_COL = "Country"
REGION_COL = "Region"
CITY_COL = "City"
ASN_COL = "ASN"
USER_AGENT_COL = "User Agent String"
BROWSER_COL = "Browser Name and Version"
OS_COL = "OS Name and Version"
ACCOUNT_TAKEOVER_COL = "Is Account Takeover"
LAT_COL = None
LON_COL = None