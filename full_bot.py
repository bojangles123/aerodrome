# aerodrome_bot.py
import time
import math
import json
import schedule
import logging
import os.path
from decimal import Decimal, getcontext
from datetime import datetime, timedelta
from wallet_setup import web3, wallet_address, private_key, weth_contract, usdc_contract

# Set decimal precision
getcontext().prec = 28

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("aerodrome_bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger()

# Check which file exists for position creation
if os.path.exists('aerodrome_swap_and_deposit.py'):
    DEPOSIT_FILE = 'aerodrome_swap_and_deposit'
    logger.info("Using aerodrome_swap_and_deposit.py for position creation")
elif os.path.exists('aerodrome_auto_deposit.py'):
    DEPOSIT_FILE = 'aerodrome_auto_deposit'
    logger.info("Using aerodrome_auto_deposit.py for position creation")
else:
    logger.warning("Neither deposit file found, will attempt aerodrome_swap_and_deposit.py")
    DEPOSIT_FILE = 'aerodrome_swap_and_deposit'

# Contract addresses
NPM_ADDRESS = web3.to_checksum_address("0x827922686190790b37229fd06084350e74485b72")
POOL_ADDRESS = web3.to_checksum_address("0xb2cc224c1c9feE385f8ad6a55b4d94e92359dc59")
HELPER_ADDRESS = web3.to_checksum_address("0x9c62ab10577fB3C20A22E231b7703Ed6D456CC7a")
WETH_ADDRESS = web3.to_checksum_address("0x4200000000000000000000000000000000000006")
USDC_ADDRESS = web3.to_checksum_address("0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913")
CL_GAUGE_ADDRESS = web3.to_checksum_address("0xF33a96b5932D9E9B9A0eDA447AbD8C9d48d2e0c8")
AERO_ADDRESS = web3.to_checksum_address("0x940181a94A35A4569E4529A3CDfB74e38FD98631")

# Router for swapping tokens
ROUTER_ADDRESS = web3.to_checksum_address("0xcF77a3Ba9A5CA399B7c97c74d54e5b1Beb874E43")

# Load ABIs from files
def load_abi(file_path):
    try:
        with open(file_path, 'r') as f:
            return f.read()
    except Exception as e:
        logger.error(f"Error loading ABI from {file_path}: {e}")
        return ""

POOL_ABI = load_abi('abis/pool_abi.json')
HELPER_ABI = load_abi('abis/helper_abi.json')
ERC20_ABI = load_abi('abis/erc20_abi.json')
NPM_ABI = load_abi('abis/npm_abi.json')
GAUGE_ABI = load_abi('abis/gauge_abi.json')
ROUTER_ABI = load_abi('abis/router_abi.json')

# Initialize contracts
pool_contract = web3.eth.contract(address=POOL_ADDRESS, abi=POOL_ABI)
helper_contract = web3.eth.contract(address=HELPER_ADDRESS, abi=HELPER_ABI)
weth_token = web3.eth.contract(address=WETH_ADDRESS, abi=ERC20_ABI)
usdc_token = web3.eth.contract(address=USDC_ADDRESS, abi=ERC20_ABI)
aero_token = web3.eth.contract(address=AERO_ADDRESS, abi=ERC20_ABI)
npm_contract = web3.eth.contract(address=NPM_ADDRESS, abi=NPM_ABI)
gauge_contract = web3.eth.contract(address=CL_GAUGE_ADDRESS, abi=GAUGE_ABI)
router_contract = web3.eth.contract(address=ROUTER_ADDRESS, abi=ROUTER_ABI)

# Constants
SLIPPAGE = Decimal('0.005')  # 0.5% slippage tolerance
MAX_UINT128 = 2**128 - 1
MAX_UINT256 = 2**256 - 1
GAS_PRICE_MULTIPLIER = 1.5
GAS_LIMIT_HIGH = 3000000  # 3M for complex operations
GAS_LIMIT_MEDIUM = 1000000  # 1M for simpler operations
GAS_LIMIT_LOW = 500000  # 500k for basic operations
RETRY_ATTEMPTS = 3
RETRY_DELAY = 10  # seconds

# Bot state
active_position_id = None
last_position_check = None

def get_token_balances():
    """Get current token balances"""
    weth_balance = Decimal(weth_token.functions.balanceOf(wallet_address).call()) / Decimal(1e18)
    usdc_balance = Decimal(usdc_token.functions.balanceOf(wallet_address).call()) / Decimal(1e6)
    aero_balance = Decimal(aero_token.functions.balanceOf(wallet_address).call()) / Decimal(1e18)
    return weth_balance, usdc_balance, aero_balance

def get_pool_info():
    """Get current tick, tick spacing, and price from the pool"""
    for attempt in range(RETRY_ATTEMPTS):
        try:
            slot0 = pool_contract.functions.slot0().call()
            current_tick = slot0[1]
            sqrt_price_x96 = slot0[0]
            tick_spacing = pool_contract.functions.tickSpacing().call()

            # Calculate price from sqrtPriceX96
            price = (Decimal(sqrt_price_x96) / Decimal(2**96)) ** 2 * Decimal(1e12)
            eth_price_in_usdc = float(price)

            logger.info(f"Current tick: {current_tick}")
            logger.info(f"Tick spacing: {tick_spacing}")
            logger.info(f"Current ETH price: ${eth_price_in_usdc:.2f}")

            return current_tick, tick_spacing, sqrt_price_x96, eth_price_in_usdc
        
        except Exception as e:
            if attempt < RETRY_ATTEMPTS - 1:
                logger.warning(f"Error getting pool info (attempt {attempt+1}/{RETRY_ATTEMPTS}): {e}")
                time.sleep(RETRY_DELAY)
            else:
                logger.error(f"Failed to get pool info after {RETRY_ATTEMPTS} attempts: {e}")
                raise

def ensure_approval(token, amount, spender):
    """Ensure token is approved for spender"""
    token_symbol = "WETH" if token.address == WETH_ADDRESS else "USDC" if token.address == USDC_ADDRESS else "AERO"
    spender_name = "NPM" if spender == NPM_ADDRESS else "Router" if spender == ROUTER_ADDRESS else "Gauge"

    try:
        allowance = token.functions.allowance(wallet_address, spender).call()
        if allowance >= amount:
            logger.info(f"{token_symbol} already approved for {spender_name}")
            return True

        logger.info(f"Approving {token_symbol} for {spender_name}...")
        tx = token.functions.approve(spender, MAX_UINT256).build_transaction({
            'from': wallet_address,
            'nonce': web3.eth.get_transaction_count(wallet_address),
            'gasPrice': web3.eth.gas_price,
            'chainId': web3.eth.chain_id
        })

        signed_tx = web3.eth.account.sign_transaction(tx, private_key)
        tx_hash = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = web3.eth.wait_for_transaction_receipt(tx_hash)

        logger.info(f"{token_symbol} approval tx: {receipt.transactionHash.hex()}")
        return receipt.status == 1
    except Exception as e:
        logger.error(f"Error approving {token_symbol} for {spender_name}: {e}")
        return False

def create_position():
    """Create a CL position with +/-2% range using the existing deposit module"""
    global active_position_id
    
    try:
        logger.info(f"Creating new position using {DEPOSIT_FILE}.py")
        
        # Dynamically import the module
        deposit_module = __import__(DEPOSIT_FILE)
        
        # Try different function names based on what's available in the module
        if hasattr(deposit_module, 'create_position_ui_flow_with_rebalance'):
            logger.info("Using create_position_ui_flow_with_rebalance function")
            create_function = deposit_module.create_position_ui_flow_with_rebalance
        elif hasattr(deposit_module, 'create_position_ui_flow'):
            logger.info("Using create_position_ui_flow function")
            create_function = deposit_module.create_position_ui_flow
        else:
            logger.error(f"No suitable position creation function found in {DEPOSIT_FILE}.py")
            return None
        
        # Call the create position function
        result = create_function()
        
        if result:
            # Find the latest position created
            num_positions = npm_contract.functions.balanceOf(wallet_address).call()
            if num_positions > 0:
                latest_token_id = npm_contract.functions.tokenOfOwnerByIndex(wallet_address, num_positions - 1).call()
                logger.info(f"New position created with ID: {latest_token_id}")
                active_position_id = latest_token_id
                
                # Stake position immediately
                stake_position(latest_token_id)
                
                return latest_token_id
            else:
                logger.error("Position creation reported success but no position found")
                return None
        else:
            logger.error("Failed to create position")
            return None
            
    except Exception as e:
        logger.error(f"Error in create_position: {e}")
        return None

def stake_position(token_id):
    """Stake position in the gauge"""
    try:
        logger.info(f"Staking position ID: {token_id}")
        
        # Ensure the NFT is approved for the gauge
        approval_check = npm_contract.functions.getApproved(token_id).call()
        
        if approval_check != CL_GAUGE_ADDRESS:
            logger.info("Approving NFT for gauge...")
            
            # Approve NFT
            approve_tx = npm_contract.functions.approve(CL_GAUGE_ADDRESS, token_id).build_transaction({
                'from': wallet_address,
                'nonce': web3.eth.get_transaction_count(wallet_address),
                'gasPrice': int(web3.eth.gas_price * GAS_PRICE_MULTIPLIER),
                'chainId': web3.eth.chain_id
            })
            
            signed_tx = web3.eth.account.sign_transaction(approve_tx, private_key)
            tx_hash = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
            
            logger.info(f"Approval transaction sent: {tx_hash.hex()}")
            receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
            
            if receipt.status != 1:
                logger.error("NFT approval failed")
                return False
                
            logger.info("NFT approved for gauge")
        
        # Stake the position using deposit function
        stake_tx = gauge_contract.functions.deposit(token_id).build_transaction({
            'from': wallet_address,
            'nonce': web3.eth.get_transaction_count(wallet_address),
            'gasPrice': int(web3.eth.gas_price * GAS_PRICE_MULTIPLIER),
            'gas': GAS_LIMIT_MEDIUM,
            'chainId': web3.eth.chain_id
        })
        
        signed_tx = web3.eth.account.sign_transaction(stake_tx, private_key)
        tx_hash = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
        
        logger.info(f"Stake transaction sent: {tx_hash.hex()}")
        receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
        
        if receipt.status == 1:
            logger.info(f"Position {token_id} successfully staked")
            return True
        else:
            logger.error(f"Failed to stake position {token_id}")
            return False
            
    except Exception as e:
        logger.error(f"Error staking position: {e}")
        return False

def check_position_in_range(token_id):
    """Check if position is within the current tick range"""
    try:
        # Get position details
        position = npm_contract.functions.positions(token_id).call()
        tick_lower = position[5]
        tick_upper = position[6]
        
        # Get current tick
        current_tick, _, _, _ = get_pool_info()
        
        # Check if position is in range
        in_range = tick_lower <= current_tick <= tick_upper
        
        logger.info(f"Position {token_id} range: {tick_lower} to {tick_upper}")
        logger.info(f"Current tick: {current_tick}")
        logger.info(f"Position is {'in' if in_range else 'out of'} range")
        
        return in_range
        
    except Exception as e:
        logger.error(f"Error checking position range: {e}")
        return None

def daily_claim_and_sell():
    """Claim rewards daily and sell AERO for USDC"""
    global active_position_id
    
    logger.info("Performing daily claim and sell")
    
    if active_position_id is None:
        # Find active position if we don't know it
        positions = list_positions()
        if positions:
            active_position_id = positions[0]['token_id']
        else:
            logger.warning("No active position found for daily claim")
            return
    
    # Import here to avoid circular imports
    from aerodrome_rewards_claim import claim_rewards
    
    # Claim rewards
    if claim_rewards(active_position_id):
        logger.info("Rewards claimed successfully")
        # TODO: Implement sell AERO for USDC logic
        # This would require using a DEX like Aerodrome's router
        # For now, we'll just log this step
        logger.info("AERO tokens would be sold to USDC here")
    else:
        logger.warning("Failed to claim rewards")

def monitor_and_rebalance():
    """Monitor position and rebalance if needed"""
    global active_position_id, last_position_check
    
    current_time = time.time()
    
    # Limit check frequency
    if last_position_check and current_time - last_position_check < 300:  # 5 minutes
        return
        
    last_position_check = current_time
    
    logger.info("Monitoring position...")
    
    if active_position_id is None:
        # Find active position if we don't know it
        positions = list_positions()
        if positions:
            active_position_id = positions[0]['token_id']
        else:
            logger.info("No active position found, creating one...")
            active_position_id = create_position()
            return
    
    # Check if position is in range
    in_range = check_position_in_range(active_position_id)
    
    if in_range is False:  # Only rebalance if explicitly out of range
        logger.info("Position out of range, rebalancing...")
        
        # Import modules only when needed
        from aerodrome_rewards_claim import claim_rewards
        from aerodrome_unstake import unstake_position
        import aerodrome_withdraw
        
        # 1. Claim rewards
        if not claim_rewards(active_position_id):
            logger.warning("Failed to claim rewards, continuing with rebalance anyway")
        
        # 2. Unstake position
        if not unstake_position(active_position_id):
            logger.error("Failed to unstake position, aborting rebalance")
            return
            
        # 3. Withdraw position
        try:
            logger.info("Withdrawing position using aerodrome_withdraw.py")
            aerodrome_withdraw.main()
        except Exception as e:
            logger.error(f"Error in withdrawal step: {e}")
            return
        
        # 4. Create new position
        active_position_id = create_position()
        
        if active_position_id:
            logger.info(f"Rebalance complete, new position ID: {active_position_id}")
        else:
            logger.error("Rebalance failed - could not create new position")

def list_positions():
    """List all CL positions owned by the user"""
    try:
        # Get number of positions owned by the user
        num_positions = npm_contract.functions.balanceOf(wallet_address).call()
        
        if num_positions == 0:
            logger.info("No positions found")
            return []
            
        positions = []
        logger.info(f"Found {num_positions} position(s)")
        
        for i in range(num_positions):
            # Get token ID for each position
            token_id = npm_contract.functions.tokenOfOwnerByIndex(wallet_address, i).call()
            
            # Get position details
            position = npm_contract.functions.positions(token_id).call()
            
            # Extract relevant details
            token0 = position[2]
            token1 = position[3]
            tick_lower = position[5]
            tick_upper = position[6]
            liquidity = position[7]
            
            # Determine token names
            token0_name = "WETH" if token0.lower() == WETH_ADDRESS.lower() else "USDC"
            token1_name = "USDC" if token1.lower() == USDC_ADDRESS.lower() else "WETH"
            
            # Store position details
            position_info = {
                'token_id': token_id,
                'token0': token0,
                'token1': token1,
                'token0_name': token0_name,
                'token1_name': token1_name,
                'tick_lower': tick_lower,
                'tick_upper': tick_upper,
                'liquidity': liquidity
            }
            positions.append(position_info)
            
            logger.info(f"Position #{i+1} (Token ID: {token_id}):")
            logger.info(f"  Tokens: {token0_name}/{token1_name}")
            logger.info(f"  Tick Range: {tick_lower} to {tick_upper}")
            logger.info(f"  Liquidity: {liquidity}")
            
        return positions
        
    except Exception as e:
        logger.error(f"Error listing positions: {e}")
        return []

def initialize_bot():
    """Initialize the bot and find or create a position"""
    global active_position_id
    
    logger.info("Initializing Aerodrome Liquidity Management Bot")
    
    # Get token balances
    weth_balance, usdc_balance, aero_balance = get_token_balances()
    logger.info(f"Initial balances: {weth_balance} WETH, {usdc_balance} USDC, {aero_balance} AERO")
    
    # Check for existing positions
    positions = list_positions()
    
    if positions:
        # Use the first position found
        active_position_id = positions[0]['token_id']
        logger.info(f"Using existing position: {active_position_id}")
        
        # Check if position is staked - if not, stake it
        try:
            # We could verify if position is already staked here, but for simplicity
            # we'll just try to stake it and handle any errors
            stake_position(active_position_id)
        except Exception as e:
            logger.warning(f"Error staking position (might already be staked): {e}")
    else:
        # Create a new position
        logger.info("No positions found, creating a new one")
        active_position_id = create_position()
        
    logger.info("Bot initialized successfully")

def run_bot():
    """Main bot loop"""
    # Initialize bot
    initialize_bot()
    
    # Schedule daily claim and sell at midnight
    schedule.every().day.at("00:00").do(daily_claim_and_sell)
    
    # Main loop
    while True:
        try:
            # Run scheduled tasks
            schedule.run_pending()
            
            # Monitor and rebalance if needed
            monitor_and_rebalance()
            
            # Sleep to avoid excessive API calls
            time.sleep(60)  # Check every minute
            
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            time.sleep(300)  # Longer sleep on error

def main():
    """Entry point"""
    try:
        run_bot()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.critical(f"Critical error: {e}")

if __name__ == "__main__":
    main()
