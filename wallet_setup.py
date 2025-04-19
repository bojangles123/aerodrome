from web3 import Web3
import boto3
import base64

rpc_url = "https://base-mainnet.g.alchemy.com/v2/mLjg_Iy304gmi36XVvQoqEAjqYgCFSXE"
web3 = Web3(Web3.HTTPProvider(rpc_url))

# Fetch private key securely
region = "eu-north-1"
secrets_client = boto3.client('secretsmanager', region_name=region)
kms_client = boto3.client('kms', region_name=region)
secret_response = secrets_client.get_secret_value(SecretId='aerodrome-bot-eth-key')
encrypted_key_base64 = secret_response['SecretString'].split(":")[1].strip()
encrypted_key_bytes = base64.b64decode(encrypted_key_base64)
decrypted = kms_client.decrypt(CiphertextBlob=encrypted_key_bytes)
private_key = decrypted['Plaintext'].decode()

# Setup wallet
account = web3.eth.account.from_key(private_key)
wallet_address = account.address

# Token Addresses
WETH_ADDRESS = web3.to_checksum_address("0x4200000000000000000000000000000000000006")
USDC_ADDRESS = web3.to_checksum_address("0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913")
AERO_ADDRESS = web3.to_checksum_address("0x940181a94A35A4569E4529A3CDfB74e38FD98631")

# ERC20 ABI (standard minimal)
ERC20_ABI = '''
[
    {"constant":true,"inputs":[{"name":"account","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"type":"function"},
    {"constant":true,"inputs":[],"name":"decimals","outputs":[{"name":"","type":"uint8"}],"type":"function"},
    {"constant":false,"inputs":[{"name":"spender","type":"address"},{"name":"amount","type":"uint256"}],"name":"approve","outputs":[{"name":"","type":"bool"}],"type":"function"}
]
'''

# Token Contracts
weth_contract = web3.eth.contract(address=WETH_ADDRESS, abi=ERC20_ABI)
usdc_contract = web3.eth.contract(address=USDC_ADDRESS, abi=ERC20_ABI)
aero_contract = web3.eth.contract(address=AERO_ADDRESS, abi=ERC20_ABI)
