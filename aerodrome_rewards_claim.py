# aerodrome_rewards_claim.py
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
        logging.FileHandler("aerodrome_rewards.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger()

# Contract address
CL_GAUGE_ADDRESS = web3.to_checksum_address("0xF33a96b5932D9E9B9A0eDA447AbD8C9d48d2e0c8")

# File where position ID is stored
POSITION_FILE = "active_position.json"

# Gauge ABI
GAUGE_ABI = '''[{"inputs":[{"internalType":"uint256","name":"tokenId","type":"uint256"}],"name":"getReward","outputs":[],"stateMutability":"nonpayable","type":"function"}]'''

# Initialize contract
gauge_contract = web3.eth.contract(address=CL_GAUGE_ADDRESS, abi=GAUGE_ABI)

def get_stored_position_id():
    """Get position ID from stored file"""
    try:
        if not os.path.exists(POSITION_FILE):
            logger.warning(f"Position file {POSITION_FILE} not found")
            return None
            
        with open(POSITION_FILE, 'r') as f:
            data = json.load(f)
            
        token_id = data.get('position_id')
        if token_id:
            logger.info(f"Found stored position ID: {token_id}")
            return token_id
        else:
            logger.warning("No position ID found in stored file")
            return None
            
    except Exception as e:
        logger.error(f"Error reading stored position ID: {e}")
        return None

def claim_rewards(token_id=None):
    """Claim rewards for a staked position"""
    try:
        # If no token_id provided, try to get the stored one
        if token_id is None:
            token_id = get_stored_position_id()
            if token_id is None:
                logger.error("No position ID found to claim rewards")
                return False
                
        logger.info(f"Claiming rewards for position ID: {token_id}")
        
        # Get transaction parameters
        nonce = web3.eth.get_transaction_count(wallet_address)
        gas_price = int(web3.eth.gas_price * 1.2)
        
        # Build transaction
        tx = gauge_contract.functions.getReward(token_id).build_transaction({
            'from': wallet_address,
            'nonce': nonce,
            'gasPrice': gas_price,
            'gas': 1000000,  # 1M gas limit
            'chainId': web3.eth.chain_id
        })
        
        # Log transaction details
        logger.info(f"Transaction details:")
        logger.info(f"  From: {wallet_address}")
        logger.info(f"  To: {CL_GAUGE_ADDRESS}")
        logger.info(f"  Gas Price: {gas_price / 1e9:.2f} Gwei")
        logger.info(f"  Gas Limit: 1,000,000")
        logger.info(f"  Function: getReward({token_id})")
        
        # Sign and send transaction
        signed_tx = web3.eth.account.sign_transaction(tx, private_key)
        tx_hash = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
        tx_hash_hex = tx_hash.hex()
        
        logger.info(f"Transaction sent: {tx_hash_hex}")
        logger.info(f"Track on BaseScan: https://basescan.org/tx/{tx_hash_hex}")
        
        # Wait for receipt
        logger.info("Waiting for transaction to be mined...")
        receipt = web3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
        
        if receipt.status == 1:
            logger.info(f"Rewards successfully claimed for position {token_id}!")
            return True
        else:
            logger.error(f"Failed to claim rewards for position {token_id}")
            logger.error(f"Check transaction: https://basescan.org/tx/{tx_hash_hex}")
            return False
    
    except Exception as e:
        logger.error(f"Error claiming rewards: {e}")
        if "execution reverted" in str(e).lower():
            logger.error("There might be no rewards to claim or the position is not staked")
        return False

# When run directly
if __name__ == "__main__":
    # If command line argument is provided, use it as token_id
    import sys
    if len(sys.argv) > 1:
        try:
            token_id = int(sys.argv[1])
            claim_rewards(token_id)
        except ValueError:
            logger.error(f"Invalid position ID: {sys.argv[1]}")
    else:
        # Otherwise use the stored position ID
        claim_rewards()
