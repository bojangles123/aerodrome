# aerodrome_unstake.py
from wallet_setup import web3, wallet_address, private_key
import time
import sys
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("aerodrome_unstake.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger()

# Contract address
CL_GAUGE_ADDRESS = web3.to_checksum_address("0xF33a96b5932D9E9B9A0eDA447AbD8C9d48d2e0c8")

# Position Manager address
NPM_ADDRESS = web3.to_checksum_address("0x827922686190790b37229fd06084350e74485b72")

# ABIs
WITHDRAW_ABI = '''[{"inputs":[{"internalType":"uint256","name":"tokenId","type":"uint256"}],"name":"withdraw","outputs":[],"stateMutability":"nonpayable","type":"function"}]'''

NPM_ABI = '''[{"inputs":[{"internalType":"address","name":"owner","type":"address"}],"name":"balanceOf","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
{"inputs":[{"internalType":"address","name":"owner","type":"address"},{"internalType":"uint256","name":"index","type":"uint256"}],"name":"tokenOfOwnerByIndex","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"}]'''

def find_latest_position():
    """Find the most recent position owned by the wallet"""
    # Initialize Position Manager contract
    npm_contract = web3.eth.contract(address=NPM_ADDRESS, abi=NPM_ABI)
    
    # Get number of positions
    num_positions = npm_contract.functions.balanceOf(wallet_address).call()
    
    if num_positions == 0:
        logger.warning("No positions found in wallet")
        return None
        
    # Get most recent position token ID
    latest_position = npm_contract.functions.tokenOfOwnerByIndex(wallet_address, num_positions - 1).call()
    logger.info(f"Found latest position: {latest_position}")
    return latest_position

def unstake_position(token_id=None):
    """Unstake position from gauge - fully autonomous"""
    try:
        # If no token_id provided, find the latest position
        if token_id is None:
            token_id = find_latest_position()
            if token_id is None:
                logger.error("No position available to unstake")
                return False
        
        logger.info(f"Unstaking position ID: {token_id}")
        
        # Initialize contract
        contract = web3.eth.contract(address=CL_GAUGE_ADDRESS, abi=WITHDRAW_ABI)

        # Build transaction
        nonce = web3.eth.get_transaction_count(wallet_address)
        gas_price = int(web3.eth.gas_price * 1.5)  # Increased multiplier for better success rate

        tx = contract.functions.withdraw(token_id).build_transaction({
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
        logger.info(f"  Function: withdraw({token_id})")

        # Sign and send without prompt
        signed_tx = web3.eth.account.sign_transaction(tx, private_key)
        tx_hash = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
        tx_hash_hex = tx_hash.hex()

        logger.info(f"Transaction sent: {tx_hash_hex}")
        logger.info(f"Track on BaseScan: https://basescan.org/tx/{tx_hash_hex}")

        # Wait for receipt
        logger.info("Waiting for transaction to be mined...")
        receipt = web3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)

        if receipt.status == 1:
            logger.info("Position successfully unstaked!")
            return True
        else:
            logger.error("Unstaking failed")
            logger.error(f"Check transaction: https://basescan.org/tx/{tx_hash_hex}")
            return False

    except Exception as e:
        logger.error(f"Error unstaking position: {e}")
        return False

# When run directly, either use the position ID from command line or the latest one
if __name__ == "__main__":
    # Check if a position ID was provided as a command-line argument
    if len(sys.argv) > 1:
        try:
            position_id = int(sys.argv[1])
            unstake_position(position_id)
        except ValueError:
            logger.error(f"Invalid position ID: {sys.argv[1]}")
    else:
        # No ID provided, unstake the latest position
        unstake_position()
