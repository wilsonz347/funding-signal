import databricks
from dotenv import load_dotenv
from databricks import sql
from databricks.sdk.core import Config, oauth_service_principal

load_dotenv()

# Load the environment variables
host = os.environ["DATABRICKS_HOST"]
http_path = os.environ["DATABRICKS_HTTP_PATH"]
client_id = os.environ["DATABRICKS_CLIENT_ID"]
client_secret = os.environ["DATABRICKS_CLIENT_SECRET"]

def creds():
    return oauth_service_principal(Config(
        host=f"https://{host}",
        client_id=client_id,
        client_secret=client_secret,
    ))

conn = sql.connect(
    server_hostname=host,
    http_path=http_path,
    credentials_provider=creds,
)

with conn.cursor() as cursor:
    cursor.execute("""
        SELECT COUNT(*)
        FROM funding_regime_project.gold.funding_rate_analysis
    """)
    
    result = cursor.fetchone()
    print("Row count:", result[0])

conn.close()