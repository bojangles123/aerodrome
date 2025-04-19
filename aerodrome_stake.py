# aerodrome_stake.py
import time
import logging
import json
import os
from wallet_setup import web3, wallet_address, private_key

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("aerodrome_stake.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger()

# Contract addresses
NPM_ADDRESS = web3.to_checksum_address("0x827922686190790b37229fd06084350e74485b72")
CL_GAUGE_ADDRESS = web3.to_checksum_address("0xF33a96b5932D9E9B9A0eDA447AbD8C9d48d2e0c8")

# ABIs
NPM_ABI = '''[
    {"inputs":[{"internalType":"address","name":"owner","type":"address"}],"name":"balanceOf","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
    {"inputs":[{"internalType":"address","name":"owner","type":"address"},{"internalType":"uint256","name":"index","type":"uint256"}],"name":"tokenOfOwnerByIndex","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
    {"inputs":[{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"tokenId","type":"uint256"}],"name":"approve","outputs":[],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"internalType":"uint256","name":"tokenId","type":"uint256"}],"name":"getApproved","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"}
]'''

CL_GAUGE_ABI = '''[
    {"inputs":[{"internalType":"uint256","name":"_tokenId","type":"uint256"}],"name":"deposit","outputs":[],"stateMutability":"nonpayable","type":"function"}
]'''

# Initialize contracts
npm_contract = web3.eth.contract(address=NPM_ADDRESS, abi=NPM_ABI)
cl_gauge_contract = web3.eth.contract(address=CL_GAUGE_ADDRESS, abi=CL_GAUGE_ABI)

# File to store the position ID
POSITION_FILE = "active_position.json"

def store_position_id(token_id):
    """Store position ID to file"""
    data = {
        'position_id': token_id,
        'timestamp': time.time(),
        'date': time.strftime('%Y-%m-%d %H:%M:%S')
    }

    with open(POSITION_FILE, 'w') as f:
        json.dump(data, f, indent=2)

    logger.info(f"Position ID {token_id} stored in {POSITION_FILE}")

def get_latest_position_id():
    """Get the latest position owned by the wallet"""
    try:
        # Check how many positions we have
        num_positions = npm_contract.functions.balanceOf(wallet_address).call()

        if num_positions == 0:
            logger.warning("No positions found in wallet")
            return None

        # Get the most recent position
        latest_position = npm_contract.functions.tokenOfOwnerByIndex(wallet_address, num_positions - 1).call()
        logger.info(f"Found latest position ID: {latest_position}")
        return latest_position

    except Exception as e:
        logger.error(f"Error finding latest position: {e}")
        return None

def check_position_approval(token_id, approval_address):
    """Check if position is approved for the specified address"""
    try:
        approved = npm_contract.functions.getApproved(token_id).call()
        return approved.lower() == approval_address.lower()
    except Exception as e:
        logger.error(f"Error checking approval status: {e}")
        return False

def approve_position(token_id):
    """Approve the position for the gauge contract"""
    try:
        # Check if already approved
        if check_position_approval(token_id, CL_GAUGE_ADDRESS):
            logger.info(f"Position {token_id} is already approved for gauge")
            return True

        logger.info(f"Approving position {token_id} for gauge...")

        # Get fresh nonce and gas price
        nonce = web3.eth.get_transaction_count(wallet_address)
        gas_price = int(web3.eth.gas_price * 1.2)

        # Build transaction
        tx = npm_contract.functions.approve(CL_GAUGE_ADDRESS, token_id).build_transaction({
            'from': wallet_address,
            'nonce': nonce,
            'gasPrice': gas_price,
            'chainId': web3.eth.chain_id
        })

        # Sign and send transaction
        signed_tx = web3.eth.account.sign_transaction(tx, private_key)
        tx_hash = web3.eth.send_raw_transaction(signed_tx.raw_transaction)

        logger.info(f"Approval transaction sent: {tx_hash.hex()}")

        # Wait for transaction receipt
        receipt = web3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
        if receipt.status == 1:
            logger.info(f"Position {token_id} approval successful")
            return True
        else:
            logger.error(f"Failed to approve position {token_id}")
            return False

    except Exception as e:
        logger.error(f"Error approving position: {e}")
        return False

def stake_position(token_id=None):
    """Stake a position in the gauge and store the ID"""
    try:
        # If no token_id provided, find the latest one
        if token_id is None:
            token_id = get_latest_position_id()
            if token_id is None:
                logger.error("No position found to stake")
                return False

        logger.info(f"Preparing to stake position {token_id}")

        # Approve to the gauge if needed
        if not check_position_approval(token_id, CL_GAUGE_ADDRESS):
            if not approve_position(token_id):
                logger.error("Approval failed. Cannot stake.")
                return False
            logger.info("Approval successful. Waiting before deposit...")
            time.sleep(5)  # Wait for approval to be registered

        logger.info(f"Staking position {token_id}...")

        # Get fresh nonce and gas price
        nonce = web3.eth.get_transaction_count(wallet_address)
        gas_price = int(web3.eth.gas_price * 1.2)

        # Build transaction
        tx = cl_gauge_contract.functions.deposit(token_id).build_transaction({
            'from': wallet_address,
            'nonce': nonce,
            'gasPrice': gas_price,
            'gas': 1000000,  # 1M gas limit
            'chainId': web3.eth.chain_id
        })

        # Sign and send transaction
        signed_tx = web3.eth.account.sign_transaction(tx, private_key)
        tx_hash = web3.eth.send_raw_transaction(signed_tx.raw_transaction)

        logger.info(f"Staking transaction sent: {tx_hash.hex()}")
        logger.info(f"Track on BaseScan: https://basescan.org/tx/{tx_hash.hex()}")

        # Wait for transaction receipt
        receipt = web3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)

        if receipt.status == 1:
            logger.info(f"Position {token_id} successfully staked!")

            # Store the position ID
            store_position_id(token_id)

            return True
        else:
            logger.error(f"Failed to stake position {token_id}")
            return False

    except Exception as e:
        logger.error(f"Error staking position: {e}")
        return False

# Main execution
if __name__ == "__main__":
    stake_position()
