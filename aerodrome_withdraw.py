# aerodrome_position_withdraw.py

import time
from decimal import Decimal, getcontext
from wallet_setup import web3, wallet_address, private_key, weth_contract, usdc_contract

getcontext().prec = 28

# Contract addresses
NPM_ADDRESS = web3.to_checksum_address("0x827922686190790b37229fd06084350e74485b72")
WETH_ADDRESS = web3.to_checksum_address("0x4200000000000000000000000000000000000006")
USDC_ADDRESS = web3.to_checksum_address("0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913")

# ABI for position manager (only relevant functions)
NPM_ABI = '''
[
    {"inputs":[{"internalType":"address","name":"owner","type":"address"}],"name":"balanceOf","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
    {"inputs":[{"internalType":"address","name":"owner","type":"address"},{"internalType":"uint256","name":"index","type":"uint256"}],"name":"tokenOfOwnerByIndex","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
    {"inputs":[{"internalType":"uint256","name":"tokenId","type":"uint256"}],"name":"positions","outputs":[{"internalType":"uint96","name":"nonce","type":"uint96"},{"internalType":"address","name":"operator","type":"address"},{"internalType":"address","name":"token0","type":"address"},{"internalType":"address","name":"token1","type":"address"},{"internalType":"int24","name":"tickSpacing","type":"int24"},{"internalType":"int24","name":"tickLower","type":"int24"},{"internalType":"int24","name":"tickUpper","type":"int24"},{"internalType":"uint128","name":"liquidity","type":"uint128"},{"internalType":"uint256","name":"feeGrowthInside0LastX128","type":"uint256"},{"internalType":"uint256","name":"feeGrowthInside1LastX128","type":"uint256"},{"internalType":"uint128","name":"tokensOwed0","type":"uint128"},{"internalType":"uint128","name":"tokensOwed1","type":"uint128"}],"stateMutability":"view","type":"function"},
    {"inputs":[{"components":[{"internalType":"uint256","name":"tokenId","type":"uint256"},{"internalType":"uint128","name":"liquidity","type":"uint128"},{"internalType":"uint256","name":"amount0Min","type":"uint256"},{"internalType":"uint256","name":"amount1Min","type":"uint256"},{"internalType":"uint256","name":"deadline","type":"uint256"}],"internalType":"struct INonfungiblePositionManager.DecreaseLiquidityParams","name":"params","type":"tuple"}],"name":"decreaseLiquidity","outputs":[{"internalType":"uint256","name":"amount0","type":"uint256"},{"internalType":"uint256","name":"amount1","type":"uint256"}],"stateMutability":"payable","type":"function"},
    {"inputs":[{"components":[{"internalType":"uint256","name":"tokenId","type":"uint256"},{"internalType":"address","name":"recipient","type":"address"},{"internalType":"uint128","name":"amount0Max","type":"uint128"},{"internalType":"uint128","name":"amount1Max","type":"uint128"}],"internalType":"struct INonfungiblePositionManager.CollectParams","name":"params","type":"tuple"}],"name":"collect","outputs":[{"internalType":"uint256","name":"amount0","type":"uint256"},{"internalType":"uint256","name":"amount1","type":"uint256"}],"stateMutability":"payable","type":"function"},
    {"inputs":[{"internalType":"uint256","name":"tokenId","type":"uint256"}],"name":"burn","outputs":[],"stateMutability":"payable","type":"function"}
]
'''

# Initialize contract
npm_contract = web3.eth.contract(address=NPM_ADDRESS, abi=NPM_ABI)

def get_token_balances():
    """Get current WETH and USDC balances"""
    weth_balance = Decimal(weth_contract.functions.balanceOf(wallet_address).call()) / Decimal(1e18)
    usdc_balance = Decimal(usdc_contract.functions.balanceOf(wallet_address).call()) / Decimal(1e6)
    return weth_balance, usdc_balance

def list_positions():
    """List all CL positions owned by the user"""
    try:
        # Get number of positions owned by the user
        num_positions = npm_contract.functions.balanceOf(wallet_address).call()

        if num_positions == 0:
            print("You don't have any positions.")
            return []

        positions = []
        print(f"Found {num_positions} position(s):")

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

            # Display position
            print(f"Position #{i+1} (Token ID: {token_id}):")
            print(f"  Tokens: {token0_name}/{token1_name}")
            print(f"  Tick Range: {tick_lower} to {tick_upper}")
            print(f"  Liquidity: {liquidity}")
            print()

        return positions

    except Exception as e:
        print(f"Error listing positions: {e}")
        return []

def decrease_liquidity(token_id):
    """Remove all liquidity from a position"""
    try:
        # Get position details
        position = npm_contract.functions.positions(token_id).call()
        liquidity = position[7]

        if liquidity == 0:
            print(f"Position {token_id} has no liquidity to remove.")
            return True

        print(f"Removing {liquidity} liquidity from position {token_id}...")

        # Prepare decrease liquidity parameters
        decrease_params = {
            'tokenId': token_id,
            'liquidity': liquidity,
            'amount0Min': 0,  # No slippage protection for simplicity, can be improved
            'amount1Min': 0,  # No slippage protection for simplicity, can be improved
            'deadline': int(time.time() + 3600)
        }

        # Get fresh nonce and gas price
        nonce = web3.eth.get_transaction_count(wallet_address, 'pending')
        gas_price = int(web3.eth.gas_price * 1.5)

        print(f"Using nonce: {nonce}")

        # Build transaction
        tx = npm_contract.functions.decreaseLiquidity(decrease_params).build_transaction({
            'from': wallet_address,
            'gas': 500000,
            'gasPrice': gas_price,
            'nonce': nonce,
            'value': 0,
            'chainId': web3.eth.chain_id
        })

        # Sign and send transaction
        signed_tx = web3.eth.account.sign_transaction(tx, private_key)
        tx_hash = web3.eth.send_raw_transaction(signed_tx.raw_transaction)

        print(f"Transaction sent: {tx_hash.hex()}")

        # Wait for transaction receipt
        receipt = web3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
        if receipt.status == 1:
            print("Successfully removed liquidity!")
            # Sleep briefly to ensure the transaction is fully processed
            time.sleep(5)
            return True
        else:
            print("Failed to remove liquidity.")
            return False

    except Exception as e:
        print(f"Error decreasing liquidity: {e}")
        return False

def collect_tokens(token_id):
    """Collect all tokens from a position"""
    try:
        # Maximum uint128 value for collecting all tokens
        max_uint128 = 2**128 - 1

        print(f"Collecting tokens from position {token_id}...")

        # Prepare collect parameters
        collect_params = {
            'tokenId': token_id,
            'recipient': wallet_address,
            'amount0Max': max_uint128,
            'amount1Max': max_uint128
        }

        # Get fresh nonce and gas price
        # Use 'pending' to get the latest nonce including pending transactions
        nonce = web3.eth.get_transaction_count(wallet_address, 'pending')
        gas_price = int(web3.eth.gas_price * 1.5)

        print(f"Using nonce: {nonce}")

        # Build transaction
        tx = npm_contract.functions.collect(collect_params).build_transaction({
            'from': wallet_address,
            'gas': 500000,
            'gasPrice': gas_price,
            'nonce': nonce,
            'value': 0,
            'chainId': web3.eth.chain_id
        })

        # Sign and send transaction
        signed_tx = web3.eth.account.sign_transaction(tx, private_key)
        tx_hash = web3.eth.send_raw_transaction(signed_tx.raw_transaction)

        print(f"Transaction sent: {tx_hash.hex()}")

        # Wait for transaction receipt
        receipt = web3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
        if receipt.status == 1:
            print("Successfully collected tokens!")
            return True
        else:
            print("Failed to collect tokens.")
            return False

    except Exception as e:
        print(f"Error collecting tokens: {e}")
        return False

def burn_position(token_id):
    """Burn the position NFT"""
    try:
        print(f"Burning position {token_id}...")

        # Get fresh nonce and gas price
        nonce = web3.eth.get_transaction_count(wallet_address, 'pending')
        gas_price = int(web3.eth.gas_price * 1.5)

        print(f"Using nonce: {nonce}")

        # Build transaction
        tx = npm_contract.functions.burn(token_id).build_transaction({
            'from': wallet_address,
            'gas': 300000,
            'gasPrice': gas_price,
            'nonce': nonce,
            'value': 0,
            'chainId': web3.eth.chain_id
        })

        # Sign and send transaction
        signed_tx = web3.eth.account.sign_transaction(tx, private_key)
        tx_hash = web3.eth.send_raw_transaction(signed_tx.raw_transaction)

        print(f"Transaction sent: {tx_hash.hex()}")

        # Wait for transaction receipt
        receipt = web3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
        if receipt.status == 1:
            print("Successfully burned position!")
            return True
        else:
            print("Failed to burn position.")
            return False

    except Exception as e:
        print(f"Error burning position: {e}")
        return False

def withdraw_position(token_id):
    """Complete workflow to withdraw a position"""
    # Get initial token balances
    initial_weth, initial_usdc = get_token_balances()
    print(f"Initial balances: {initial_weth} WETH, {initial_usdc} USDC")

    # Step 1: Remove liquidity
    if not decrease_liquidity(token_id):
        print("Failed to decrease liquidity. Aborting...")
        return False

    # Short delay to ensure blockchain state is updated
    print("Waiting for transaction to be fully processed...")
    time.sleep(10)

    # Step 2: Collect all tokens
    if not collect_tokens(token_id):
        print("Failed to collect tokens. Aborting...")
        return False

    # Short delay to ensure blockchain state is updated
    print("Waiting for transaction to be fully processed...")
    time.sleep(10)

    # Step 3: Burn the position NFT
    if not burn_position(token_id):
        print("Failed to burn position. The tokens have been collected but you still own the NFT.")
        return False

    # Get final token balances and show difference
    final_weth, final_usdc = get_token_balances()
    weth_gained = final_weth - initial_weth
    usdc_gained = final_usdc - initial_usdc

    print("\nWithdrawal completed successfully!")
    print(f"WETH gained: {weth_gained}")
    print(f"USDC gained: {usdc_gained}")
    print(f"Final balances: {final_weth} WETH, {final_usdc} USDC")

    return True

def main():
    print("Aerodrome CL Position Withdrawal")
    print("--------------------------------")

    # List all positions
    positions = list_positions()

    if not positions:
        print("No positions to withdraw.")
        return

    # Automatically process all positions
    for i, position in enumerate(positions):
        token_id = position['token_id']

        print(f"\nProcessing position #{i+1} (Token ID: {token_id}):")
        print(f"  Tokens: {position['token0_name']}/{position['token1_name']}")
        print(f"  Tick Range: {position['tick_lower']} to {position['tick_upper']}")
        print(f"  Liquidity: {position['liquidity']}")

        # Proceed with withdrawal
        success = withdraw_position(token_id)
        if success:
            print(f"Successfully withdrew position #{i+1} (Token ID: {token_id})")
        else:
            print(f"Failed to fully withdraw position #{i+1} (Token ID: {token_id})")

    print("\nAll positions processed.")

if __name__ == "__main__":
    main()
