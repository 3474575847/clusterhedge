import os
import secrets
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///clusterhedge.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Material Ticker Mapping (Initial Set)
    MATERIAL_TICKERS = {
        'copper': 'CPER',
        'lumber': 'WOOD',
        'steel': 'SLX',
        'gold': 'GLD',
        'silver': 'SLV'
    }
    
    # Default Proxy Hedge ETFs
    PROXY_ETFS = ['CPER', 'WOOD', 'SLX', 'GLD', 'SLV', 'DBB', 'XME']
